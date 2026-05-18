"""
数据库 Schema 检索节点 — 对齐 Java SchemaRecallNode

Harness 角色: 连接 Agent 的数据源，读取实际数据库表结构 (DDL)，
将结构化信息转为 LLM 能理解的文本格式。

I/O 契约:
  requires: agent_id
  provides: schema (DDL 文本), schema_info (结构化 dict)
"""

from ..state import WorkflowState
from ..node_base import WorkflowNode, SSEPayload
from ...services.agent_datasource_service import AgentDatasourceService
from ...services.schema_service import SchemaService
from ...core.database import async_session_maker
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SchemaRecallNode(WorkflowNode):
    """数据库模式检索 — 对齐 Java SchemaRecallNode

    获取 Agent 激活数据源的表结构信息（DDL 文本 + 结构化 dict）。
    DDL 供 LLM 理解，结构化 dict 供后续节点（table_relation）使用。
    """

    name = "schema_recall"
    description = "读取数据库表结构 (DDL)，供 LLM 生成 SQL 时使用"
    requires = ["agent_id"]
    provides = ["schema", "schema_info"]
    applicable_data_sources = ["database"]

    async def execute(self, state: WorkflowState) -> Dict[str, Any]:
        agent_id = state["agent_id"]

        try:
            async with async_session_maker() as session:
                datasource = await AgentDatasourceService.get_active_datasource(session, agent_id)

                if not datasource:
                    logger.warning(f"Agent {agent_id} 没有激活的数据源 — 无法进行数据分析")
                    return {
                        "error": "No active datasource found for this Agent",
                        "_no_datasource": True,  # 标记，供 format_sse 识别
                    }

                schema_ddl = await SchemaService.get_database_ddl(datasource)
                schema_dict = await SchemaService.get_database_schema(datasource)

                table_count = len(schema_dict.get("tables", []))
                logger.info(
                    f"Schema 召回完成: {datasource.database_name}, {table_count} 张表"
                )
                return {"schema": schema_ddl, "schema_info": schema_dict}

        except Exception as e:
            logger.error(f"Schema 召回失败: {str(e)}", exc_info=True)
            return {"error": f"Schema recall failed: {str(e)}"}

    def format_sse(self, output: Dict[str, Any]) -> SSEPayload | None:
        # [旧代码] 不声明 Agent/Tool
        # 无数据源 → 明确告知用户，不继续走数据分析链路
        if output.get("_no_datasource"):
            # return SSEPayload(
            #     text="当前 Agent 没有配置数据源，请先在 Agent 设置中绑定一个数据库。",
            #     text_type="TEXT",
            # )
            return SSEPayload(
                text="当前 Agent 没有配置数据源，请先在 Agent 设置中绑定一个数据库。",
                text_type="TEXT",
                agent_name="Explorer", tool_name="get_schema",
                tool_status="error", tool_summary="无数据源",
            )
        # 召回异常 → 告知用户并提供错误信息
        if output.get("error") and not output.get("schema_info"):
            # return SSEPayload(
            #     text=f"数据库 Schema 加载失败：{output['error']}",
            #     text_type="TEXT",
            # )
            return SSEPayload(
                text=f"数据库 Schema 加载失败：{output['error']}",
                text_type="TEXT",
                agent_name="Explorer", tool_name="get_schema",
                tool_status="error", tool_summary="Schema 加载失败",
            )
        # 正常召回 → 报告发现的表数量
        schema_info = output.get("schema_info", {})
        tables = schema_info.get("tables", []) if isinstance(schema_info, dict) else []
        table_count = len(tables)
        text = f"正在加载数据库表结构...找到 {table_count} 张表" if table_count else "正在加载数据库表结构..."
        # return SSEPayload(text=text, text_type="TEXT")
        return SSEPayload(
            text=text, text_type="TEXT",
            agent_name="Explorer", tool_name="get_schema",
            tool_status="done", tool_summary=f"找到 {table_count} 张表",
        )


# LangGraph 兼容实例
schema_recall_node = SchemaRecallNode()
