"""
意图识别节点 — 对齐 Java IntentRecognitionNode

【处理流程】
  1. 从 state 读 user_query + multi_turn_context → 拼 prompt
  2. llm_service.chat() → 解析 intent + classification + confidence
  3. confidence >= 0.7 → 直接接受，写入 state
  4. confidence < 0.7  → interrupt() 暂停，等用户确认/纠正
     用户反馈喂回 LLM 重判一次，仍不确定则用人工答案

【输入】全部从 WorkflowState 读取
  user_query         — state["user_query"]，Controller 写入
  multi_turn_context — state["multi_turn_context"]，来自 MultiTurnContextManager
  intent_retry_count — state["intent_retry_count"]，重判计数 (max 1)

【输出】写入 state
  intent              — "data_analysis" | "chitchat"
  classification      — 人类可读的分类说明
  intent_confidence   — float 0.0-1.0
  intent_needs_confirm — bool，是否触发了人工确认
  intent_retry_count  — int
  intent_human_feedback — str，用户纠正反馈

【下游】
  graph.py route_after_intent() 读 intent 决定走数据分析链路还是闲聊
"""

from typing import Dict, Any
import json
import logging

from langgraph.types import interrupt

from ..state import WorkflowState
from ..node_base import WorkflowNode, SSEPayload
from ...core.llm import llm_service
from ...core.text_utils import clean_code_block

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.7   # 低于此值暂停等人工确认
MAX_RETRY = 1                # 最多用人工反馈重判 1 次

INTENT_SYSTEM_PROMPT = """你是一个意图识别助手。
你的任务是判断用户的问题是否需要查询数据库并进行数据分析。

如果用户的问题是：
- 数据查询、统计、分析、报表相关 → 返回 "data_analysis"
- 闲聊、问候、感谢、无关问题 → 返回 "chitchat"

同时评估你的判断置信度 (0.0-1.0):
- 0.9-1.0: 非常确定
- 0.7-0.9: 比较确定
- 0.5-0.7: 不太确定
- 0.0-0.5: 完全不确定

返回 JSON 格式:
{
  "intent": "data_analysis" | "chitchat",
  "classification": "意图分类说明",
  "confidence": 0.85
}
"""


class IntentRecognitionNode(WorkflowNode):
    """读 state → LLM 二分类 + 置信度 → 不确定时 interrupt 等人工确认 → 写 state"""

    name = "intent_recognition"
    description = "识别用户意图（含置信度），不确定时暂停等人工确认"
    requires = ["user_query", "multi_turn_context"]
    provides = [
        "intent", "classification",
        "intent_confidence", "intent_needs_confirm",
        "intent_retry_count", "intent_human_feedback",
    ]
    applicable_data_sources = ["*"]

    # ── LLM 调用 + 解析 ──

    async def _call_llm(self, user_prompt: str) -> Dict[str, Any]:
        """调 LLM 做意图分类，返回 {intent, classification, confidence}"""
        llm_output = await llm_service.chat(INTENT_SYSTEM_PROMPT, user_prompt)
        llm_output = llm_output.strip()

        try:
            text = clean_code_block(llm_output, lang="json")
            data = json.loads(text)
            intent = data.get("intent", "").strip().lower()
            classification = data.get("classification", "")
            confidence = float(data.get("confidence", 0.5))
        except (json.JSONDecodeError, ValueError, Exception):
            intent = llm_output.lower()
            classification = ""
            confidence = 0.5

        # 白名单校验
        if intent not in ("data_analysis", "chitchat"):
            intent = "chitchat"
            confidence = 0.3

        # 补全 classification
        if not classification:
            classification = (
                "可能的数据分析请求" if intent == "data_analysis" else "闲聊或无关指令"
            )

        return {"intent": intent, "classification": classification, "confidence": confidence}

    # ── 构建 prompt ──

    def _build_prompt(
        self, user_query: str, multi_turn: str,
        previous_feedback: str = "", previous_intent: str = "",
    ) -> str:
        """拼接 LLM 输入 prompt

        - 有历史反馈 → 重判模式：原始问题 + 上次判断 + 用户纠正
        - 有多轮上下文 → 首轮模式：历史对话 + 当前问题
        - 都没有 → 纯首轮
        """
        if previous_feedback:
            return (
                f"用户问题: {user_query}\n\n"
                f"你上次判断为「{previous_intent}」，但用户反馈: {previous_feedback}\n"
                f"请根据用户反馈重新判断意图，并给出新的置信度。"
            )
        if multi_turn:
            return f"多轮对话上下文:\n{multi_turn}\n\n当前用户问题: {user_query}"
        return f"用户问题: {user_query}"

    # ── 主执行 ──

    async def execute(self, state: WorkflowState) -> Dict[str, Any]:
        user_query = state["user_query"]
        multi_turn = state.get("multi_turn_context", "")
        retry_count = state.get("intent_retry_count", 0)
        previous_feedback = state.get("intent_human_feedback", "")
        previous_intent = state.get("intent", "")

        user_prompt = self._build_prompt(
            user_query, multi_turn, previous_feedback, previous_intent
        )

        logger.info(
            f"[IntentRecognition] query={user_query[:80]}, "
            f"retry={retry_count}, has_feedback={bool(previous_feedback)}"
        )

        try:
            result = await self._call_llm(user_prompt)
        except Exception as e:
            logger.error(f"[IntentRecognition] LLM failed: {e}")
            return {
                "intent": "chitchat",
                "classification": "闲聊或无关指令",
                "intent_confidence": 0.0,
                "error": f"LLM 意图识别失败: {str(e)}",
            }

        intent = result["intent"]
        classification = result["classification"]
        confidence = result["confidence"]

        logger.info(
            f"[IntentRecognition] intent={intent}, confidence={confidence:.2f}, "
            f"threshold={CONFIDENCE_THRESHOLD}"
        )

        # ── 置信度足够 或 已达最大重试次数 → 直接接受 ──
        if confidence >= CONFIDENCE_THRESHOLD or retry_count >= MAX_RETRY:
            if retry_count >= MAX_RETRY and confidence < CONFIDENCE_THRESHOLD:
                logger.warning(
                    f"[IntentRecognition] Max retry ({MAX_RETRY}) reached, "
                    f"accepting intent={intent} despite low confidence={confidence:.2f}"
                )
            return {
                "intent": intent,
                "classification": classification,
                "intent_confidence": confidence,
                "intent_needs_confirm": False,
            }

        # ── 置信度不足 → interrupt 暂停，等人工确认 ──
        logger.info(f"[IntentRecognition] Low confidence ({confidence:.2f}), pausing for human confirm")

        feedback = interrupt({
            "type": "intent_confirm",
            "message": (
                f"我判断你的意图可能是「{classification}」，"
                f"但不太确定（置信度 {confidence:.0%}）。请确认或纠正。"
            ),
            "guessed_intent": intent,
            "confidence": confidence,
            "classification": classification,
        })

        # 用户反馈 → 记录，下次 execute 重判时用
        user_feedback = ""
        if isinstance(feedback, dict):
            user_feedback = feedback.get("reason", "") or json.dumps(feedback, ensure_ascii=False)
        elif isinstance(feedback, str):
            user_feedback = feedback

        logger.info(f"[IntentRecognition] Human feedback: {user_feedback[:100]}")

        return {
            "intent": intent,                         # 保留首次判断，重判时作为 previous_intent
            "classification": classification,
            "intent_confidence": confidence,
            "intent_needs_confirm": True,
            "intent_retry_count": retry_count + 1,
            "intent_human_feedback": user_feedback,
        }

    # ── SSE 输出 ──

    def format_sse(self, output: Dict[str, Any]) -> SSEPayload:
        intent = output.get("intent", "")
        confidence = output.get("intent_confidence")
        needs_confirm = output.get("intent_needs_confirm", False)

        if needs_confirm:
            text = (
                f"正在进行意图识别...\n"
                f"初步判断: {output.get('classification', '')} (置信度 {confidence:.0%})\n"
                f"等待人工确认..."
            )
        elif confidence is not None:
            text = (
                f"正在进行意图识别...\n"
                f"判断结果: {output.get('classification', '')} (置信度 {confidence:.0%})\n"
                f"意图识别完成！"
            )
        else:
            text = f"正在进行意图识别...\n意图识别完成！"

        return SSEPayload(
            text=text,
            text_type="TEXT",
            metrics_delta={"intent_classification": intent},
        )


# LangGraph 兼容实例
intent_recognition_node = IntentRecognitionNode()
