"""
工作流节点：简单报告生成
"""
import json
from ..state import WorkflowState
from ..core.llm import llm_service


REPORT_SYSTEM_PROMPT = """你是一个数据分析报告生成助手。
根据用户的问题、SQL 查询和查询结果，生成简洁清晰的分析报告。

要求：
1. 用自然语言描述查询结果
2. 突出关键数据和趋势
3. 简洁明了，不要冗长
4. 如果结果为空，说明没有找到相关数据
"""


async def simple_report_node(state: WorkflowState) -> WorkflowState:
    """
    简单报告生成节点

    根据查询结果生成自然语言报告
    """
    user_query = state["user_query"]
    sql = state.get("generated_sql", "")
    sql_result = state.get("sql_result", [])

    # 构建提示词
    result_str = json.dumps(sql_result, ensure_ascii=False, indent=2)

    user_prompt = f"""用户问题：{user_query}

SQL 查询：
{sql}

查询结果：
{result_str}

请生成分析报告："""

    try:
        report = await llm_service.chat(REPORT_SYSTEM_PROMPT, user_prompt)
        state["report"] = report

    except Exception as e:
        state["error"] = f"Report generation failed: {str(e)}"
        # 如果报告生成失败，返回简单的结果描述
        if sql_result:
            state["report"] = f"查询成功，共返回 {len(sql_result)} 条记录。"
        else:
            state["report"] = "查询成功，但没有找到匹配的数据。"

    return state
