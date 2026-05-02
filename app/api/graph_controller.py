from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..schemas.query import QueryRequest, QueryResponse
from ..workflows.graph import compiled_workflow
from ..workflows.state import WorkflowState
from ..core.workflow_controller import get_workflow_controller
from ..models.human_feedback import HumanFeedback

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
    controller = get_workflow_controller()

    # 恢复路径：携带 workflow_id + feedback 时恢复执行
    if query_request.workflow_id and query_request.human_feedback_content:
        feedback_data = {
            "action": "reject" if query_request.rejected_plan else "approve",
            "comment": query_request.human_feedback_content,
            "modified_content": query_request.human_feedback_content if query_request.rejected_plan else None,
        }
        resumed = await controller.resume_workflow(query_request.workflow_id, feedback_data)
        if not resumed:
            raise HTTPException(status_code=400, detail="Workflow is not in paused state or not found")

    # 暂停路径：启用人工反馈，先创建待审批任务
    if query_request.human_feedback and not query_request.human_feedback_content:
        workflow_id = controller.create_workflow(query_request.agent_id, query_request.query)
        await controller.pause_workflow(workflow_id)
        feedback = HumanFeedback(
            workflow_id=workflow_id,
            agent_id=query_request.agent_id,
            node_name="human_feedback",
            content=query_request.query,
            status="pending",
        )
        db.add(feedback)
        await db.commit()
        return QueryResponse(
            intent="data_analysis",
            report="工作流已暂停，等待人工反馈",
            workflow_id=workflow_id,
            status="paused",
        )

    effective_query = query_request.query
    if query_request.workflow_id:
        feedback_data = controller.get_feedback_data(query_request.workflow_id) or {}
        if feedback_data.get("modified_content"):
            effective_query = feedback_data["modified_content"]
        elif feedback_data.get("comment"):
            effective_query = feedback_data["comment"]

    # 构建初始状态
    initial_state: WorkflowState = {
        "agent_id": query_request.agent_id,
        "user_query": effective_query,
        "sql_retry_count": 0
    }

    try:
        # 执行工作流
        final_state = await compiled_workflow.ainvoke(initial_state)

        # 构建响应
        intent = final_state.get("intent", "chitchat")

        if intent == "chitchat":
            # 闲聊响应
            if query_request.workflow_id:
                await controller.complete_workflow(query_request.workflow_id)
            return QueryResponse(
                intent=intent,
                report="您好！我是数据分析助手，专门帮助您分析数据。请问有什么数据分析需求吗？",
                workflow_id=query_request.workflow_id,
                status="completed",
            )
        else:
            # 数据分析响应
            if query_request.workflow_id:
                await controller.complete_workflow(query_request.workflow_id)
            return QueryResponse(
                intent=intent,
                sql=final_state.get("generated_sql"),
                result=final_state.get("sql_result"),
                report=final_state.get("report"),
                error=final_state.get("error"),
                workflow_id=query_request.workflow_id,
                status="completed",
            )

    except Exception as e:
        if query_request.workflow_id:
            await controller.error_workflow(query_request.workflow_id, str(e))
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")
