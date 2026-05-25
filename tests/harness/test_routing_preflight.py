# [阶段3] Harness：Preflight 澄清门控与 SSE（Gateway 已移除）

import pytest

from app.harness.planning.routing import needs_clarification_from_preflight
from app.harness.prompts.sections import format_conversation_history
from app.harness.sse.emit import emit_agent_execution_started
from app.harness.types.context import RuntimeContext
from app.harness.types.preflight import PreflightSnapshot


def test_needs_clarify_when_no_datasource():
    pre = PreflightSnapshot(agent_ok=True, has_datasource=False)
    ok, reason = needs_clarification_from_preflight(pre)
    assert ok is True
    assert reason


def test_no_clarify_when_datasource_ok():
    pre = PreflightSnapshot(agent_ok=True, has_datasource=True)
    ok, _ = needs_clarification_from_preflight(pre)
    assert ok is False


class TestFormatHistory:
    def test_assistant_truncation(self):
        long_assistant = "您好！为了更好地帮您查询，请补充以下信息：" + "A" * 200
        messages = [
            {"role": "user", "content": "帮我看下销售"},
            {"role": "assistant", "content": long_assistant},
        ]
        result = format_conversation_history(messages)
        assert "A" * 150 not in result
        assert "## 对话历史" in result

    def test_empty_messages(self):
        assert format_conversation_history([]) == ""
        assert format_conversation_history(None) == ""


def test_emit_agent_execution_started_event_type():
    ctx = RuntimeContext(
        run_id="r1", thread_id="t1", agent_id=1, user_query="q", mode="smart_query"
    )
    ev = emit_agent_execution_started(ctx, run_profile="smart_query")
    assert ev.event_type == "agent.execution.started"
    assert ev.action == "harness.agent.started"
