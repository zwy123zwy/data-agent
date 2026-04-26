"""
工作流节点：SQL 生成
"""
import re
from ..state import WorkflowState
from ...core.llm import llm_service


SQL_GENERATION_SYSTEM_PROMPT = """你是一个 SQL 专家。
根据用户的问题和数据库表结构，生成准确的 SQL 查询语句。

要求：
1. 只返回 SQL 语句，不要有任何解释
2. SQL 语句要准确、高效
3. 使用标准 SQL 语法
4. 不要使用 LIMIT 子句（除非用户明确要求）
5. 表名和字段名使用反引号包裹（MySQL）或不加引号（SQLite）

示例：
用户问题：查询所有用户
表结构：users (id, name, email)
SQL：SELECT * FROM users
"""


async def sql_generate_node(state: WorkflowState) -> WorkflowState:
    """
    SQL 生成节点

    使用 LLM 根据用户问题和数据库 schema 生成 SQL
    """
    # 优先使用改写后的查询，如果没有则使用原始查询
    user_query = state.get("rewritten_query") or state["user_query"]
    schema = state.get("schema", "")  # 使用文本格式的 DDL
    recalled_knowledge = state.get("recalled_knowledge", "")

    if not schema:
        state["error"] = "No schema information available"
        return state

    # 构建用户提示，包含知识库信息
    user_prompt = f"{schema}\n\n"

    if recalled_knowledge:
        user_prompt += f"{recalled_knowledge}\n\n"

    user_prompt += f"用户问题：{user_query}\n\n请生成 SQL 查询语句："

    try:
        sql = await llm_service.chat(SQL_GENERATION_SYSTEM_PROMPT, user_prompt)

        # 清理 SQL（移除 markdown 代码块标记）
        sql = sql.strip()
        sql = re.sub(r'^```sql\s*', '', sql)
        sql = re.sub(r'^```\s*', '', sql)
        sql = re.sub(r'\s*```$', '', sql)
        sql = sql.strip()

        state["generated_sql"] = sql
        state["sql_retry_count"] = state.get("sql_retry_count", 0)

    except Exception as e:
        state["error"] = f"SQL generation failed: {str(e)}"

    return state
