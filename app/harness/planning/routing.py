# [阶段1] Gateway 路由决策（纯函数，阈值与机械约束）
# [Harness: Intelligent Routing #3] 根据意图分类置信度 + Preflight 环境状态，决定执行路径。

from __future__ import annotations

from app.harness.types.intent import IntentClassification
from app.harness.types.preflight import PreflightSnapshot


# TODO(H2): 路由决策当前只看 Preflight 的数据源/文件状态 + 分类置信度。
# 答：Phase 1/2 设计如此；H2 可选读 memory 元数据增强。
def resolve_route_action(
    classification: IntentClassification,
    preflight: PreflightSnapshot | None = None,
) -> str:
    """[阶段1] 根据分类结果与 Preflight 决定 execute / clarify / fallback_v1。

    路由决策树（按优先级）:
    1. 数据源/文件缺失 → clarify（即使 LLM 高置信度也要先补齐前置条件）
       - smart_query / deep_research / report 但没有数据源 → clarify
       - file_analysis 但没有文件 → clarify
    2. chitchat → 直接 execute（闲聊不需要数据源）
    3. confidence ≥ 0.7 → execute（LLM 高置信度，直接执行）
    4. 0.3 ≤ confidence < 0.7 → clarify（LLM 不确定，反问用户）
    5. confidence < 0.3 → fallback_v1（LLM 基本瞎猜，降级到 V1 全管线保底）

    阈值设计依据:
    - 0.7: 经验阈值，GPT-4 级别模型在此之上极少误分类
    - 0.3: chatitchat 默认置信度，低于此值说明 LLM 输出几乎无意义
    """
    mode = classification.mode
    confidence = classification.confidence

    # 前置条件检查: 需要的资源是否存在
    if preflight and preflight.agent_ok:
        if not preflight.has_datasource and mode in ("smart_query", "deep_research", "report"):
            return "clarify"
        if mode == "file_analysis" and not preflight.has_files:
            return "clarify"

    # 置信度路由
    if mode == "chitchat":
        return "execute"
    if confidence >= 0.7:
        return "execute"
    if confidence >= 0.3:
        return "clarify"
    return "fallback_v1"
