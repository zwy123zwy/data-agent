# [阶段1] Gateway 双路由决策（chitchat | agent）

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.harness.types.intent import IntentClassification

RouteKind = Literal["chitchat", "agent"]


class RouteDecision(BaseModel):
    """[阶段1] 对用户可见仅两档；澄清为 agent 准备子流程。"""

    kind: RouteKind
    classification: IntentClassification
    needs_clarification: bool = False
    clarify_reason: str | None = None
    use_v1_fallback: bool = False

    model_config = ConfigDict(extra="forbid")

    def route_label(self) -> str:
        """[阶段1] 思考区展示用路由文案。"""
        return "闲聊" if self.kind == "chitchat" else "数据分析 Agent"
