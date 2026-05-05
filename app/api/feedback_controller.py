"""人工反馈 API — 对齐 Java (LangGraph interrupt + HumanFeedback entity)"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from ..core.database import get_db
from ..core.workflow_controller import get_workflow_controller
from ..models.human_feedback import HumanFeedback
from ..schemas.human_feedback import (
    HumanFeedbackSubmitRequest,
    HumanFeedbackResponse,
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def _to_response(feedback: HumanFeedback) -> dict:
    return HumanFeedbackResponse.model_validate(feedback).model_dump(by_alias=True)


@router.get("/workflows/{workflow_id}/status", summary="获取工作流状态")
async def get_workflow_status(workflow_id: str):
    """获取工作流实时状态"""
    controller = get_workflow_controller()
    workflow = controller.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {
        "workflow_id": workflow.workflow_id,
        "agent_id": workflow.agent_id,
        "status": workflow.status,
        "current_node": workflow.current_node,
        "query": workflow.query,
        "feedback_data": workflow.feedback_data,
        "created_at": workflow.created_at.isoformat(),
        "updated_at": workflow.updated_at.isoformat(),
    }


@router.get("/feedback/pending", summary="获取待审批任务")
async def get_pending_feedback(
    agent_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取待审批任务 — 对齐 Java findPendingFeedback"""
    query = select(HumanFeedback).filter(HumanFeedback.status == "pending")

    if agent_id:
        query = query.filter(HumanFeedback.agent_id == agent_id)

    result = await db.execute(query.order_by(HumanFeedback.created_at.desc()))
    feedbacks = result.scalars().all()
    return [_to_response(f) for f in feedbacks]


@router.post("/feedback/{workflow_id}", summary="提交反馈")
async def submit_feedback(
    workflow_id: str,
    submit: HumanFeedbackSubmitRequest,
    db: AsyncSession = Depends(get_db)
):
    """提交反馈 — 对齐 Java submitFeedback"""
    query = select(HumanFeedback).filter(
        HumanFeedback.workflow_id == workflow_id,
        HumanFeedback.status == "pending"
    )
    result = await db.execute(query)
    feedback = result.scalar_one_or_none()

    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    feedback.action = submit.action
    feedback.comment = submit.comment
    feedback.modified_content = submit.modified_content

    if submit.action == "approve":
        feedback.status = "approved"
    elif submit.action == "reject":
        feedback.status = "rejected"
    elif submit.action == "modify":
        feedback.status = "approved"

    await db.commit()
    await db.refresh(feedback)

    controller = get_workflow_controller()
    feedback_data = {
        "action": submit.action,
        "comment": submit.comment,
        "modified_content": submit.modified_content
    }
    resumed = await controller.resume_workflow(workflow_id, feedback_data)
    if not resumed:
        raise HTTPException(status_code=400, detail="Workflow is not in paused state or not found")

    return _to_response(feedback)


@router.get("/feedback/history", summary="获取反馈历史")
async def get_feedback_history(
    workflow_id: Optional[str] = None,
    agent_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取反馈历史 — 对齐 Java findFeedbackHistory"""
    query = select(HumanFeedback)

    if workflow_id:
        query = query.filter(HumanFeedback.workflow_id == workflow_id)
    if agent_id:
        query = query.filter(HumanFeedback.agent_id == agent_id)

    result = await db.execute(query.order_by(HumanFeedback.created_at.desc()))
    feedbacks = result.scalars().all()
    return [_to_response(f) for f in feedbacks]


@router.get("/feedback/{feedback_id}", summary="获取反馈详情")
async def get_feedback(
    feedback_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取反馈详情 — 对齐 Java getFeedback"""
    query = select(HumanFeedback).filter(HumanFeedback.id == feedback_id)
    result = await db.execute(query)
    feedback = result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return _to_response(feedback)
