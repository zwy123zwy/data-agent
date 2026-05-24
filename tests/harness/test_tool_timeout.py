# [阶段2] Tool timed_run 超时（M2.5）

import asyncio

from app.harness.tools.base import BaseTool, ToolResult
from app.harness.types.context import RuntimeContext


class _SlowTool(BaseTool):
    name = "slow_tool"

    async def run(self, ctx, state, db) -> ToolResult:
        await asyncio.sleep(10)
        return ToolResult(status="ok", tool_name=self.name, summary="ok")


def test_timed_run_timeout(monkeypatch):
    monkeypatch.setattr(
        "app.harness.tools.base._tool_timeout_seconds",
        lambda: 0.05,
    )
    ctx = RuntimeContext(
        run_id="r1",
        thread_id="t1",
        agent_id=1,
        user_query="q",
        mode="smart_query",
    )
    tool = _SlowTool()

    async def _run():
        return await tool.timed_run(ctx, {}, None)  # type: ignore[arg-type]

    result = asyncio.run(_run())
    assert result.status == "error"
    assert result.error_code == "TOOL_TIMEOUT"
    assert result.error_severity == "retryable"
