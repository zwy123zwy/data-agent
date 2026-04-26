"""
Python 代码生成节点（Python Generate Node）
根据 SQL 查询结果生成 Python 分析代码
"""
from typing import Dict, Any
from ..state import AgentState
from ...core.llm import get_llm_client
from ...core.config import settings
import logging
import re

logger = logging.getLogger(__name__)


PYTHON_GENERATION_SYSTEM_PROMPT = """你是一个 Python 数据分析专家。
根据 SQL 查询结果，生成 Python 数据分析代码。

要求：
1. 使用 pandas 处理数据
2. 使用 matplotlib 生成图表
3. 代码要简洁、高效
4. 包含必要的注释
5. 图表要保存为文件（使用 plt.savefig）
6. 输出关键的统计信息（使用 print）

可用的库：
- pandas
- numpy
- matplotlib.pyplot

输入数据格式：
- sql_result 变量包含 SQL 查询结果（list of dict）

示例：
```python
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# 加载数据
df = pd.DataFrame(sql_result)

# 数据分析
print(f"总记录数: {len(df)}")
print(f"平均值: {df['amount'].mean()}")

# 生成图表
plt.figure(figsize=(10, 6))
plt.plot(df['date'], df['amount'])
plt.title('趋势分析')
plt.xlabel('日期')
plt.ylabel('金额')
plt.savefig('trend.png')
plt.close()
```

只返回 Python 代码，不要有任何解释。
"""


async def python_generate_node(state: AgentState) -> Dict[str, Any]:
    """
    Python 代码生成节点

    根据 SQL 查询结果生成数据分析代码

    Args:
        state: 工作流状态

    Returns:
        更新后的状态
    """
    sql_result = state.get("sql_result")
    user_query = state.get("rewritten_query") or state["user_query"]

    if not sql_result:
        logger.warning("[PythonGenerate] No SQL result available")
        return {"python_code": None}

    logger.info(f"[PythonGenerate] Generating Python code for {len(sql_result)} records")

    try:
        llm = get_llm_client()

        # 构建提示
        user_prompt = f"""用户查询: {user_query}

SQL 查询结果（前3条）:
{sql_result[:3]}

总记录数: {len(sql_result)}

请生成 Python 代码来分析这些数据，包括：
1. 基本统计分析
2. 生成合适的可视化图表
3. 输出关键发现

注意：sql_result 变量已经包含了完整的查询结果。
"""

        response = await llm.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": PYTHON_GENERATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0
        )

        python_code = response.choices[0].message.content.strip()

        # 清理代码（移除 markdown 代码块标记）
        python_code = re.sub(r'^```python\s*', '', python_code)
        python_code = re.sub(r'^```\s*', '', python_code)
        python_code = re.sub(r'\s*```$', '', python_code)
        python_code = python_code.strip()

        logger.info(f"[PythonGenerate] Generated {len(python_code)} characters of code")

        return {"python_code": python_code}

    except Exception as e:
        logger.error(f"[PythonGenerate] Error: {e}")
        return {"python_code": None, "error": f"Python code generation failed: {str(e)}"}
