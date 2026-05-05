"""
SQL 执行节点（SQL Execute Node） — 对齐 Java SqlExecuteNode
执行 SQL 并回写结果到执行计划，支持图表配置推荐
"""
from typing import Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from ..state import WorkflowState, get_current_step_number
from ...services.agent_datasource_service import AgentDatasourceService
from ...core.database import async_session_maker
from ...core.config import settings
import logging
import json

logger = logging.getLogger(__name__)


def _build_connection_url(datasource) -> str:
    """构建数据库连接 URL"""
    if datasource.type == "mysql":
        return (
            f"mysql+aiomysql://{datasource.username}:{datasource.password}"
            f"@{datasource.host}:{datasource.port}/{datasource.database}"
        )
    elif datasource.type == "postgresql":
        return (
            f"postgresql+asyncpg://{datasource.username}:{datasource.password}"
            f"@{datasource.host}:{datasource.port}/{datasource.database}"
        )
    elif datasource.type == "sqlite":
        return datasource.connection_url or f"sqlite+aiosqlite:///{datasource.database}"
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


async def sql_execute_node(state: WorkflowState) -> Dict[str, Any]:
    """SQL 执行节点 — 对齐 Java SqlExecuteNode.apply()

    1. 执行 SQL
    2. 回写 sql_query 到当前步骤的 tool_parameters
    3. 存储结果到 sql_result_list_memory (供 Python 节点使用)
    4. 存储分步结果到 sql_step_results
    """
    agent_id = state["agent_id"]
    sql = state.get("generated_sql")

    if not sql:
        logger.warning("[SqlExecute] No SQL to execute")
        return {"sql_error": "No SQL to execute"}

    current_step = get_current_step_number(state)
    logger.info(f"[SqlExecute] Step {current_step}: executing SQL ({len(sql)} chars)")

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
                    logger.info(f"[SqlExecute] Got {len(sql_result)} rows, {len(columns)} columns")

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
                        "plan_current_step": current_step + 1,  # 当前步骤完成，递增
                    }
                    # 仅在 plan 被修改后才回写，避免覆盖为 None
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
