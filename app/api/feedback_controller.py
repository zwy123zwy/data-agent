"""
人工反馈 API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from ..core.database import get_db
from ..core.workflow_controller import get_workflow_controller
from ..models.human_feedback import HumanFeedback
from ..schemas.human_feedback import (
    HumanFeedbackCreate,
    HumanFeedbackSubmit,
    HumanFeedbackResponse
)

router = APIRouter()


@router.get("/feedback/pending", response_model=List[HumanFeedbackResponse], summary="获取待审批任务")
async def get_pending_feedback(
    agent_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取待审批任务"""
    query = select(HumanFeedback).filter(HumanFeedback.status == "pending")

    if agent_id:
        query = query.filter(HumanFeedback.agent_id == agent_id)

    result = await db.execute(query.order_by(HumanFeedback.created_at.desc()))
    feedbacks = result.scalars().all()
    return feedbacks


@router.post("/feedback/{workflow_id}", response_model=HumanFeedbackResponse, summary="提交反馈")
async def submit_feedback(
    workflow_id: str,
    submit: HumanFeedbackSubmit,
    db: AsyncSession = Depends(get_db)
):
    """提交反馈"""
    # 查找待审批的反馈
    query = select(HumanFeedback).filter(
        HumanFeedback.workflow_id == workflow_id,
        HumanFeedback.status == "pending"
    )
    result = await db.execute(query)
    feedback = result.scalar_one_or_none()

    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    # 更新反馈
    feedback.action = submit.action
    feedback.comment = submit.comment
    feedback.modified_content = submit.modified_content

    if submit.action == "approve":
        feedback.status = "approved"
    elif submit.action == "reject":
        feedback.status = "rejected"
    elif submit.action == "modify":
        feedback.status = "approved"  # 修改后也算批准

    await db.commit()
    await db.refresh(feedback)

    # 恢复工作流
    controller = get_workflow_controller()
    feedback_data = {
        "action": submit.action,
        "comment": submit.comment,
        "modified_content": submit.modified_content
    }
    await controller.resume_workflow(workflow_id, feedback_data)

    return feedback


@router.get("/feedback/history", response_model=List[HumanFeedbackResponse], summary="获取反馈历史")
async def get_feedback_history(
    workflow_id: Optional[str] = None,
    agent_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取反馈历史"""
    query = select(HumanFeedback)

    if workflow_id:
        query = query.filter(HumanFeedback.workflow_id == workflow_id)
    if agent_id:
        query = query.filter(HumanFeedback.agent_id == agent_id)

    result = await db.execute(query.order_by(HumanFeedback.created_at.desc()))
    feedbacks = result.scalars().all()
    return feedbacks


@router.get("/feedback/{feedback_id}", response_model=HumanFeedbackResponse, summary="获取反馈详情")
async def get_feedback(
    feedback_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取反馈详情"""
    query = select(HumanFeedback).filter(HumanFeedback.id == feedback_id)
    result = await db.execute(query)
    feedback = result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return feedback
