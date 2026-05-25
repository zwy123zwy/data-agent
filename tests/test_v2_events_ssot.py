"""events.py 为 eventType SSOT，须包含 text.delta 且可实例化。"""

from app.agent_runtime.events import AGENT_EVENT_TYPES, AgentEventType, AgentSSEEvent


def test_agent_event_types_include_text_delta():
    assert "text.delta" in AGENT_EVENT_TYPES


def test_create_text_delta_event():
    ev = AgentSSEEvent.create_v2_only(
        run_id="run-1",
        event_type="text.delta",
        agent_id=1,
        thread_id="thread-1",
        agent_name="Explorer",
        text="你",
        text_type="TEXT",
        action="chitchat",
    )
    assert ev.event_type == "text.delta"
    assert ev.text == "你"


def test_agent_event_type_literal_matches_frontend():
    # 与 data-agent-fronted src/types/graph.ts AgentEventType 保持一致
    expected: set[AgentEventType] = {
        "agent.think",
        "agent.execution.started",
        "tool.call",
        "tool.result",
        "tools.available",
        "text.delta",
        "agent.complete",
        "clarification.requested",
        "run.complete",
        "error",
    }
    assert set(AGENT_EVENT_TYPES) == expected


def test_harness_event_types_include_agent_execution_started():
    from app.harness.types.events import HARNESS_EVENT_TYPES

    assert "agent.execution.started" in HARNESS_EVENT_TYPES
