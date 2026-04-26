"""
工作流节点：数据库模式检索
"""
from ..state import WorkflowState
from ...services.agent_datasource_service import AgentDatasourceService
from ...services.schema_service import SchemaService
from ...core.database import async_session_maker
import logging

logger = logging.getLogger(__name__)


async def schema_recall_node(state: WorkflowState) -> WorkflowState:
    """
    数据库模式检索节点

    获取 Agent 激活数据源的表结构信息（使用统一的 Schema 服务）
    """
    agent_id = state["agent_id"]

    try:
        # 获取激活的数据源
        async with async_session_maker() as session:
            datasource = await AgentDatasourceService.get_active_datasource(session, agent_id)

            if not datasource:
                state["error"] = "No active datasource found for this Agent"
                logger.error(f"Agent {agent_id} 没有激活的数据源")
                return state

            # 使用 SchemaService 获取数据库 DDL（格式化为 LLM 友好的文本）
            schema_ddl = await SchemaService.get_database_ddl(datasource)

            # 同时保存结构化的 schema 信息（用于后续处理）
            schema_dict = await SchemaService.get_database_schema(datasource)

            state["schema"] = schema_ddl  # LLM 使用的文本格式
            state["schema_info"] = schema_dict  # 结构化数据

            logger.info(f"Schema 召回完成: {datasource.database}, {len(schema_dict['tables'])} 张表")

    except Exception as e:
        state["error"] = f"Schema recall failed: {str(e)}"
        logger.error(f"Schema 召回失败: {str(e)}", exc_info=True)

    return state
