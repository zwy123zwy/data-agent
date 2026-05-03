"""
LLM 响应文本工具
处理 LLM 返回的 markdown 代码块、JSON 清理等
"""
import re
import logging

logger = logging.getLogger(__name__)


def clean_code_block(text: str, lang: str = None) -> str:
    """清理 LLM 返回的 markdown 代码块包裹

    Args:
        text: LLM 原始响应文本
        lang: 可选的语言标识 (如 "json", "sql", "python")，用于更精确匹配

    Returns:
        清理后的纯文本内容

    Examples:
        >>> clean_code_block("```sql\\nSELECT * FROM t\\n```")
        'SELECT * FROM t'

        >>> clean_code_block("```json\\n{"key": "val"}\\n```", lang="json")
        '{"key": "val"}'
    """
    text = text.strip()

    if lang:
        # 精确匹配指定语言的代码块
        text = re.sub(rf'^```{re.escape(lang)}\s*\n?', '', text, flags=re.IGNORECASE)
    else:
        # 匹配任意语言的代码块
        text = re.sub(r'^```(?:\w+)?\s*\n?', '', text)

    # 移除结尾的 ```
    text = re.sub(r'\n?\s*```\s*$', '', text)

    return text.strip()
