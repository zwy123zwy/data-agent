# [阶段4] Gateway 意图分类：route（分流键）与 run_profile（弱标签）分离
# [Harness: Intelligent Routing #3]
#
# 设计原则：
#   mode: LLM 只输出 chitchat | agent 两档，执行分流只看这两个值。
#   run_profile: UI / 埋点弱标签（smart_query / deep_research / report），不影响工具链。
#   normalize(): 校验 LLM 输出，非法 mode 按 chitchat 兜底。
#   fallback_unparsed(): 解析失败时返回 agent 低置信，由 routing 走澄清而非误闲聊。

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# [阶段4] LLM 输出的 mode 只有两档
GatewayMode = Literal["chitchat", "agent"]

# [阶段4] 执行分流只分两档
RouteMode = Literal["chitchat", "agent"]


class IntentClassification(BaseModel):
    """[阶段4] classify_intent 返回契约：mode 分流 + run_profile 弱标签。

    Attributes:
        mode: LLM 输出的意图分类（chitchat | agent），下游 routing 据此分流。
        confidence: LLM 输出的置信度 [0.0, 1.0]。
        reasoning: LLM 输出的一句推理依据。
        run_profile: UI / 埋点弱标签，不与路由或工具选择耦合。
    """

    mode: GatewayMode = "chitchat"
    confidence: float = Field(default=0.3, ge=0.0, le=1.0)
    reasoning: str = ""
    run_profile: str = "chitchat"

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _sync_run_profile(self) -> IntentClassification:
        """[阶段4] 确保 mode 与 run_profile 一致。"""
        if self.mode == "agent" and self.run_profile == "chitchat":
            object.__setattr__(self, "run_profile", "smart_query")
        elif self.mode == "chitchat" and self.run_profile != "chitchat":
            object.__setattr__(self, "run_profile", "chitchat")
        return self

    # ---- 工厂方法 ----

    @classmethod
    def normalize(
        cls,
        *,
        mode: str,
        confidence: float,
        reasoning: str,
    ) -> IntentClassification:
        """[阶段4] 校验 LLM 输出的 mode，非法值按 chitchat 兜底。

        Args:
            mode: LLM 输出的原始 mode 字符串，只接受 chitchat 或 agent。
            confidence: LLM 输出的置信度，自动裁剪到 [0.0, 1.0]。
            reasoning: LLM 输出的推理依据。

        Returns:
            校验后的 IntentClassification。
        """
        raw = (mode or "").strip()
        conf = max(0.0, min(1.0, float(confidence)))
        reason = (reasoning or "").strip()

        if raw == "agent":
            return cls(mode="agent", confidence=conf, reasoning=reason, run_profile="smart_query")
        if raw == "chitchat":
            return cls(mode="chitchat", confidence=conf, reasoning=reason)

        # 非法 mode：按 chitchat 兜底，压低置信度
        return cls(mode="chitchat", confidence=min(conf, 0.5), reasoning=reason)

    @classmethod
    def fallback_unparsed(cls) -> IntentClassification:
        """[阶段1] LLM 输出完全无法解析时的最后兜底。

        mode=agent, confidence=0.25 → routing 在 agent 路径上判定 needs_clarification。
        """
        return cls(
            mode="agent",
            confidence=0.25,
            reasoning="无法解析 Gateway 输出",
            run_profile="smart_query",
        )

    # ---- 分流查询 ----

    def route_mode(self) -> RouteMode:
        """[阶段4] 执行分流的唯一键：chitchat 或 agent。"""
        return "chitchat" if self.mode == "chitchat" else "agent"

    def is_chitchat(self) -> bool:
        """[阶段4] 是否为闲聊。"""
        return self.mode == "chitchat"

    def is_agent_execute(self) -> bool:
        """[阶段4] 是否需要 Agent 执行。"""
        return self.mode == "agent"

    def label_for_ui(self) -> str:
        """[阶段4] 思考区展示用弱标签。"""
        return self.run_profile
