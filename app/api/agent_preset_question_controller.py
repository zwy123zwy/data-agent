"""AgentPresetQuestion API — 对齐 Java AgentPresetQuestionController"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any

from ..core.database import get_db
from ..services.agent_preset_question_service import AgentPresetQuestionService
from ..services.agent_service import AgentService
from ..schemas.agent_preset_question import AgentPresetQuestionResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["Agent预设问题"])


@router.get(
    "/{agent_id}/preset-questions",
    response_model=List[AgentPresetQuestionResponse],
    summary="获取预设问题列表",
)
async def get_preset_questions(agent_id: int, db: AsyncSession = Depends(get_db)):
    """获取 Agent 的预设问题列表 — 对齐 Java getPresetQuestions"""
    agent = await AgentService.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    questions = await AgentPresetQuestionService.find_all_by_agent_id(db, agent_id)
    return questions


@router.post(
    "/{agent_id}/preset-questions",
    summary="批量保存预设问题",
)
async def save_preset_questions(
    agent_id: int,
    questions_data: List[Dict[str, Any]] = Body(..., description="预设问题列表 [{question, is_active?, sort_order?}]"),
    db: AsyncSession = Depends(get_db),
):
    """批量保存预设问题（先删后增）— 对齐 Java savePresetQuestions"""
    agent = await AgentService.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    try:
        await AgentPresetQuestionService.batch_save(db, agent_id, questions_data)
        return {"success": True, "message": "预设问题保存成功", "data": None}
    except Exception as e:
        logger.error(f"Error saving preset questions for agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=f"保存预设问题失败: {str(e)}")


@router.delete(
    "/{agent_id}/preset-questions/{question_id}",
    summary="删除预设问题",
)
async def delete_preset_question(
    agent_id: int,
    question_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除指定预设问题 — 对齐 Java deletePresetQuestion"""
    agent = await AgentService.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    try:
        success = await AgentPresetQuestionService.delete_by_id(db, question_id)
        if not success:
            raise HTTPException(status_code=404, detail="预设问题不存在")
        return {"success": True, "message": "预设问题删除成功", "data": None}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting preset question {question_id}: {e}")
        raise HTTPException(status_code=500, detail=f"删除预设问题失败: {str(e)}")
