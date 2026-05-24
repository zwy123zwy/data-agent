# [阶段2] Explorer 编排策略：error_severity 与前置工具降级（M2.5）

from __future__ import annotations

import logging
from typing import Any

from app.harness.tools.base import ToolResult

logger = logging.getLogger(__name__)


def is_fatal_tool_error(result: ToolResult) -> bool:
    """[阶段2] 是否应立即终止 Run（fatal 或未标 retryable 的错误）。"""
    if result.status != "error":
        return False
    return result.error_severity != "retryable"


def apply_preflight_degrade(tool_name: str, state: dict[str, Any]) -> bool:
    """[阶段2] 前置工具 retryable 失败时降级 state，返回是否可继续管道。

    仅 search_knowledge 支持降级；inspect_schema 失败仍需 Schema，不可跳过。
    """
    if tool_name == "search_knowledge":
        state["recalled_knowledge"] = "无"
        logger.warning(
            "[阶段2][Explorer] search_knowledge 失败已降级为空知识，继续管道",
        )
        return True
    return False
