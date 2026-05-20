# [阶段2] Explorer SQL 门控与 validate_sql 语义失败

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.agent_runtime.agents.explorer_agent import run_explorer_agent
from app.agent_runtime.context import RuntimeContext
from app.agent_runtime.tools.base import ToolResult
from app.agent_runtime.tools.wrap_v1_node import V1NodeTool


def _ctx() -> RuntimeContext:
    return RuntimeContext(
        run_id="r1",
        agent_id=1,
        thread_id="t1",
        user_query="q",
        mode="smart_query",
    )


def test_validate_sql_fails_when_semantic_not_passed():
    node = MagicMock()
    node.execute = AsyncMock(
        return_value={
            "semantic_consistency_result": False,
            "sql_regenerate_reason": "列不存在",
        }
    )
    node.format_sse = MagicMock(return_value=None)
    tool = V1NodeTool("validate_sql", node, "Explorer")

    async def _run():
        state: dict = {}
        return await tool.run(_ctx(), state, MagicMock())

    result = asyncio.run(_run())
    assert result.status == "error"


def test_explorer_skips_execute_when_generate_sql_fails():
    ctx = _ctx()

    async def _collect():
        events = []
        with patch(
            "app.agent_runtime.agents.explorer_agent.build_full_registry"
        ) as mock_reg:
            reg = MagicMock()

            async def _ok(ctx, state, db):
                return ToolResult(status="ok", tool_name="x", summary="ok")

            async def _fail(ctx, state, db):
                return ToolResult(
                    status="error",
                    tool_name="generate_sql",
                    summary="fail",
                )

            def get(name):
                t = MagicMock()
                t._timed_run = _fail if name == "generate_sql" else _ok
                return t

            reg.get.side_effect = get
            mock_reg.return_value = reg

            async for ev in run_explorer_agent(ctx, MagicMock(), {}, sql_retry=False):
                events.append(ev)
        return events

    events = asyncio.run(_collect())
    actions = [e.action for e in events if e.event_type == "tool.result"]
    assert "execute_sql" not in actions
    assert any(e.event_type == "error" for e in events)
