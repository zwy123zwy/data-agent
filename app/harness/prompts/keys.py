# [阶段1] Harness 系统提示词 Key 登记（与 prompts/harness/{key}.system.md 对应）

from __future__ import annotations

from enum import StrEnum


class HarnessPromptKey(StrEnum):
    """[阶段1] 稳定 Prompt 标识；DB prompt_type = harness-{value}。"""

    CHITCHAT = "chitchat"
    CLARIFY = "clarify"
    TOOL_PICKER = "tool_picker"
    GENERATE_SQL = "generate_sql"
    ANSWER = "answer"
    SEARCH_KNOWLEDGE_REWRITE = "search_knowledge_rewrite"


def db_prompt_type(key: HarnessPromptKey | str) -> str:
    """[阶段1] user_prompt_config.prompt_type 字段值。"""
    name = key.value if isinstance(key, HarnessPromptKey) else str(key)
    return f"harness-{name.replace('_', '-')}"
