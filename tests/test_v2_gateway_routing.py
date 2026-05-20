"""Gateway 路由：闲聊低置信度也应执行，避免误走澄清。"""

from app.agent_runtime.gateway import get_route_action


def test_chitchat_low_confidence_executes():
    action = get_route_action({"mode": "chitchat", "confidence": 0.3})
    assert action == "execute"


def test_smart_query_mid_confidence_clarifies():
    action = get_route_action({"mode": "smart_query", "confidence": 0.5})
    assert action == "clarify"


def test_smart_query_high_confidence_executes():
    action = get_route_action({"mode": "smart_query", "confidence": 0.85})
    assert action == "execute"
