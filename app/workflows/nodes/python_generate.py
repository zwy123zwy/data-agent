"""
Python 代码生成节点（Python Generate Node） — 对齐 Java PythonGenerateNode
增强 Prompt: Schema + 样本数据 + Plan 描述 + 内存/超时约束 + 重试反馈
"""
from typing import Dict, Any
from ..state import WorkflowState, get_canonical_query, get_current_instruction
from ...core.llm import get_llm_client
from ...core.config import settings
import logging
import re

logger = logging.getLogger(__name__)

PYTHON_GENERATION_SYSTEM_PROMPT = """你是一个 Python 数据分析专家。
根据 SQL 查询结果，生成安全、高效的 Python 数据分析代码。

要求:
1. 使用 pandas 处理数据 (pd.DataFrame(sql_result))
2. 使用 matplotlib 生成图表，设置中文字体
3. 代码要简洁、高效、包含必要的注释
4. 图表保存为文件（使用 plt.savefig），文件名使用英文
5. 输出关键统计信息（使用 print），避免打印过长数据
6. 禁止访问网络、文件系统（除图表保存）、系统命令
7. 禁止使用 eval/exec/compile/__import__/open（除 plt.savefig）

内存和超时约束:
- 内存限制: {limit_memory}
- 超时限制: {code_timeout} 秒

可用的库:
- pandas, numpy, matplotlib.pyplot
- json, datetime, collections, math, statistics

输入数据说明:
- sql_result: list[dict] — 数据库查询结果
- 可通过 pd.DataFrame(sql_result) 转换为 DataFrame

只返回 Python 代码，不要有任何解释或 markdown 包裹。
"""

PYTHON_RETRY_PROMPT = """上次生成的代码执行失败，请根据错误信息修正。

上次代码:
```python
{last_code}
```

错误信息:
{error_info}

当前步骤需求: {instruction}

请修正上述问题，重新生成正确的 Python 代码。只返回代码，不要解释。
"""


def _clean_code(text: str) -> str:
    """清理 Python 代码"""
    text = text.strip()
    text = re.sub(r'^```python\s*', '', text)
    text = re.sub(r'^```\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


def _get_sample_data(state: WorkflowState, max_rows: int = 5) -> str:
    """获取 SQL 结果的前几条样本数据"""
    sql_result = state.get("sql_result")
    if not sql_result:
        return "无"
    sample = sql_result[:max_rows]
    return str(sample)


async def python_generate_node(state: WorkflowState) -> Dict[str, Any]:
    """Python 代码生成节点 — 对齐 Java PythonGenerateNode.apply()

    首次生成: Schema + 样本数据(前5条) + Plan 描述 + 内存/超时约束
    重试生成: 上次代码 + 错误信息 + instruction
    """
    instruction = get_current_instruction(state)
    user_query = get_canonical_query(state)
    schema = state.get("schema", "")

    # 判断是否为重试
    last_code = state.get("python_code")
    last_error = state.get("python_error")
    tries_count = state.get("python_tries_count", 0)
    is_retry = last_code and last_error and tries_count > 0

    llm = get_llm_client()

    if is_retry:
        # === 重试模式 ===
        logger.info(f"[PythonGenerate] Retry {tries_count}/{settings.code_executor.python_max_tries_count}")

        retry_prompt = PYTHON_RETRY_PROMPT.format(
            last_code=last_code,
            error_info=last_error,
            instruction=instruction,
        )

        try:
            response = await llm.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": PYTHON_GENERATION_SYSTEM_PROMPT.format(
                        limit_memory=settings.code_executor.limit_memory,
                        code_timeout=settings.code_executor.code_timeout,
                    )},
                    {"role": "user", "content": retry_prompt},
                ],
                temperature=0.0,
            )
            code = _clean_code(response.choices[0].message.content.strip())
            logger.info(f"[PythonGenerate] Retry code: {len(code)} chars")
            return {"python_code": code, "python_error": None}
        except Exception as e:
            logger.error(f"[PythonGenerate] Retry error: {e}")
            return {"python_error": str(e)}

    else:
        # === 首次生成模式 ===
        sql_result = state.get("sql_result")
        if not sql_result:
            logger.warning("[PythonGenerate] No SQL result available for code generation")
            return {"python_code": None, "python_error": "No SQL result available"}

        sample_data = _get_sample_data(state)
        logger.info(f"[PythonGenerate] First generation for {len(sql_result)} records, instruction: {instruction[:80]}")

        # 汇总所有 SQL 步骤结果供代码参考
        sql_memory = state.get("sql_result_list_memory") or []
        memory_desc = ""
        if len(sql_memory) > 1:
            memory_desc = f"\n历史 SQL 步骤结果:\n"
            for entry in sql_memory[:-1]:
                memory_desc += (
                    f"  - Step {entry.get('step')}: "
                    f"{entry.get('row_count', 0)} rows, "
                    f"SQL: {entry.get('sql', '')[:100]}\n"
                )

        prompt = (
            f"数据库 Schema:\n{schema}\n\n"
            f"用户问题: {user_query}\n\n"
            f"当前步骤需求: {instruction}\n\n"
            f"SQL 查询结果样本（前5条）:\n{sample_data}\n\n"
            f"总记录数: {len(sql_result)}\n"
            f"{memory_desc}"
            f"请生成 Python 数据分析代码。"
        )

        try:
            response = await llm.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": PYTHON_GENERATION_SYSTEM_PROMPT.format(
                        limit_memory=settings.code_executor.limit_memory,
                        code_timeout=settings.code_executor.code_timeout,
                    )},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
            )
            code = _clean_code(response.choices[0].message.content.strip())
            logger.info(f"[PythonGenerate] Generated {len(code)} chars of code")
            return {"python_code": code}
        except Exception as e:
            logger.error(f"[PythonGenerate] Error: {e}")
            return {"python_code": None, "error": f"Python code generation failed: {str(e)}"}
