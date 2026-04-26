from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..schemas.query import QueryRequest, QueryResponse
from ..workflows.graph import compiled_workflow
from ..workflows.state import WorkflowState

router = APIRouter(prefix="/api", tags=["查询执行"])


@router.post("/query", response_model=QueryResponse, summary="执行查询")
async def execute_query(
    query_request: QueryRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    执行查询（核心接口）

    工作流：
    1. 意图识别 - 判断是否需要查询数据库
    2. 数据库模式检索 - 获取表结构
    3. SQL 生成 - 使用 LLM 生成 SQL
    4. SQL 执行 - 执行查询
    5. 报告生成 - 生成自然语言报告

    - **agent_id**: Agent ID（必填）
    - **query**: 用户问题（必填）

    返回：
    - **intent**: 意图（data_analysis/chitchat）
    - **sql**: 生成的 SQL（如果是数据分析）
    - **result**: 查询结果（如果是数据分析）
    - **report**: 分析报告
    - **error**: 错误信息（如果有）
    """
    # 构建初始状态
    initial_state: WorkflowState = {
        "agent_id": query_request.agent_id,
        "user_query": query_request.query,
        "sql_retry_count": 0
    }

    try:
        # 执行工作流
        final_state = await compiled_workflow.ainvoke(initial_state)

        # 构建响应
        intent = final_state.get("intent", "chitchat")

        if intent == "chitchat":
            # 闲聊响应
            return QueryResponse(
                intent=intent,
                report="您好！我是数据分析助手，专门帮助您分析数据。请问有什么数据分析需求吗？"
            )
        else:
            # 数据分析响应
            return QueryResponse(
                intent=intent,
                sql=final_state.get("generated_sql"),
                result=final_state.get("sql_result"),
                report=final_state.get("report"),
                error=final_state.get("error")
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")
