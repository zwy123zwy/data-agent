# [阶段1] Preflight：机械校验 Agent/数据源/注入，产出 PreflightSnapshot
# [Harness: Sandbox #5 + Intelligent Routing #3]
#
# Preflight 是 PPAF 管线的第一环，执行顺序:
#   ① scan_prompt(user_query): 提示词注入扫描（正则，不调 LLM）
#   ② Agent 存在性检查: 不存在 → blocked=True, 返回 AGENT_NOT_FOUND
#   ③ 注入阻断检查: 命中 → blocked=True, 返回 PROMPT_INJECTION
#   ④ run_datasource_probe: 数据源探测 + 语义模型采样
#   ⑤ 组装 PreflightSnapshot: 汇总 ①~④ 的所有结果
#
# 灰度开关: harness_v2_preflight_enabled=False 时返回空快照（agent_ok=True），
#   跳过所有校验，用于紧急回滚。

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.harness.perception.datasource_probe import run_datasource_probe
from app.harness.perception.prompt_guard import scan_prompt
from app.harness.types.preflight import PreflightSnapshot
from app.services.agent_service import AgentService

logger = logging.getLogger(__name__)


def _empty_pass(agent_id: int) -> PreflightSnapshot:
    """[阶段1] 开关关闭时返回通过快照（便于灰度回滚）。"""
    return PreflightSnapshot(agent_ok=True, agent_id=agent_id)


async def run_preflight(
    db: AsyncSession,
    *,
    agent_id: int,
    user_query: str,
    nl2sql_only: bool = False,
) -> PreflightSnapshot:
    """[阶段2] 执行 ② 用户校验；数据源探测一次写入快照字段。"""
    if not getattr(settings, "harness_v2_preflight_enabled", True):
        return _empty_pass(agent_id)

    guard = scan_prompt(user_query)
    agent = await AgentService.get_agent(db, agent_id)
    if not agent:
        return PreflightSnapshot(
            agent_ok=False,
            agent_id=agent_id,
            risk_level="block",
            blocked=True,
            block_code="AGENT_NOT_FOUND",
        )

    if guard.risk_level == "block":
        return PreflightSnapshot(
            agent_ok=True,
            agent_id=agent_id,
            risk_level="block",
            blocked=True,
            block_code=guard.code or "PROMPT_INJECTION",
        )

    probe = await run_datasource_probe(db, agent_id=agent_id)

    snap = PreflightSnapshot(
        agent_ok=True,
        agent_id=agent_id,
        risk_level=guard.risk_level,
        blocked=False,
        has_datasource=probe.has_datasource,
        # TODO(Phase 3+): has_files 硬编码 False，文件分析功能未实现
        # 答：Phase 3 任务 3.1–3.3。届时从会话文件域/上传表查询，routing 对 file_analysis 无文件走 clarify。
        has_files=False,
        select_tables=probe.select_tables,
        semantic_warn=probe.semantic_warn,
        nl2sql_only=nl2sql_only,
        probe=probe,
    )

    logger.info(
        "[阶段2][Preflight] agent_id=%s has_ds=%s tables=%d blocked=%s",
        agent_id,
        probe.has_datasource,
        len(probe.select_tables),
        snap.blocked,
    )
    return snap
