"""AgentPresetQuestion 服务 — 对齐 Java AgentPresetQuestionService"""
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from ..models.agent_preset_question import AgentPresetQuestion


class AgentPresetQuestionService:
    """预设问题管理服务"""

    @staticmethod
    async def find_all_by_agent_id(db: AsyncSession, agent_id: int) -> List[AgentPresetQuestion]:
        """获取 Agent 的所有预设问题 — 对齐 Java findAllByAgentId"""
        result = await db.execute(
            select(AgentPresetQuestion)
            .where(AgentPresetQuestion.agent_id == agent_id)
            .order_by(AgentPresetQuestion.sort_order.asc())
        )
        return result.scalars().all()

    @staticmethod
    async def batch_save(
        db: AsyncSession, agent_id: int, questions_data: List[dict]
    ) -> List[AgentPresetQuestion]:
        """批量保存预设问题 — 对齐 Java batchSave"""
        # 删除旧的预设问题
        await db.execute(
            delete(AgentPresetQuestion).where(AgentPresetQuestion.agent_id == agent_id)
        )

        # 批量创建新问题
        saved = []
        for i, data in enumerate(questions_data):
            question = AgentPresetQuestion(
                agent_id=agent_id,
                question=data.get("question", ""),
                sort_order=data.get("sort_order", i),
                is_active=data.get("is_active", True),
            )
            db.add(question)
            saved.append(question)

        await db.commit()
        return saved

    @staticmethod
    async def delete_by_id(db: AsyncSession, question_id: int) -> bool:
        """删除预设问题 — 对齐 Java deleteById"""
        result = await db.execute(
            delete(AgentPresetQuestion).where(AgentPresetQuestion.id == question_id)
        )
        await db.commit()
        return result.rowcount > 0
