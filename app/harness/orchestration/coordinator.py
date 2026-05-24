# [阶段2] V2RunCoordinator：PPAF + harness mode_runner

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.harness.agents.chitchat import stream_chitchat
from app.harness.agents.clarify import stream_clarification
from app.harness.context.builder import build_runtime_context
from app.harness.orchestration.mode_runner import run_mode
from app.harness.perception.preflight import run_preflight
from app.harness.planning.gateway import classify_intent
from app.harness.planning.routing import resolve_route_action
from app.harness.sse.emit import emit_error, emit_think
from app.harness.types.context import HarnessMode, RuntimeContext
from app.harness.types.events import HarnessSSEEvent
from app.harness.types.intent import GatewayMode, IntentClassification
from app.harness.types.preflight import PreflightSnapshot
from app.services.thread_memory import resolve_stream_thread_id

logger = logging.getLogger(__name__)

_FORCE_GATEWAY_MODES: frozenset[GatewayMode] = frozenset(
    {"smart_query", "deep_research", "report", "chitchat"}
)
_CTX_BUILD_MODES: frozenset[HarnessMode] = frozenset(
    {"smart_query", "deep_research", "report", "chitchat", "clarification"}
)


class HarnessCoordinator:
    """[阶段2] V2 流式 Run 协调器：preflight → gateway → route → 执行分支。"""

    async def stream_run(
        self,
        *,
        agent_id: int,
        user_query: str,
        db: AsyncSession,
        thread_id: str | None,
        run_id: str,
        force_mode: str | None = None,
    ) -> AsyncIterator[HarnessSSEEvent]:
        """
        [阶段2] 主入口：处理用户查询并流式返回事件；多轮记忆暂不实现。
        
        该函数执行以下步骤：
        1. 预检查：验证用户请求是否被允许
        2. 意图分类：确定用户查询的意图类型
        3. 路由决策：根据意图选择合适的处理路径
        4. 构建运行时上下文
        5. 发送意图分析结果
        6. 根据路由执行相应的处理分支
        
        Args:
            agent_id: 智能体ID，用于标识处理请求的智能体
            user_query: 用户输入的查询字符串
            db: 异步数据库会话对象，用于数据库操作
            thread_id: 会话线程ID，用于关联对话历史，可选
            run_id: 运行ID，用于标识当前执行流程
            force_mode: 强制模式，用于覆盖默认的意图分类结果，可选
            
        Yields:
            HarnessSSEEvent: 一系列服务端发送事件，包含处理过程中的各种状态和结果
        """
        thread_id = resolve_stream_thread_id(thread_id)

        # ① 感知：Preflight（DB 探针，不涉及会话文件系统，Phase 3 再做 has_files）
        # 对用户请求进行预检查，验证其是否符合安全和合规要求
        preflight = await run_preflight(db, agent_id=agent_id, user_query=user_query)
        if preflight.blocked:
            yield emit_error(
                None,
                agent_id=agent_id,
                thread_id=thread_id,
                run_id=run_id,
                code=preflight.block_code or "PREFLIGHT_BLOCKED",
                summary="请求未通过安全校验",
            )
            return

        # ② 规划：Gateway 意图分类（无 conversation_history，H2 恢复）
        # 使用网关对用户查询进行意图分类，确定处理模式
        classification = await classify_intent(
            user_query,
            conversation_history=None,
            preflight=preflight,
        )
        classification = self._apply_force_mode(classification, force_mode)

        # ③ 路由：execute | clarify | fallback_v1
        # 根据意图分类和预检查结果决定具体的处理动作
        action = resolve_route_action(classification, preflight)
        if force_mode and force_mode != "auto":
            action = "execute"
        mode = self._normalize_mode(classification.mode)

        # ④ 装配 RuntimeContext（环境上下文；memory 恒 []）
        # 构建运行时上下文，为后续处理提供必要的环境信息
        ctx_mode = mode if mode in _CTX_BUILD_MODES else "smart_query"
        ctx = await build_runtime_context(
            db,
            agent_id=agent_id,
            user_query=user_query,
            thread_id=thread_id,
            mode=ctx_mode,
            run_id=run_id,
            preflight=preflight,
        )

        # ⑤ SSE：意图结论（思考区）
        # 向客户端发送意图分析结果，让用户了解系统如何理解其查询
        yield emit_think(
            ctx,
            summary=f"意图: {mode} (置信度: {classification.confidence:.0%})",
            text=classification.reasoning or "（无判断依据）",
            action="harness.gateway.intent",
        )

        # ⑥ 执行分支：澄清 / V1 降级 / 闲聊 / mode_runner（含 tools.available + Explorer）
        # 根据路由决策执行相应的处理逻辑，并流式返回处理事件
        async for event in self._dispatch_route(
            action=action,
            mode=mode,
            ctx=ctx,
            classification=classification,
            db=db,
            agent_id=agent_id,
            user_query=user_query,
            thread_id=thread_id,
            run_id=run_id,
            preflight=preflight,
        ):
            yield event

    @staticmethod
    def _apply_force_mode(
        classification: IntentClassification,
        force_mode: str | None,
    ) -> IntentClassification:
        """[阶段2] API forceMode 覆盖 Gateway 分类结果。"""
        if not force_mode or force_mode == "auto":
            return classification
        if force_mode not in _FORCE_GATEWAY_MODES:
            return classification
        return classification.model_copy(
            update={
                "mode": force_mode,
                "confidence": max(classification.confidence, 0.95),
            }
        )

    @staticmethod
    def _normalize_mode(mode: str) -> str:
        """[阶段2] 兜底非法 mode 字符串。"""
        if mode in (
            "smart_query",
            "deep_research",
            "report",
            "chitchat",
            "clarification",
            "file_analysis",
        ):
            return mode
        return "smart_query"

    async def _dispatch_route(
        self,
        *,
        action: str,
        mode: str,
        ctx: RuntimeContext,
        classification: IntentClassification,
        db: AsyncSession,
        agent_id: int,
        user_query: str,
        thread_id: str,
        run_id: str,
        preflight: PreflightSnapshot,
    ) -> AsyncIterator[HarnessSSEEvent]:
        """[阶段2] 按路由动作分发；执行链 SSE 由 mode_runner/explorer 逐条发出。"""
        if action == "clarify":
            yield emit_think(ctx, summary="路由: 请求澄清", action="harness.gateway.route")
            clarify_ctx = await build_runtime_context(
                db,
                agent_id=agent_id,
                user_query=user_query,
                thread_id=thread_id,
                mode="clarification",
                run_id=run_id,
                preflight=preflight,
            )
            reason = classification.reasoning or "请补充更多信息"
            async for ev in stream_clarification(clarify_ctx, reason):
                yield ev
            return

        if action == "fallback_v1":
            yield emit_think(ctx, summary="路由: 降级 V1", action="harness.gateway.route")
            from app.api.streaming_graph_controller import stream_workflow_execution

            async for frame in stream_workflow_execution(
                agent_id=agent_id,
                user_query=user_query,
                db=db,
                thread_id=thread_id,
            ):
                yield frame  # type: ignore[misc]
            return

        yield emit_think(
            ctx,
            summary=f"路由: 执行 {mode}",
            action="harness.gateway.route",
        )

        if mode == "chitchat":
            async for ev in stream_chitchat(ctx):
                yield ev
            return

        if getattr(settings, "harness_v2_delegate_execute", False):
            logger.warning(
                "[阶段2][Coordinator] harness_v2_delegate_execute 已弃用，"
                "请改用 harness_v2_use_legacy_agent_runtime 或关闭该开关"
            )

        async for ev in run_mode(ctx, db, mode=mode):
            yield ev
