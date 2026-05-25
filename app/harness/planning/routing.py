# [阶段3] Preflight 门控：仅保留机械澄清（无 Gateway / 无 mode 分流）

from __future__ import annotations

from app.harness.types.preflight import PreflightSnapshot


def needs_clarification_from_preflight(
    preflight: PreflightSnapshot | None,
) -> tuple[bool, str | None]:
    """[阶段3] 无数据源时澄清；其余请求统一进入 Agent 执行链。"""
    if preflight and preflight.agent_ok and not preflight.has_datasource:
        return True, "需要查数但未配置可用数据源"
    return False, None
