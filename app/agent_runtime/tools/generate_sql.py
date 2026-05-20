# [阶段1] generate_sql Tool — 包装 SchemaRecall + SqlGenerateNode

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.artifacts import Artifact, Provenance
from app.agent_runtime.context import RuntimeContext
from app.agent_runtime.tools.base import BaseTool, ToolResult
from app.workflows.nodes.planner import NL2SQL_PLAN
from app.workflows.nodes.schema_recall import schema_recall_node
from app.workflows.nodes.sql_generate import sql_generate_node


class GenerateSqlTool(BaseTool):
    """[阶段1] 探查 Schema 并生成 SELECT SQL（smart_query 单步计划）。"""

    name = "generate_sql"

    async def run(
        self,
        ctx: RuntimeContext,
        state: dict[str, Any],
        db: AsyncSession,
    ) -> ToolResult:
        merged = {**state, "agent_id": ctx.agent_id, "user_query": ctx.user_query}
        merged.setdefault("query_plan", json.dumps(NL2SQL_PLAN, ensure_ascii=False))
        merged.setdefault("plan_current_step", 1)
        merged.setdefault("sql_generate_count", 0)
        merged.setdefault("semantic_model_prompt", ctx.semantic_model.get("prompt", ""))
        merged.setdefault(
            "multi_turn_context",
            "\n".join(m.content for m in ctx.memory[-6:]),
        )
        state.setdefault("semantic_model_prompt", merged["semantic_model_prompt"])
        state.setdefault("multi_turn_context", merged["multi_turn_context"])

        if not merged.get("schema"):
            schema_out = await schema_recall_node.execute(merged)
            merged.update(schema_out)
            state.update(schema_out)
            if schema_out.get("_no_datasource") or schema_out.get("error"):
                msg = schema_out.get("error") or "未配置激活数据源"
                return ToolResult(
                    status="error",
                    tool_name=self.name,
                    summary=msg[:200],
                    error_code="NO_DATASOURCE",
                    error_severity="fatal",
                )

        ds = ctx.datasets[0] if ctx.datasets else None
        if ds:
            merged["db_dialect_type"] = ds.dialect
            state.setdefault("db_dialect_type", ds.dialect)

        output = await sql_generate_node.execute(merged)
        state.update(output)

        sql = output.get("generated_sql", "")
        if output.get("error") or not sql:
            err = output.get("error", "SQL 生成失败")
            return ToolResult(
                status="error",
                tool_name=self.name,
                summary=str(err)[:200],
                error_code="SQL_GENERATE_ERROR",
                error_severity="retryable",
            )

        obs_id = str(uuid4())
        artifact = Artifact(
            type="sql",
            content=sql,
            provenance=Provenance(
                agent_name="Explorer",
                tool_name=self.name,
                observation_id=obs_id,
            ),
        )
        return ToolResult(
            status="ok",
            tool_name=self.name,
            data={"sql": sql},
            summary=artifact.summary(80),
            artifacts=[artifact],
            v1_text=sql,
            v1_text_type="SQL",
        )
