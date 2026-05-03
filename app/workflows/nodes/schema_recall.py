"""
数据库 Schema 检索节点 — 对齐 Java SchemaRecallNode

【在系统中的地位】
  这个节点连接 Agent 的数据源，读取实际的数据库表结构 (DDL)，
  将结构化信息转为 LLM 能理解的文本格式，作为 SQL 生成的上下文。

【模块连接】
  上游 (由谁路由到此):
    - query_rewrite → 查询改写成功后路由而来

  下游 (写入 state):
    - state["schema"]      → DDL 文本 (如 "CREATE TABLE users (id INT, name VARCHAR...)")
    - state["schema_info"] → 结构化 dict {tables: [...], relations: [...]}

  调用链:
    - AgentDatasourceService.get_active_datasource() → 获取 Agent 激活的数据源连接
    - SchemaService.get_database_ddl()               → 查询 information_schema 获取 DDL
    - SchemaService.get_database_schema()            → 返回结构化表/列信息

  路由 (graph.py):
    - schema_recall → table_relation (如果 schema 非空)
    - schema_recall → END (如果无 schema)

  Java 对应:
    schema_recall_node ≈ SchemaRecallNode.java
    SchemaService       ≈ SchemaService.java

【DDL 格式示例】
  CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '用户ID',
    name VARCHAR(100) NOT NULL COMMENT '用户名',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
  );
  ...
  这种格式 LLM 可以直接理解，用于生成准确的 SQL。
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
