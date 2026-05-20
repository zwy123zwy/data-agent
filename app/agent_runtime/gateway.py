# [Harness: Routing #3] V2 Agent Runtime — Gateway 意图分类
#
# Gateway 是 V2 执行流程的第一个节点，负责：
#   1. 用 LLM 对用户输入做意图分类（smart_query | deep_research | report | chitchat）
#   2. 返回置信度分数，决定路由策略：
#      - conf ≥ 0.7 → 直接执行 V2 流程
#      - 0.3 ≤ conf < 0.7 → 请求用户澄清
#      - conf < 0.3 → 降级到 V1
#
# 本模块是 V2 Agent Runtime 的一部分。参考 CLAUDE.md 了解 Harness Engineering 理念。
#
# DO NOT:
#   - Import from app/api/（跨层调用禁止）
#   - Hardcode prompt templates（走 prompt_config service）

import json
import logging
import re

from ..core.llm import llm_service

logger = logging.getLogger(__name__)

# ── Gateway 意图分类 prompt ──
# TODO: 后续迁移到 prompt_config service，当前先用内联 prompt 跑通流程
GATEWAY_SYSTEM_PROMPT = """你是 Data Agent 的智能路由网关（Gateway）。
你的任务是分析用户的输入，判断用户意图并给出置信度。

## 意图类型
- **smart_query**: 用户想查询具体数据，期望快速得到表格/图表结果
- **deep_research**: 用户想做深度数据分析，可能需要多步 SQL + Python 分析
- **report**: 用户想基于数据生成分析报告
- **chitchat**: 闲聊、打招呼、问系统能力等非数据查询

## 置信度规则
- 0.9-1.0: 输入非常明确，无歧义（如 "查询昨天的订单总数" → smart_query/0.95）
- 0.7-0.9: 意图基本清晰，但可能有边界模糊（如 "分析一下销售情况" → deep_research/0.8）
- 0.3-0.7: 输入模糊，需要用户补充信息（如 "帮我看看数据" → clarification 需求）
- <0.3: 无法理解或不在能力范围内

## 输出格式（严格 JSON，不要输出其他内容）
{"mode": "smart_query|deep_research|report|chitchat", "confidence": 0.0-1.0, "reasoning": "一句话说明判断依据"}
"""


def _parse_classification(raw: str) -> dict:
    """从 LLM 原始输出中提取 JSON 分类结果。

    容错策略：
    1. 先尝试直接解析整个字符串
    2. 失败则用正则提取第一个 JSON 对象
    3. 仍失败则返回默认值（chitchat / 0.3）
    """
    raw = raw.strip()
    # 去掉可能的 markdown 代码块包裹
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        result = json.loads(raw)
        if all(k in result for k in ("mode", "confidence", "reasoning")):
            return result
    except json.JSONDecodeError:
        pass

    # 正则兜底：匹配第一个 JSON 对象
    match = re.search(r'\{[^{}]*"mode"\s*:\s*"[^"]*"\s*,\s*"confidence"[^{}]*\}', raw)
    if match:
        try:
            result = json.loads(match.group())
            if all(k in result for k in ("mode", "confidence", "reasoning")):
                return result
        except json.JSONDecodeError:
            pass

    logger.warning("[Gateway] 无法解析 LLM 输出，使用默认分类: %s", raw[:200])
    return {"mode": "chitchat", "confidence": 0.3, "reasoning": "无法解析 LLM 输出，降级为默认分类"}


async def classify_intent(
    user_query: str,
    conversation_history: list[dict] | None = None,
) -> dict:
    """Gateway 意图分类（裸函数，返回 plain dict）。

    [Harness: Routing #3] 这是 V2 执行流程的第一个函数。
    用 LLM 对用户输入做意图分类，返回 mode + confidence + reasoning。

    Args:
        user_query: 用户原始输入
        conversation_history: 可选，近期对话消息 [{"role": "user/assistant", "content": "..."}]

    Returns:
        {"mode": "smart_query|deep_research|report|chitchat",
         "confidence": 0.0-1.0,
         "reasoning": "判断依据"}
    """
    # 构建 user prompt：拼接对话历史 + 当前输入
    history_text = ""
    if conversation_history:
        lines = []
        for msg in conversation_history[-6:]:  # 最近 3 轮对话
            role = "用户" if msg.get("role") == "user" else "助手"
            content = msg.get("content", "")
            if content:
                lines.append(f"{role}: {content[:200]}")
        if lines:
            history_text = "## 对话历史\n" + "\n".join(lines) + "\n\n"

    user_prompt = f"{history_text}## 当前用户输入\n{user_query}"

    logger.info("[Gateway] 开始意图分类, query=%s", user_query[:100])

    raw = await llm_service.chat(
        system_prompt=GATEWAY_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.0,  # 分类任务用低温，保证稳定性
    )

    result = _parse_classification(raw)

    # 校验 mode 合法性
    valid_modes = {"smart_query", "deep_research", "report", "chitchat"}
    if result.get("mode") not in valid_modes:
        result["mode"] = "chitchat"
        result["confidence"] = min(result.get("confidence", 0.3), 0.5)

    # 钳制 confidence 到 [0, 1]
    result["confidence"] = max(0.0, min(1.0, float(result.get("confidence", 0.5))))

    logger.info(
        "[Gateway] 分类完成: mode=%s confidence=%.2f reasoning=%s",
        result["mode"], result["confidence"], result.get("reasoning", ""),
    )
    return result


def get_route_action(classification: dict) -> str:
    """根据分类结果决定路由动作（纯函数，不涉及 I/O）。

    Args:
        classification: classify_intent() 返回的 dict

    Returns:
        "execute": 置信度足够，直接执行 V2
        "clarify": 需要用户补充信息
        "fallback_v1": 降级到 V1 流程
    """
    mode = classification.get("mode", "")
    confidence = float(classification.get("confidence", 0.0))
    # 闲聊、报告类问候不阻塞澄清，低置信度也直接执行
    if mode in ("chitchat",):
        return "execute"
    if confidence >= 0.7:
        return "execute"
    elif confidence >= 0.3:
        return "clarify"
    else:
        return "fallback_v1"
