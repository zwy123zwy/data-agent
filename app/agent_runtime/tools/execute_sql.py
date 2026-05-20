# [阶段1] execute_sql Tool — 包装 V1 SqlExecuteNode

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.artifacts import Artifact, Provenance
from app.agent_runtime.context import RuntimeContext
from app.agent_runtime.tools.base import BaseTool, ToolResult
from app.workflows.nodes.planner import NL2SQL_PLAN
from app.workflows.nodes.sql_execute import sql_execute_node


class ExecuteSqlTool(BaseTool):
    """[阶段1] 安全执行 SQL 并返回表格结果（RESULT_SET）。"""

    name = "execute_sql"

    async def run(
        self,
        ctx: RuntimeContext,
        state: dict[str, Any],
        db: AsyncSession,
    ) -> ToolResult:
        merged = {**state, "agent_id": ctx.agent_id}
        merged.setdefault("query_plan", json.dumps(NL2SQL_PLAN, ensure_ascii=False))
        merged.setdefault("plan_current_step", 1)

        if not merged.get("generated_sql"):
            return ToolResult(
                status="error",
                tool_name=self.name,
                summary="无待执行 SQL",
                error_code="NO_SQL",
                error_severity="fatal",
            )

        output = await sql_execute_node.execute(merged)
        state.update(output)

        if output.get("sql_error"):
            err = output["sql_error"]
            return ToolResult(
                status="error",
                tool_name=self.name,
                summary=str(err)[:200],
                error_code="SQL_EXECUTE_ERROR",
                error_severity="retryable",
                v1_text=f"SQL 执行错误: {err}",
                v1_text_type="TEXT",
            )

        rows = output.get("sql_result") or []
        if rows and isinstance(rows[0], dict):
            columns = list(rows[0].keys())
        else:
            columns = []
        obs_id = str(uuid4())
        table_payload = {"rows": rows, "columns": columns}
        artifact = Artifact(
            type="table",
            content=table_payload,
            provenance=Provenance(
                agent_name="Explorer",
                tool_name=self.name,
                observation_id=obs_id,
            ),
        )
        return ToolResult(
            status="ok",
            tool_name=self.name,
            data=table_payload,
            summary=f"查询返回 {len(rows)} 行",
            artifacts=[artifact],
            v1_text=json.dumps(rows, ensure_ascii=False),
            v1_text_type="RESULT_SET",
        )
