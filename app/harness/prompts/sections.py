# [阶段1] Harness user prompt 片段拼装（Gateway / M2 等可复用）
#
# 将「对话历史」「环境摘要」「当前输入」拆成独立函数，避免各模块重复截断/格式化逻辑。

from __future__ import annotations

from collections.abc import Sequence

from app.harness.types.preflight import PreflightSnapshot

# 助理消息在历史中的最大字符数，超出截断以防止澄清套话污染上下文
_ASSISTANT_MAX_CHARS = 120
# 用户消息在历史中的最大字符数
_USER_MAX_CHARS = 500


def format_conversation_history(
    messages: Sequence[dict[str, str]] | None,
    *,
    section_title: str = "## 对话历史（仅用于理解指代关系，不作为分类依据）",
) -> str:
    """[阶段1] 多轮历史格式化为 prompt 片段，助理消息短截断防污染。"""
    if not messages:
        return ""
    lines: list[str] = []
    for msg in messages:
        role = msg.get("role", "")
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        if role == "assistant":
            content = content[:_ASSISTANT_MAX_CHARS]
        elif role == "user":
            content = content[:_USER_MAX_CHARS]
        label = "用户" if role == "user" else "助手"
        lines.append(f"{label}: {content}")
    if not lines:
        return ""
    return f"{section_title}\n" + "\n".join(lines) + "\n\n"


def format_preflight_environment(
    preflight: PreflightSnapshot | None,
    *,
    section_title: str = "## 环境摘要（仅供参考，不作为分类依据）",
) -> str:
    """[阶段1] PreflightSnapshot → LLM 可读环境摘要。"""
    if not preflight:
        return ""
    return "\n".join([section_title, *preflight.to_prompt_lines(), ""]) + "\n\n"


def build_layered_user_prompt(
    *,
    user_query: str,
    current_input_title: str = "## 当前用户输入（唯一分类依据）",
    prefix_sections: Sequence[str] | None = None,
) -> str:
    """[阶段1] 按顺序拼接非空 prompt 段 + 当前用户输入。"""
    parts: list[str] = []
    if prefix_sections:
        for section in prefix_sections:
            text = (section or "").strip()
            if text:
                parts.append(text)
    parts.append(f"{current_input_title}\n{user_query}")
    return "\n".join(parts)
