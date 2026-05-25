# [阶段1] Harness SSE action 常量：eventType 下的子类型，与 tool 名区分
#
# 约定：
#   eventType — 前端路由主键（agent.think / tool.call / …）
#   action    — 同 eventType 内的语义标签（Gateway 步骤、工具名、流种类）

from __future__ import annotations


class HarnessSseAction:
    """[阶段1] Harness 发出的 action 字符串 SSOT。"""

    GATEWAY_INTENT = "harness.gateway.intent"
    GATEWAY_ROUTE = "harness.gateway.route"
    AGENT_STARTED = "harness.agent.started"
    THINK_DEFAULT = "harness.think"
    REPLY = "harness.reply"
    CHITCHAT = "chitchat"
    CLARIFICATION = "clarification"
    ANSWER = "harness.answer"


def is_gateway_action(action: str | None) -> bool:
    """[阶段1] Gateway 路由/意图类 think 步骤（兼容 legacy gateway.* 前缀）。"""
    if not action:
        return False
    return "gateway.intent" in action or "gateway.route" in action
