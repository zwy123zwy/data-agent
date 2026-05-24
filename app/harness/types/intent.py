# [阶段1] Gateway 意图分类结果（替代裸 dict）
# [Harness: Intelligent Routing #3] IntentClassification 是 Gateway 路由决策的核心数据契约，
#   替代 V1 中裸 dict 传递分类结果，提供类型安全 + 边界校验 + 错误恢复。

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# [阶段1] LLM Gateway 可输出的 mode 枚举。
# 注意: clarification 不在此枚举中 — 它不是 LLM 分类结果，而是 routing.py 根据置信度
#   (0.3 ≤ conf < 0.7) 推导出的路由动作。file_analysis 预留给 Phase 3 文件上传场景。
GatewayMode = Literal[
    "smart_query",     # 查数：单表查询、简单聚合
    "deep_research",   # 深度分析：多表关联、趋势分析
    "report",          # 报告：需要多 Agent 协作输出完整分析报告
    "chitchat",        # 闲聊：非数据分析问题
    "file_analysis",   # 文件分析（Phase 3 启用）
]

# 合法 mode 集合，供 normalize() 验证和路由决策使用
_GATEWAY_MODES: frozenset[str] = frozenset(
    {"smart_query", "deep_research", "report", "chitchat", "file_analysis"}
)


class IntentClassification(BaseModel):
    """[阶段1] classify_intent 返回契约 — Gateway 分类结果的唯一数据模型。

    设计决策:
    - extra="forbid": 防止 LLM 输出多余字段污染路由决策
    - 默认 mode="chitchat" + confidence=0.3: 最安全的降级默认值（会触发 clarify）
    """

    mode: GatewayMode = "chitchat"
    confidence: float = Field(default=0.3, ge=0.0, le=1.0)
    reasoning: str = ""

    model_config = ConfigDict(extra="forbid")

    @classmethod
    def normalize(cls, *, mode: str, confidence: float, reasoning: str) -> IntentClassification:
        """[阶段1] 校验 mode 与 confidence 边界，防止 LLM 输出非法值。

        关键行为:
        - mode 不在 _GATEWAY_MODES 中时 → 降级为 chitchat，置信度上限 0.5
          （防止 LLM 幻觉出不存在 mode 的同时还给出高置信度，跳过澄清直接执行）
        - confidence 硬钳位到 [0, 1]，防止 LLM 输出负数或 >1 的异常值
        """
        m: GatewayMode = mode if mode in _GATEWAY_MODES else "chitchat"  # type: ignore[assignment]
        conf = max(0.0, min(1.0, float(confidence)))
        if m != mode:
            # 非法 mode → 置信度上限 0.5，确保 routing 走 clarify 而非直接 execute
            conf = min(conf, 0.5)
        return cls(mode=m, confidence=conf, reasoning=(reasoning or "").strip())

    @classmethod
    def fallback_unparsed(cls) -> IntentClassification:
        """[阶段1] LLM 输出完全无法解析时的兜底默认值。

        mode=chitchat + confidence=0.3 → routing 判定为 clarify，
        系统会反问用户「请问您想做什么？」，而非静默执行错误模式。
        """
        return cls(mode="chitchat", confidence=0.3, reasoning="无法解析分类结果")