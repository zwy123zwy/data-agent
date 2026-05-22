"""MultiTurnContextManager — 结构化消息供 Gateway 使用。"""

from app.agent_runtime.gateway import format_conversation_history_for_prompt
from app.services.multi_turn import MultiTurnContextManager


def test_get_messages_for_llm_empty():
    mgr = MultiTurnContextManager()
    assert mgr.get_messages_for_llm("t-new") == []


def test_get_messages_for_llm_after_turns():
    mgr = MultiTurnContextManager()
    tid = "t-1"
    mgr.add_turn(tid, "昨天销售额", "[分析完成]")
    mgr.add_turn(tid, "那今天呢", "[V2 execute smart_query]")
    msgs = mgr.get_messages_for_llm(tid, max_turns=2)
    assert len(msgs) == 4
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "昨天销售额"
    assert msgs[-1]["role"] == "assistant"


def test_format_conversation_history_for_prompt():
    history = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好，有什么可以帮您？"},
    ]
    text = format_conversation_history_for_prompt(history)
    assert "## 对话历史" in text
    assert "用户: 你好" in text
    assert "助手:" in text
    assert "## 当前用户输入" not in text
