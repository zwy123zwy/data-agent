# [阶段2] Explorer 编排策略单测（M2.5）

from app.harness.agents.explorer_policy import (
    apply_preflight_degrade,
    is_fatal_tool_error,
)
from app.harness.tools.base import ToolResult


def test_fatal_error_when_severity_fatal():
    r = ToolResult(
        status="error",
        tool_name="execute_sql",
        summary="无数据源",
        error_severity="fatal",
    )
    assert is_fatal_tool_error(r) is True


def test_fatal_error_when_severity_missing():
    r = ToolResult(status="error", tool_name="x", summary="err", error_severity=None)
    assert is_fatal_tool_error(r) is True


def test_not_fatal_when_retryable():
    r = ToolResult(
        status="error",
        tool_name="search_knowledge",
        summary="临时失败",
        error_severity="retryable",
    )
    assert is_fatal_tool_error(r) is False


def test_ok_not_fatal():
    r = ToolResult(status="ok", tool_name="x", summary="ok")
    assert is_fatal_tool_error(r) is False


def test_degrade_search_knowledge_only():
    state: dict = {}
    assert apply_preflight_degrade("search_knowledge", state) is True
    assert state["recalled_knowledge"] == "无"
    assert apply_preflight_degrade("inspect_schema", state) is False
