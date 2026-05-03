"""
LLM 响应文本工具 — 清洗大模型输出

【在系统中的地位】
  大模型经常返回带 markdown 代码块的响应 (如 ```sql ... ```)。
  clean_code_block() 是所有工作流节点的"后处理器"，剥离代码块标记，
  提取纯文本内容。

【模块连接】
  调用者 (几乎所有工作流节点都依赖此工具):
    - workflows/nodes/sql_generate.py       → 剥离 ```sql ... ```
    - workflows/nodes/python_generate.py    → 剥离 ```python ... ```
    - workflows/nodes/report_generator.py   → 剥离 ```json ... ```
    - workflows/nodes/planner.py            → 剥离 ```json ... ```
    - core/code_executor.py (AISimExecutor) → 剥离 ```json ... ```

  Java 对应:
    clean_code_block() ≈ code block extraction in TextUtils.java
"""
import re
import logging

logger = logging.getLogger(__name__)


def clean_code_block(text: str, lang: str = None) -> str:
    """清理 LLM 返回的 markdown 代码块包裹

    大模型输出通常为:
      ```sql
      SELECT * FROM users
      ```
    此函数提取内容: SELECT * FROM users

    Args:
        text: LLM 原始响应文本
        lang: 可选语言标识 ("json", "sql", "python")，精确匹配 ```<lang>

    Returns:
        清理后的纯文本内容
    """
    text = text.strip()

    if lang:
        text = re.sub(rf'^```{re.escape(lang)}\s*\n?', '', text, flags=re.IGNORECASE)
    else:
        text = re.sub(r'^```(?:\w+)?\s*\n?', '', text)

    text = re.sub(r'\n?\s*```\s*$', '', text)

    return text.strip()
