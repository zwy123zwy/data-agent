# [阶段1] 新 Gateway：在 Preflight 与 Context 之后做意图分类

from __future__ import annotations

import json
import logging
import re

from app.core.llm import llm_service
from app.harness.types.intent import IntentClassification
from app.harness.types.preflight import PreflightSnapshot

logger = logging.getLogger(__name__)

# TODO: Gateway 系统提示硬编码，应迁移到 prompts/gateway.system.md（Phase 2 未完成）
# 答：是。属 T-05 / H7 模板化，计划在 Phase 3+ 或单独 PR 迁入 prompts/；M2 未包含此项，当前硬编码可跑通分类。
_GATEWAY_SYSTEM = """你是 Data Agent 的智能路由网关。
分析用户输入，输出 JSON：{"mode": "smart_query|deep_research|report|chitchat", "confidence": 0.0-1.0, "reasoning": "一句话"}
模式说明：smart_query=查数；deep_research=深度分析；report=报告；chitchat=闲聊。
只输出 JSON，不要其它文字。"""


# TODO(H2): _format_history 当前为死代码 — coordinator 传 conversation_history=None。
# 答：对。记忆暂缓后 coordinator 固定传 None；H2 恢复后填入 conversation_history。
def _format_history(messages: list[dict] | None, *, max_messages: int = 6) -> str:
    """[阶段1] 多轮历史格式化为 prompt 片段。"""
    if not messages:
        return ""
    lines: list[str] = []
    for msg in messages[-max_messages:]:
        role = "用户" if msg.get("role") == "user" else "助手"
        content = (msg.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content[:500]}")
    if not lines:
        return ""
    return "## 对话历史\n" + "\n".join(lines) + "\n\n"


def _parse_classification(raw: str) -> IntentClassification:
    """[阶段1] 解析 LLM 输出的 JSON 分类 — 三阶段容错解析。

    解析策略（从严格到宽松，逐级降级）:
    ① 直接 JSON 解析: 去掉 ``` 围栏后尝试 json.loads，成功则 normalize 返回
    ② 正则兜底提取: LLM 有时在 JSON 前后附加解释文字，用正则捞出第一个含 mode/confidence
       的 JSON 对象再解析
    ③ 完全失败: 返回 fallback_unparsed() → mode=chitchat, confidence=0.3
       路由层会判定为 clarify，反问用户意图，避免静默误执行
    """
    raw = raw.strip()
    # 去掉 LLM 常见的 ```json ... ``` 围栏
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    # ① 直接 JSON 解析（正常路径，大部分 LLM 输出走这里）
    try:
        result = json.loads(raw)
        if all(k in result for k in ("mode", "confidence", "reasoning")):
            return IntentClassification.normalize(
                mode=str(result["mode"]),
                confidence=float(result["confidence"]),
                reasoning=str(result.get("reasoning", "")),
            )
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    # ② 正则兜底: 在混杂了额外文本的输出中提取 JSON 对象
    #    匹配模式: {"mode": "...", "confidence": ...}（含 reasoning 等其余字段）
    match = re.search(
        r'\{[^{}]*"mode"\s*:\s*"[^"]*"\s*,\s*"confidence"[^{}]*\}',
        raw,
    )
    if match:
        try:
            result = json.loads(match.group())
            if all(k in result for k in ("mode", "confidence", "reasoning")):
                return IntentClassification.normalize(
                    mode=str(result["mode"]),
                    confidence=float(result["confidence"]),
                    reasoning=str(result.get("reasoning", "")),
                )
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    # ③ 完全无法解析 → 兜底默认值
    return IntentClassification.fallback_unparsed()


def _preflight_block(preflight: PreflightSnapshot | None) -> str:
    """[阶段1] 环境摘要注入 Gateway user prompt。"""
    if not preflight:
        return ""
    lines = ["## 环境摘要（Preflight）", *preflight.to_prompt_lines(), ""]
    return "\n".join(lines)


async def classify_intent(
    user_query: str,
    *,
    conversation_history: list[dict] | None = None,
    preflight: PreflightSnapshot | None = None,
) -> IntentClassification:
    """[阶段1] LLM 意图分类；调用方须保证 preflight/context 已就绪。"""
    history_text = _format_history(conversation_history)
    env_text = _preflight_block(preflight)
    user_prompt = f"{history_text}{env_text}## 当前用户输入\n{user_query}"

    raw = await llm_service.chat(
        system_prompt=_GATEWAY_SYSTEM,
        user_prompt=user_prompt,
        temperature=0.0,
    )
    result = _parse_classification(raw)
    logger.info(
        "[阶段1][HarnessGateway] mode=%s confidence=%.2f",
        result.mode,
        result.confidence,
    )
    return result
