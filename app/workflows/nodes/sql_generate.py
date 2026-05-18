"""
SQL 生成节点 — 对齐 Java SqlGenerateNode

Harness 角色: Text-to-SQL 核心。根据 Schema + 用户问题 + 当前步骤指令，
调用 LLM 生成 SQL 查询。支持首次生成和基于错误/语义反馈的重试。

I/O 契约:
  requires: schema, user_query, query_plan, recalled_knowledge, db_dialect_type
  provides: generated_sql, sql_generate_count, sql_regenerate_reason
"""

from typing import Dict, Any
from ..state import WorkflowState, get_canonical_query, get_current_instruction
from ..node_base import WorkflowNode, SSEPayload
from ...core.llm import llm_service
from ...core.config import settings
from ...core.text_utils import clean_code_block
import logging

logger = logging.getLogger(__name__)

SQL_GENERATION_SYSTEM_PROMPT = """你是一个 SQL 专家。
根据用户问题、数据库 Schema 和当前步骤需求，生成准确的 SQL 查询语句。

要求:
1. 只返回 SQL 语句，不要有任何解释
2. SQL 语句要准确、高效
3. 使用标准 SQL 语法，注意数据库方言
4. 表名和字段名使用反引号包裹（MySQL）或不加引号（PostgreSQL）
5. 只生成 SELECT 语句，禁止 INSERT/UPDATE/DELETE/TRUNCATE/DROP
6. 谨慎使用 LIMIT，除非步骤需求明确指定条数
"""

SQL_RETRY_PROMPT = """上次生成的 SQL 存在问题，请根据错误信息重新生成。

上次生成的 SQL:
{last_sql}

错误类型: {error_type}
错误信息:
{error_reason}

当前步骤需求: {instruction}

请修正上述问题，重新生成正确的 SQL 语句。只返回 SQL，不要解释。
"""


def _build_retry_prompt(
    last_sql: str, error_type: str, error_reason: str, instruction: str
) -> str:
    """构建重试提示 — 对齐 Java SqlGenerateNode.handleRetryGenerateSql"""
    return SQL_RETRY_PROMPT.format(
        last_sql=last_sql,
        error_type=error_type,
        error_reason=error_reason,
        instruction=instruction,
    )


def _extract_last_sql(state: WorkflowState) -> str:
    """获取上次生成的 SQL（如果存在）"""
    results = state.get("sql_result_list_memory") or []
    if results:
        last = results[-1]
        return last.get("sql", "")
    return state.get("generated_sql", "")


class SqlGenerateNode(WorkflowNode):
    """SQL 生成 — 对齐 Java SqlGenerateNode.apply()

    Text-to-SQL 核心节点。LLM 根据数据库结构和用户问题生成 SQL。
    首次: schema + instruction + 知识证据
    重试: 上次 SQL + 错误原因 + instruction
    """

    name = "sql_generate"
    description = "将自然语言问题转为 SQL 查询语句"
    requires = ["schema", "user_query", "query_plan", "recalled_knowledge", "db_dialect_type"]
    provides = ["generated_sql", "sql_generate_count", "sql_regenerate_reason"]
    applicable_data_sources = ["database"]

    async def execute(self, state: WorkflowState) -> Dict[str, Any]:
        user_query = get_canonical_query(state)
        instruction = get_current_instruction(state)
        schema = state.get("schema", "")
        evidence = state.get("recalled_knowledge", "")
        dialect = state.get("db_dialect_type", "")

        regenerate_reason = state.get("sql_regenerate_reason")
        generate_count = state.get("sql_generate_count", 0)
        max_retry = settings.max_sql_retry_count

        if regenerate_reason:
            last_sql = _extract_last_sql(state)
            error_type = regenerate_reason.get("type", "unknown")
            error_reason = regenerate_reason.get("reason", str(regenerate_reason))

            logger.info(
                f"[SqlGenerate] Retry {generate_count}/{max_retry}, "
                f"error_type={error_type}, reason={error_reason[:80]}"
            )

            if generate_count >= max_retry:
                logger.error(f"[SqlGenerate] Max retry ({max_retry}) exceeded")
                return {
                    "sql_generate_count": generate_count + 1,
                    "error": f"SQL 生成失败，已重试 {max_retry} 次，最后错误: {error_reason}",
                }

            retry_prompt = _build_retry_prompt(last_sql, error_type, error_reason, instruction)
            try:
                sql = await llm_service.chat(SQL_GENERATION_SYSTEM_PROMPT, retry_prompt, temperature=0.0)
                sql = clean_code_block(sql, lang="sql")
                logger.info(f"[SqlGenerate] Retry SQL: {sql[:100]}...")
                return {
                    "generated_sql": sql,
                    "sql_generate_count": generate_count + 1,
                    "sql_regenerate_reason": None,
                }
            except Exception as e:
                logger.error(f"[SqlGenerate] Retry error: {e}")
                return {
                    "sql_generate_count": generate_count + 1,
                    "sql_regenerate_reason": {"type": "generate", "reason": str(e)},
                }
        else:
            logger.info(f"[SqlGenerate] First generation for: {instruction[:80]}")
            if not schema:
                return {"error": "No schema information available"}

            prompt = (
                f"数据库方言: {dialect}\n\n"
                f"数据库 Schema:\n{schema}\n\n"
                f"知识证据:\n{evidence}\n\n"
                f"用户问题: {user_query}\n\n"
                f"当前步骤需求: {instruction}\n\n"
                f"请生成 SQL 查询语句。"
            )

            try:
                sql = await llm_service.chat(SQL_GENERATION_SYSTEM_PROMPT, prompt, temperature=0.0)
                sql = clean_code_block(sql, lang="sql")
                logger.info(f"[SqlGenerate] Generated SQL: {sql[:100]}...")
                return {
                    "generated_sql": sql,
                    "sql_generate_count": 1,
                    "sql_regenerate_reason": None,
                }
            except Exception as e:
                logger.error(f"[SqlGenerate] Error: {e}")
                return {
                    "error": f"SQL generation failed: {str(e)}",
                    "sql_generate_count": generate_count + 1,
                }

    def format_sse(self, output: Dict[str, Any]) -> SSEPayload | None:
        sql = output.get("generated_sql", "")
        if sql:
            # [旧代码] 不声明 Agent/Tool
            # return SSEPayload(
            #     text=sql,
            #     text_type="SQL",
            #     metrics_delta={"sql_generated": True},
            # )
            # V3.0: 声明 Analyst 归属 + text_to_sql tool
            return SSEPayload(
                text=sql,
                text_type="SQL",
                metrics_delta={"sql_generated": True},
                agent_name="Analyst", tool_name="text_to_sql",
                tool_status="done",
            )
        return None


# LangGraph 兼容实例
sql_generate_node = SqlGenerateNode()
