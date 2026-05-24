# [阶段2] execute_sql — 安全校验 + 数据源执行，无 workflows 节点包装
# [Harness: Sandbox #5] SQL 执行工具，只读执行 + 安全校验 + 结果序列化。
#
# 安全机制:
#   ① validate_sql_safety(): 检查 SQL 是否为写操作（INSERT/UPDATE/DELETE/DROP 等），
#      命中则设置 sql_regenerate_reason (type=safety)，不执行 SQL，由 explorer 重试
#   ② 只读执行: 即使安全校验通过也用只读连接执行，双重保险
#
# _serialize_row(): 处理 SQL 驱动返回的 Python 类型 → JSON 可序列化类型
#   datetime → isoformat, Decimal → float, bytes → str
#
# _connection_url(): 按数据源类型组装 SQLAlchemy async 连接串
#   mysql → mysql+aiomysql, postgresql → postgresql+asyncpg, sqlite → sqlite+aiosqlite

from __future__ import annotations

import asyncio
import json
import logging
import re
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.harness.tools.base import BaseTool, ToolResult
from app.harness.types.artifacts import Artifact, Provenance
from app.harness.types.context import RuntimeContext
from app.core.sql_validator import validate_sql_safety
from app.harness.tools.constants import NL2SQL_PLAN_JSON
from app.services.agent_datasource_service import AgentDatasourceService

logger = logging.getLogger(__name__)


def _sql_exec_timeout_seconds() -> float:
    """[阶段2] 单次 SQL 执行超时（M2.5，可与工具总超时共用配置）。"""
    return max(5.0, float(getattr(settings, "harness_sql_timeout_seconds", 60)))


def _max_result_rows(ctx: RuntimeContext) -> int:
    """[阶段2] 结果行数上限（M2.5 T-04）。"""
    return max(1, int(ctx.permissions.max_sql_result_rows))


def _apply_row_limit(sql: str, max_rows: int) -> str:
    """[阶段2] 若无 LIMIT 则追加行数上限（仅 SELECT/WITH 简单场景）。"""
    stripped = sql.strip().rstrip(";")
    if re.search(r"\blimit\s+\d+", stripped, re.IGNORECASE):
        return stripped
    return f"{stripped}\nLIMIT {max_rows}"


def _connection_url(datasource) -> str:
    if datasource.type == "mysql":
        return (
            f"mysql+aiomysql://{datasource.username}:{datasource.password}"
            f"@{datasource.host}:{datasource.port}/{datasource.database_name}"
        )
    if datasource.type == "postgresql":
        return (
            f"postgresql+asyncpg://{datasource.username}:{datasource.password}"
            f"@{datasource.host}:{datasource.port}/{datasource.database_name}"
        )
    if datasource.type == "sqlite":
        return datasource.connection_url or f"sqlite+aiosqlite:///{datasource.database_name}"
    raise ValueError(f"不支持的数据库类型: {datasource.type}")


def _serialize_row(row, columns) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for i, col in enumerate(columns):
        val = row[i]
        if hasattr(val, "isoformat"):
            val = val.isoformat()
        elif isinstance(val, Decimal):
            val = float(val)
        elif isinstance(val, (bytes, bytearray)):
            val = str(val)
        out[col] = val
    return out


class HarnessExecuteSqlTool(BaseTool):
    """[阶段2] 只读执行 generated_sql，返回 RESULT_SET。"""

    name = "execute_sql"

    async def run(
        self,
        ctx: RuntimeContext,
        state: dict[str, Any],
        db: AsyncSession,
    ) -> ToolResult:
        sql = (state.get("generated_sql") or "").strip()
        if not sql:
            return ToolResult(
                status="error",
                tool_name=self.name,
                summary="无待执行 SQL",
                error_code="NO_SQL",
                error_severity="fatal",
            )

        safety = validate_sql_safety(sql)
        if safety:
            state["sql_regenerate_reason"] = {"type": "safety", "reason": safety}
            return ToolResult(
                status="error",
                tool_name=self.name,
                summary=f"SQL 安全校验失败: {safety}",
                error_code="SQL_SAFETY",
                error_severity="retryable",
            )

        datasource = await AgentDatasourceService.get_active_datasource(db, ctx.agent_id)
        if not datasource:
            return ToolResult(
                status="error",
                tool_name=self.name,
                summary="无激活数据源",
                error_code="NO_DATASOURCE",
                error_severity="fatal",
            )

        state.setdefault("query_plan", NL2SQL_PLAN_JSON)
        max_rows = _max_result_rows(ctx)
        sql_to_run = _apply_row_limit(sql, max_rows)

        # TODO(T-09): 每次新建 Engine，高并发性能债；M2.5 未改
        engine = create_async_engine(_connection_url(datasource), echo=False)
        exec_timeout = _sql_exec_timeout_seconds()
        try:
            async with engine.connect() as conn:

                async def _run_query():
                    res = await conn.execute(text(sql_to_run))
                    return res.fetchall(), list(res.keys())

                rows, columns = await asyncio.wait_for(_run_query(), timeout=exec_timeout)
        except asyncio.TimeoutError:
            state["sql_regenerate_reason"] = {
                "type": "execute",
                "reason": f"SQL 执行超时（{int(exec_timeout)}s）",
            }
            return ToolResult(
                status="error",
                tool_name=self.name,
                summary=f"SQL 执行超时（{int(exec_timeout)}s）",
                error_code="SQL_EXECUTE_TIMEOUT",
                error_severity="retryable",
            )
        except Exception as exc:
            logger.error("[阶段2][execute_sql] %s", exc)
            state["sql_regenerate_reason"] = {"type": "execute", "reason": str(exc)}
            return ToolResult(
                status="error",
                tool_name=self.name,
                summary=str(exc)[:200],
                error_code="SQL_EXECUTE_ERROR",
                error_severity="retryable",
                v1_text=f"SQL 执行错误: {exc}",
                v1_text_type="TEXT",
            )
        finally:
            await engine.dispose()

        sql_result = [_serialize_row(r, columns) for r in rows]
        truncated = False
        if len(sql_result) > max_rows:
            sql_result = sql_result[:max_rows]
            truncated = True
        state["sql_result"] = sql_result
        table_payload = {"rows": sql_result, "columns": columns}

        obs_id = str(uuid4())
        artifact = Artifact(
            type="table",
            content=table_payload,
            provenance=Provenance(
                agent_name="Explorer",
                tool_name=self.name,
                observation_id=obs_id,
            ),
        )
        summary = f"查询返回 {len(sql_result)} 行"
        if truncated:
            summary += f"（已截断至 {max_rows} 行）"
        return ToolResult(
            status="ok",
            tool_name=self.name,
            data=table_payload,
            summary=summary,
            artifacts=[artifact],
            v1_text=json.dumps(sql_result, ensure_ascii=False),
            v1_text_type="RESULT_SET",
        )
