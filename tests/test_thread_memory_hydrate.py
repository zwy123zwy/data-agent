"""thread_id 与 DB 消息回填 MultiTurn。"""

from unittest.mock import MagicMock

from app.services.multi_turn import MultiTurnContextManager
from app.services.thread_memory import resolve_stream_thread_id


def test_resolve_stream_thread_id_prefers_thread():
    assert resolve_stream_thread_id("t-1", "s-2") == "t-1"
    assert resolve_stream_thread_id(None, "s-2") == "s-2"


def test_hydrate_from_chat_messages_pairs():
    mgr = MultiTurnContextManager()
    tid = "session-abc"
    msgs = [
        MagicMock(role="user", content="第一轮问题"),
        MagicMock(role="assistant", content="第一轮回答"),
        MagicMock(role="user", content="第二轮问题"),
        MagicMock(role="assistant", content="第二轮回答"),
    ]
    n = mgr.hydrate_from_chat_messages(tid, msgs)
    assert n == 2
    assert mgr.get_turn_count(tid) == 2
    llm = mgr.get_messages_for_llm(tid)
    assert len(llm) == 4
    assert llm[0]["role"] == "user"
    assert "第一轮" in llm[0]["content"]


def test_hydrate_skips_if_already_has_turns_memory_backend():
    from unittest.mock import patch

    mgr = MultiTurnContextManager()
    tid = "session-dup"
    mgr.add_turn(tid, "q", "a")
    with patch("app.services.multi_turn.settings") as mock_settings:
        mock_settings.multi_turn_backend = "memory"
        mock_settings.max_turn_history = 5
        n = mgr.hydrate_from_chat_messages(
            tid,
            [MagicMock(role="user", content="x"), MagicMock(role="assistant", content="y")],
        )
    assert n == 0
    assert mgr.get_turn_count(tid) == 1

