"""
QueryPlan API
查询计划管理接口
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..services.agent_service import AgentService
from ..schemas.query_plan import (
    GeneratePlanRequest,
    GeneratePlanResponse,
    ExecutePlanRequest,
    QueryPlanResponse,
    ExecutePlanResponse,
    QueryPlanListResponse,
)
from ..workflows.nodes.planner import planner_node
from ..workflows.nodes.plan_executor import plan_executor_node
from ..workflows.state import AgentState
from ..models.query_plan import QueryPlan
from sqlalchemy import select, func
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents/{agent_id}/plans", tags=["QueryPlan"])


@router.post("/generate", response_model=GeneratePlanResponse)
async def generate_plan(
    agent_id: int,
    request: GeneratePlanRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    生成查询计划（不执行）

    分析用户查询，生成多步骤执行计划
    """
    # 检查 Agent 是否存在
    agent = await AgentService.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")

    # 构建状态
    state: AgentState = {
        "agent_id": agent_id,
        "user_query": request.query,
        "sql_retry_count": 0
    }

    # 调用计划生成节点
    result = await planner_node(state)

    if not result.get("is_complex_query"):
        return GeneratePlanResponse(
            plan={"simple": True, "message": "这是一个简单查询，不需要多步骤计划"},
            steps=[],
        )

    query_plan = result.get("query_plan", {})
    steps = query_plan.get("steps", [])

    return GeneratePlanResponse(
        plan=query_plan,
        steps=steps,
    )


@router.post("/execute", response_model=ExecutePlanResponse)
async def execute_plan(
    agent_id: int,
    request: ExecutePlanRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    执行查询计划

    生成并执行多步骤计划
    """
    # 检查 Agent 是否存在
    agent = await AgentService.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")

    try:
        # 构建状态
        state: AgentState = {
            "agent_id": agent_id,
            "user_query": request.query,
            "sql_retry_count": 0
        }

        # 1. 生成计划
        plan_result = await planner_node(state)

        if not plan_result.get("is_complex_query"):
            return ExecutePlanResponse(
                simple=True,
                message="简单查询，不需要多步骤计划",
                plan=None,
            )

        query_plan = plan_result.get("query_plan")

        # 2. 保存计划到数据库
        plan_record = QueryPlan(
            agent_id=agent_id,
            user_query=request.query,
            plan_json=query_plan,
            status="pending"
        )
        db.add(plan_record)
        await db.commit()
        await db.refresh(plan_record)

        # 3. 执行计划（如果 auto_execute=True）
        if request.auto_execute:
            # 更新状态
            state["query_plan"] = query_plan

            # 执行计划
            plan_record.status = "running"
            await db.commit()

            exec_result = await plan_executor_node(state)

            # 更新结果
            if exec_result.get("error"):
                plan_record.status = "failed"
                plan_record.error = exec_result["error"]
            else:
                plan_record.status = "completed"
                plan_record.result = exec_result.get("plan_execution_result")

            await db.commit()
            await db.refresh(plan_record)

        return ExecutePlanResponse(
            simple=False,
            message="计划已生成并处理",
            plan=QueryPlanResponse.model_validate(plan_record),
        )

    except Exception as e:
        logger.error(f"Execute plan error: {e}")
        raise HTTPException(status_code=500, detail=f"执行计划失败: {str(e)}")


@router.get("/{plan_id}", response_model=QueryPlanResponse)
async def get_plan(
    agent_id: int,
    plan_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取查询计划详情"""
    result = await db.execute(
        select(QueryPlan).where(QueryPlan.id == plan_id)
    )
    plan = result.scalar_one_or_none()

    if not plan or plan.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="查询计划不存在")

    return plan


@router.get("", response_model=QueryPlanListResponse)
async def list_plans(
    agent_id: int,
    status: str = None,
    page: int = 1,
    size: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """列出查询计划历史"""
    # 检查 Agent 是否存在
    agent = await AgentService.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")

    # 构建查询
    query = select(QueryPlan).where(QueryPlan.agent_id == agent_id)
    if status:
        query = query.where(QueryPlan.status == status)

    # 查询总数
    count_query = select(func.count(QueryPlan.id)).where(QueryPlan.agent_id == agent_id)
    if status:
        count_query = count_query.where(QueryPlan.status == status)
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # 查询列表
    skip = (page - 1) * size
    query = query.order_by(QueryPlan.created_at.desc()).offset(skip).limit(size)
    result = await db.execute(query)
    plans = result.scalars().all()

    return QueryPlanListResponse(
        items=[QueryPlanResponse.model_validate(p) for p in plans],
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size,
    )
