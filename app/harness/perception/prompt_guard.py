# [阶段1] Case1 提示词注入规则扫描（不调 LLM）
# [Harness: Sandbox #5] 用户输入安全扫描，基于正则白名单/黑名单，零 LLM 开销。
#
# 检测类型（_BLOCK_PATTERNS）:
#   ① 提示词注入: "忽略上述指令" / "ignore previous instructions" 等经典越狱
#   ② System Prompt 泄露: "输出系统提示" / "reveal system prompt"
#   ③ 命令注入: os.system / subprocess / rm -rf / eval() 等危险调用
# 命中任意模式 → risk_level=block，Preflight 直接阻断，不进入 LLM 管线
#
# 额外检查: 输入长度 > harness_max_query_chars → INPUT_TOO_LONG 阻断
#   (防止 token 炸弹攻击，默认 16000 字符)

from __future__ import annotations

import logging
import re

from app.core.config import settings
from app.harness.types.preflight import PromptGuardResult

logger = logging.getLogger(__name__)

# [阶段1] 危险模式（中英），命中即 block
_BLOCK_PATTERNS: list[tuple[str, str]] = [
    (r"忽略(以上|先前|之前|上面)(的)?(所有)?(指令|规则|提示)", "PROMPT_INJECTION"),
    (r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|rules?|prompts?)", "PROMPT_INJECTION"),
    (r"(泄露|输出|打印|显示).{0,8}(system\s*prompt|系统提示)", "PROMPT_INJECTION"),
    (r"(reveal|print|show|dump).{0,12}(system\s*prompt)", "PROMPT_INJECTION"),
    (r"\b(os\.system|subprocess\.|rm\s+-rf|eval\s*\()", "PROMPT_INJECTION"),
]


def _max_query_len() -> int:
    """[阶段2] 用户输入字符上限（可配置）。"""
    return int(getattr(settings, "harness_max_query_chars", 16_000))


def scan_prompt(text: str) -> PromptGuardResult:
    """[阶段1] 扫描用户输入，返回风险等级与错误码。"""
    raw = (text or "").strip()
    if not raw:
        return PromptGuardResult(risk_level="ok")

    max_len = _max_query_len()
    actual = len(raw)
    if actual > max_len:
        logger.warning(
            "[阶段2][PromptGuard] INPUT_TOO_LONG actual=%s max=%s",
            actual,
            max_len,
        )
        return PromptGuardResult(
            risk_level="block",
            code="INPUT_TOO_LONG",
            message="输入过长",
        )

    lowered = raw.lower()
    for pattern, code in _BLOCK_PATTERNS:
        if re.search(pattern, raw, re.IGNORECASE) or re.search(pattern, lowered):
            return PromptGuardResult(
                risk_level="block",
                code=code,
                message="检测到不安全输入",
            )

    return PromptGuardResult(risk_level="ok")
