
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from langgraph.types import Command
from ..core.database import get_db
from ..schemas.query import QueryRequest, QueryResponse
from ..workflows.graph import get_compiled_workflow
from ..workflows.state import WorkflowState
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["查询执行"])


def _build_initial_state(
    agent_id: int,
    user_query: str,
    nl2sql_only: bool = False,
    human_review: bool = False,
    multi_turn_context: str = "",
) -> WorkflowState:
    return {
        "agent_id": agent_id,
        "user_query": user_query,
        "is_only_nl2sql": nl2sql_only,
        "human_review_enabled": human_review,
        "multi_turn_context": multi_turn_context,
        "sql_retry_count": 0,
        "sql_generate_count": 0,
        "python_tries_count": 0,
        "plan_repair_count": 0,
        "plan_current_step": 1,
    }


@router.post("/query", response_model=QueryResponse, summary="执行查询")
async def execute_query(
    query_request: QueryRequest,
    db: AsyncSession = Depends(get_db),
):
    """执行查询（核心接口）

    工作流拓扑:
    1. IntentRecognition → 意图识别
    2. KnowledgeRecall → 知识召回
    3. QueryRewrite → 查询改写
    4. SchemaRecall → Schema 召回
    5. TableRelation → 表关系构建
    6. FeasibilityAssessment → 可行性评估
    7. Planner → 计划生成
    8. PlanExecutor → 循环调度 (SQL/Python/Report)
    9. ReportGenerator → 报告生成

    - **agent_id**: Agent ID（必填）
    - **query**: 用户问题（必填）
    - **nl2sql_only**: 仅 NL2SQL 模式，跳过 Python 和报告
    - **human_feedback**: 启用人工审批
    """
    # 恢复路径：携带 thread_id + feedback_content 时恢复 HumanFeedback
    graph_input = _build_initial_state(
        agent_id=query_request.agent_id,
        user_query=query_request.query,
        nl2sql_only=query_request.nl2sql_only,
        human_review=query_request.human_feedback,
    )

    if query_request.workflow_id and query_request.human_feedback_content:
        action = "reject" if query_request.rejected_plan else "approve"
        graph_input = Command(
            resume={
                "action": action,
                "reason": query_request.human_feedback_content,
            }
        )

    try:
        # 使用 ainvoke 执行完整工作流
        config = (
            {"configurable": {"thread_id": query_request.workflow_id}}
            if query_request.workflow_id
            else None
        )
        compiled_workflow = await get_compiled_workflow()
        final_state = await compiled_workflow.ainvoke(graph_input, config)

        intent = final_state.get("intent", "chitchat")
        if intent == "chitchat":
            return QueryResponse(
                intent=intent,
                report="您好！我是数据分析助手，专门帮助您分析数据。请问有什么数据分析需求吗？",
                status="completed",
            )

        # 检查 HumanFeedback 暂停
        feedback_data = final_state.get("human_feedback_data")
        if feedback_data and isinstance(feedback_data, dict):
            if feedback_data.get("type") == "human_feedback":
                return QueryResponse(
                    intent=intent,
                    report="工作流暂停，等待人工审批",
                    workflow_id=query_request.workflow_id,
                    status="paused",
                )

        # 构建响应
        report = final_state.get("report") or final_state.get("markdown_report", "")
        plan = final_state.get("query_plan")
        if isinstance(plan, str):
            try:
                plan = json.loads(plan)
            except json.JSONDecodeError:
                plan = None

        return QueryResponse(
            intent=intent,
            sql=final_state.get("generated_sql"),
            result=final_state.get("sql_result"),
            report=report,
            error=final_state.get("error"),
            workflow_id=query_request.workflow_id,
            status="completed",
        )

    except Exception as e:
        logger.error(f"[GraphController] Error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Query execution failed: {str(e)}"
        )
