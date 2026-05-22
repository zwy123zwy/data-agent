"""[阶段4] DB 同步与 merge/replace 策略 — MultiTurnContextManager。"""

from unittest.mock import MagicMock, patch

from app.services.multi_turn import MultiTurnContextManager
from app.services.multi_turn_store import merge_db_and_memory_turns, pair_messages_to_turns


def test_pair_messages_to_turns():
    msgs = [
        MagicMock(role="user", content="Q1"),
        MagicMock(role="assistant", content="A1"),
        MagicMock(role="user", content="Q2"),
        MagicMock(role="assistant", content="A2"),
    ]
    pairs = pair_messages_to_turns(msgs)
    assert pairs == [("Q1", "A1"), ("Q2", "A2")]


def test_merge_db_and_memory_tail():
    db = [("Q1", "A1")]
    mem = [("Q1", "A1"), ("Q2", "[分析完成]")]
    merged = merge_db_and_memory_turns(db, mem, sync_mode="merge", max_turns=5)
    assert len(merged) == 2
    assert merged[1][0] == "Q2"


def test_replace_drops_memory_tail():
    db = [("Q1", "A1")]
    mem = [("Q1", "A1"), ("Q2", "[分析完成]")]
    merged = merge_db_and_memory_turns(db, mem, sync_mode="replace", max_turns=5)
    assert merged == [("Q1", "A1")]


def test_sync_from_db_merge_keeps_add_turn_tail():
    mgr = MultiTurnContextManager()
    tid = "sess-merge"
    # 模拟：DB 仅落库第 1 轮，内存已有 2 轮（含本轮 add_turn 未同步）
    mgr.add_turn(tid, "Q1", "mem-only A1")
    mgr.add_turn(tid, "Q2", "[V2 execute]")
    msgs = [
        MagicMock(role="user", content="Q1"),
        MagicMock(role="assistant", content="A1 from DB"),
    ]
    with patch("app.services.multi_turn.settings") as mock_settings:
        mock_settings.multi_turn_db_sync_mode = "merge"
        mock_settings.max_turn_history = 5
        n = mgr.sync_from_db_messages(tid, msgs)
    assert n == 2
    llm = mgr.get_messages_for_llm(tid)
    assert any("Q1" in m["content"] for m in llm)
    assert any("Q2" in m["content"] for m in llm)


def test_sync_from_db_replace_overwrites_memory():
    mgr = MultiTurnContextManager()
    tid = "sess-replace"
    mgr.add_turn(tid, "stale", "mem-only")
    msgs = [
        MagicMock(role="user", content="Q1"),
        MagicMock(role="assistant", content="A1"),
    ]
    with patch("app.services.multi_turn.settings") as mock_settings:
        mock_settings.multi_turn_db_sync_mode = "replace"
        mock_settings.max_turn_history = 5
        mgr.sync_from_db_messages(tid, msgs)
    assert mgr.get_turn_count(tid) == 1
    assert mgr.get_messages_for_llm(tid)[0]["content"] == "Q1"


def test_hydrate_memory_backend_skips_when_has_turns():
    mgr = MultiTurnContextManager()
    tid = "sess-mem"
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
