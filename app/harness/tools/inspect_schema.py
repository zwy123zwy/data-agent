# [阶段2] inspect_schema — SchemaService，无 V1NodeTool
# [Harness: Tool Access #1] Schema 检查工具，读取数据源 DDL + 结构化 Schema。
#
# 同时获取两种格式的原因:
#   schema_ddl  (DDL 文本): 注入 generate_sql 的 prompt，LLM 原生理解 DDL 格式
#   schema_dict (结构化): 存入 state["schema_info"]，供后续工具（如 execute_sql）
#     做类型校验、主键检测等编程访问，避免从 DDL 文本中重新解析

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.harness.tools.base import BaseTool, ToolResult
from app.harness.types.artifacts import Artifact, Provenance
from app.harness.types.context import RuntimeContext
from app.services.agent_datasource_service import AgentDatasourceService
from app.services.schema_service import SchemaService


class HarnessInspectSchemaTool(BaseTool):
    """[阶段2] 读取激活数据源 DDL，写入 workflow state['schema']。"""

    name = "inspect_schema"

    async def run(
        self,
        ctx: RuntimeContext,
        state: dict[str, Any],
        db: AsyncSession,
    ) -> ToolResult:
        datasource = await AgentDatasourceService.get_active_datasource(db, ctx.agent_id)
        if not datasource:
            return ToolResult(
                status="error",
                tool_name=self.name,
                summary="未配置激活数据源",
                error_code="NO_DATASOURCE",
                error_severity="fatal",
            )

        try:
            table_names = [d.table_name for d in ctx.datasets] or None
            schema_ddl = await SchemaService.get_database_ddl(datasource, table_names=table_names)
            schema_dict = await SchemaService.get_database_schema(datasource, table_names=table_names)
        except Exception as exc:
            return ToolResult(
                status="error",
                tool_name=self.name,
                summary=str(exc)[:200],
                error_code="SCHEMA_RECALL_ERROR",
                error_severity="retryable",
            )

        state["schema"] = schema_ddl
        state["schema_info"] = schema_dict
        if ctx.datasets:
            state["db_dialect_type"] = ctx.datasets[0].dialect

        obs_id = str(uuid4())
        summary = f"Schema 已加载（约 {len(schema_dict.get('tables', []))} 张表）"
        return ToolResult(
            status="ok",
            tool_name=self.name,
            data={"schema": schema_ddl},
            summary=summary,
            artifacts=[
                Artifact(
                    type="schema",
                    content=schema_ddl[:2000],
                    provenance=Provenance(
                        agent_name="Explorer",
                        tool_name=self.name,
                        observation_id=obs_id,
                    ),
                )
            ],
            v1_text=schema_ddl[:8000] if isinstance(schema_ddl, str) else str(schema_ddl)[:8000],
            v1_text_type="TEXT",
        )
