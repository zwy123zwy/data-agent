"""
工作流节点：SQL 执行
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from ..state import WorkflowState
from ...services.agent_datasource_service import AgentDatasourceService
from ...core.database import async_session_maker


async def sql_execute_node(state: WorkflowState) -> WorkflowState:
    """
    SQL 执行节点

    执行生成的 SQL 语句并返回结果
    """
    agent_id = state["agent_id"]
    sql = state.get("generated_sql")

    if not sql:
        state["error"] = "No SQL to execute"
        return state

    try:
        # 获取激活的数据源
        async with async_session_maker() as session:
            datasource = await AgentDatasourceService.get_active_datasource(session, agent_id)

            if not datasource:
                state["error"] = "No active datasource found"
                return state

            # 构建数据库连接
            if datasource.type == "mysql":
                db_url = f"mysql+aiomysql://{datasource.username}:{datasource.password}@{datasource.host}:{datasource.port}/{datasource.database}"
            elif datasource.type == "sqlite":
                db_url = datasource.connection_url or f"sqlite+aiosqlite:///{datasource.database}"
            else:
                state["error"] = f"Unsupported database type: {datasource.type}"
                return state

            # 创建临时引擎执行查询
            temp_engine = create_async_engine(db_url, echo=False)

            try:
                async with temp_engine.connect() as conn:
                    result = await conn.execute(text(sql))

                    # 将结果转换为字典列表
                    rows = result.fetchall()
                    columns = result.keys()

                    sql_result = []
                    for row in rows:
                        row_dict = {}
                        for i, col in enumerate(columns):
                            row_dict[col] = row[i]
                        sql_result.append(row_dict)

                    state["sql_result"] = sql_result
                    state["sql_error"] = None

            finally:
                await temp_engine.dispose()

    except Exception as e:
        state["sql_error"] = str(e)
        state["sql_result"] = None

        # 增加重试计数
        retry_count = state.get("sql_retry_count", 0)
        state["sql_retry_count"] = retry_count + 1

    return state
