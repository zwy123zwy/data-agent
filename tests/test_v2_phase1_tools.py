# [阶段1] V2 Tool 与 Registry 单元测试

import pytest
from unittest.mock import AsyncMock, patch

from app.agent_runtime.context import Permissions, RuntimeContext
from app.agent_runtime.tools.base import ToolResult
from app.agent_runtime.tools.registry import build_phase1_registry
from app.agent_runtime.tools.search_knowledge import SearchKnowledgeTool


def test_tool_result_contract():
    r = ToolResult(status="ok", tool_name="search_knowledge", summary="召回完成")
    assert r.status == "ok"


def test_phase1_registry_lists_three_tools():
    reg = build_phase1_registry()
    assert set(reg.list_names()) == {"search_knowledge", "generate_sql", "execute_sql"}


def test_search_knowledge_tool_name():
    assert SearchKnowledgeTool().name == "search_knowledge"
