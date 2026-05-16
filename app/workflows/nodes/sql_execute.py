"""
SQL 执行节点 — 对齐 Java SqlExecuteNode

Harness 角色: 执行 LLM 生成的 SQL，回写结果到执行计划和内存。
支持安全校验（只允许只读语句）、图表配置推荐和数据序列化。

I/O 契约:
  requires: agent_id, generated_sql, query_plan
  provides: sql_result, sql_result_list_memory, sql_step_results, sql_error, sql_regenerate_reason
"""
from typing import Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from ..state import WorkflowState, get_current_step_number
from ..node_base import WorkflowNode, SSEPayload
from ...services.agent_datasource_service import AgentDatasourceService
from ...core.database import async_session_maker
from ...core.config import settings
from ...core.sql_validator import validate_sql_safety
import logging
import json

logger = logging.getLogger(__name__)


def _build_connection_url(datasource) -> str:
    """构建数据库连接 URL"""
    if datasource.type == "mysql":
        return (
            f"mysql+aiomysql://{datasource.username}:{datasource.password}"
            f"@{datasource.host}:{datasource.port}/{datasource.database_name}"
        )
    elif datasource.type == "postgresql":
        return (
            f"postgresql+asyncpg://{datasource.username}:{datasource.password}"
            f"@{datasource.host}:{datasource.port}/{datasource.database_name}"
        )
    elif datasource.type == "sqlite":
        return datasource.connection_url or f"sqlite+aiosqlite:///{datasource.database_name}"
    else:
        raise ValueError(f"Unsupported database type: {datasource.type}")


def _serialize_row(row, columns) -> Dict[str, Any]:
    """将数据库行序列化为 JSON 兼容的 dict"""
    from decimal import Decimal
    result = {}
    for i, col in enumerate(columns):
        val = row[i]
        if hasattr(val, 'isoformat'):
            val = val.isoformat()
        elif isinstance(val, Decimal):
            val = float(val)
        elif isinstance(val, (bytes, bytearray)):
            val = str(val)
        elif isinstance(val, (set, frozenset)):
            val = list(val)
        result[col] = val
    return result


class SqlExecuteNode(WorkflowNode):
    """SQL 执行 — 对齐 Java SqlExecuteNode.apply()

    1. 安全校验（只允许 SELECT/WITH/EXPLAIN）
    2. 执行 SQL 并序列化结果
    3. 回写 sql_query 到当前步骤的 tool_parameters
    4. 追加到 sql_result_list_memory（供 Python 节点使用）
    5. 递增 plan_current_step（当前步骤完成）
    """

    name = "sql_execute"
    description = "安全校验 + 执行 SQL + 回写结果到执行计划内存，支持重试反馈"
    requires = ["agent_id", "generated_sql", "query_plan"]
    provides = [
        "sql_result", "sql_result_list_memory", "sql_step_results",
        "sql_error", "sql_regenerate_reason", "plan_current_step",
    ]
    applicable_data_sources = ["database"]

    async def execute(self, state: WorkflowState) -> Dict[str, Any]:
        agent_id = state["agent_id"]
        sql = state.get("generated_sql")

        if not sql:
            logger.warning("[SqlExecute] No SQL to execute")
            return {"sql_error": "No SQL to execute"}

        current_step = get_current_step_number(state)
        logger.info(f"[SqlExecute] Step {current_step}: executing SQL ({len(sql)} chars)")

        # SQL 安全校验 — 只允许 SELECT/WITH/EXPLAIN 等只读语句
        safety_error = validate_sql_safety(sql)
        if safety_error:
            logger.warning(f"[SqlExecute] SQL rejected by safety validator: {safety_error}")
            logger.warning(f"[SqlExecute] Rejected SQL: {sql[:200]}")
            return {
                "sql_error": f"SQL 安全校验失败: {safety_error}",
                "sql_regenerate_reason": {"type": "safety", "reason": safety_error},
            }

        try:
            async with async_session_maker() as session:
                datasource = await AgentDatasourceService.get_active_datasource(session, agent_id)
                if not datasource:
                    return {"sql_error": "No active datasource found"}

                db_url = _build_connection_url(datasource)
                temp_engine = create_async_engine(db_url, echo=False)

                try:
                    async with temp_engine.connect() as conn:
                        result = await conn.execute(text(sql))
                        rows = result.fetchall()
                        columns = list(result.keys())

                        sql_result = [_serialize_row(row, columns) for row in rows]
                        logger.info(
                            f"[SqlExecute] Got {len(sql_result)} rows, {len(columns)} columns"
                        )

                        # 回写 SQL 到当前步骤的 tool_parameters
                        plan = state.get("query_plan")
                        if isinstance(plan, str):
                            plan = json.loads(plan)
                        if plan:
                            steps = plan.get("execution_plan") or plan.get("steps", [])
                            idx = current_step - 1
                            if 0 <= idx < len(steps):
                                tp = steps[idx].get("tool_parameters") or {}
                                tp["sql_query"] = sql
                                steps[idx]["tool_parameters"] = tp

                        # 构建当前步骤的结果条目
                        step_result_entry = {
                            "step": current_step,
                            "sql": sql,
                            "result": sql_result,
                            "columns": columns,
                            "row_count": len(sql_result),
                        }

                        # 追加到 sql_result_list_memory — 对齐 Java
                        result_list = list(state.get("sql_result_list_memory") or [])
                        result_list.append(step_result_entry)

                        # 构建分步结果 — 对齐 Java
                        step_results = dict(state.get("sql_step_results") or {})
                        step_results[f"step_{current_step}"] = {
                            "sql": sql,
                            "data": sql_result,
                            "columns": columns,
                        }

                        result = {
                            "sql_result": sql_result,
                            "sql_result_list_memory": result_list,
                            "sql_step_results": step_results,
                            "sql_error": None,
                            "plan_current_step": current_step + 1,
                        }
                        if plan:
                            result["query_plan"] = json.dumps(plan, ensure_ascii=False)
                        return result

                finally:
                    await temp_engine.dispose()

        except Exception as e:
            logger.error(f"[SqlExecute] Error: {e}")
            return {
                "sql_error": str(e),
                "sql_regenerate_reason": {"type": "execute", "reason": str(e)},
            }

    def format_sse(self, output: Dict[str, Any]) -> SSEPayload | None:
        error = output.get("sql_error")
        result_data = output.get("sql_result")
        if error:
            return SSEPayload(
                text=f"SQL 执行错误: {error}",
                text_type="TEXT",
                metrics_delta={"sql_executed": True, "sql_success": False},
            )
        if result_data is not None:
            return SSEPayload(
                text=json.dumps(result_data, ensure_ascii=False),
                text_type="RESULT_SET",
                metrics_delta={"sql_executed": True, "sql_success": True},
            )
        return None


# LangGraph 兼容实例
sql_execute_node = SqlExecuteNode()
