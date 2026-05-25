# [阶段2] RuntimeContext 装配：信任 Preflight + 注入多轮 memory
# [Harness: Memory #4]
#
# 调用方（coordinator）已拉取过 conversation_history 时，传入该参数可避免重复查询 DB。
# 未传入时从 MultiTurnContextManager 进程内存读取（兼容旧调用路径）。

from __future__ import annotations

import logging
from collections.abc import Sequence
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.harness.types.context import HarnessMode, Message, Permissions, RuntimeContext
from app.harness.types.preflight import PreflightSnapshot
from app.services.multi_turn import get_multi_turn_manager

logger = logging.getLogger(__name__)

# 需要装配数据源的执行模式
_EXECUTE_MODES: frozenset[str] = frozenset(
    {"smart_query", "deep_research", "report", "file_analysis"}
)


def _build_memory_from_history(
    thread_id: str,
    conversation_history: Sequence[dict[str, str]] | None = None,
) -> list[Message]:
    """[阶段1] 将多轮对话历史转换为 ctx.memory（list[Message]）。

    Args:
        thread_id: 会话 ID，用于未传入 history 时从进程内存加载。
        conversation_history: 已拉取的历史消息列表；为 None 时自动从 MultiTurnContextManager 读取。

    Returns:
        Message 列表，供 RuntimeContext.memory 使用。
    """
    if conversation_history is None:
        # 兼容旧路径：coordinator 未传入时从进程内存读取
        if not thread_id:
            return []
        conversation_history = get_multi_turn_manager().get_messages_for_llm(
            thread_id,
            max_turns=settings.max_turn_history,
        )

    out: list[Message] = []
    for item in conversation_history:
        role = item.get("role", "")
        content = (item.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            out.append(Message(role=role, content=content))  # type: ignore[arg-type]
    return out


async def build_runtime_context(
    db: AsyncSession,
    *,
    agent_id: int,
    user_query: str,
    thread_id: str,
    mode: HarnessMode = "smart_query",
    run_id: str | None = None,
    preflight: PreflightSnapshot | None = None,
    conversation_history: Sequence[dict[str, str]] | None = None,
) -> RuntimeContext:
    """[阶段2] Run 开始前一次性装配 RuntimeContext（frozen）。

    Args:
        db: 异步数据库会话（当前仅用于语义校验，不再查 DB）。
        agent_id: 当前 Agent ID。
        user_query: 当前用户输入文本。
        thread_id: 会话 ID。
        mode: 执行模式（chitchat / smart_query / clarification）。
        run_id: 本次 Run 的唯一标识，未传入时自动生成。
        preflight: Preflight 阶段产出的环境快照。
        conversation_history: 多轮对话历史；coordinator 传入可避免重复查询。

    Returns:
        装配完成的 RuntimeContext（frozen=True，一次 Run 内不可变）。

    Raises:
        ValueError: preflight 存在但 agent_ok 为 False。
    """
    if preflight and not preflight.agent_ok:
        raise ValueError(f"Agent 不存在: {agent_id}")

    # [阶段2] 从 Preflight.probe 提取数据源与语义模型
    datasets = []
    semantic_model: dict[str, str] = {}
    if mode in _EXECUTE_MODES and preflight and preflight.probe:
        probe = preflight.probe
        datasets = list(probe.datasets)
        if probe.semantic_prompt:
            semantic_model = {"prompt": probe.semantic_prompt}

    # [阶段2] 权限边界（默认只读）
    permissions = Permissions(
        allow_write_operations=False,
        allow_python_execution=True,
        max_sql_result_rows=10000,
    )

    ctx = RuntimeContext(
        run_id=run_id or str(uuid4()),
        thread_id=thread_id,
        agent_id=agent_id,
        user_query=user_query,
        mode=mode,
        datasets=datasets,
        semantic_model=semantic_model,
        business_knowledge=[],
        permissions=permissions,
        memory=_build_memory_from_history(thread_id, conversation_history),
    )
    logger.info(
        "[阶段2][Context] run_id=%s datasets=%d mode=%s memory_msgs=%d",
        ctx.run_id,
        len(datasets),
        mode,
        len(ctx.memory),
    )
    return ctx
