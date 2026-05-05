"""BusinessKnowledgeService — 对齐 Java BusinessKnowledgeService"""
from typing import Optional, List
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.business_knowledge import BusinessKnowledge
from ..schemas.business_knowledge import BusinessKnowledgeCreateRequest, BusinessKnowledgeUpdateRequest, BusinessKnowledgeResponse


class BusinessKnowledgeService:

    @staticmethod
    async def list_by_agent(
        db: AsyncSession, agent_id: int, keyword: Optional[str] = None
    ) -> List[BusinessKnowledgeResponse]:
        """列出 Agent 的业务知识，支持关键词搜索"""
        query = select(BusinessKnowledge).where(
            and_(
                BusinessKnowledge.agent_id == agent_id,
                BusinessKnowledge.is_deleted == 0,
            )
        )
        if keyword:
            query = query.where(
                BusinessKnowledge.business_term.like(f"%{keyword}%")
            )
        query = query.order_by(BusinessKnowledge.created_time.desc())
        result = await db.execute(query)
        rows = result.scalars().all()
        return [BusinessKnowledgeResponse.model_validate(r) for r in rows]

    @staticmethod
    async def get_by_id(db: AsyncSession, id: int) -> Optional[BusinessKnowledgeResponse]:
        result = await db.execute(
            select(BusinessKnowledge).where(
                and_(BusinessKnowledge.id == id, BusinessKnowledge.is_deleted == 0)
            )
        )
        row = result.scalar_one_or_none()
        return BusinessKnowledgeResponse.model_validate(row) if row else None

    @staticmethod
    async def create(db: AsyncSession, dto: BusinessKnowledgeCreateRequest) -> BusinessKnowledgeResponse:
        bk = BusinessKnowledge(
            business_term=dto.business_term,
            description=dto.description,
            synonyms=dto.synonyms,
            agent_id=dto.agent_id,
            is_recall=dto.is_recall,
        )
        db.add(bk)
        await db.flush()
        await db.refresh(bk)
        return BusinessKnowledgeResponse.model_validate(bk)

    @staticmethod
    async def update(db: AsyncSession, id: int, dto: BusinessKnowledgeUpdateRequest) -> Optional[BusinessKnowledgeResponse]:
        result = await db.execute(
            select(BusinessKnowledge).where(
                and_(BusinessKnowledge.id == id, BusinessKnowledge.is_deleted == 0)
            )
        )
        bk = result.scalar_one_or_none()
        if not bk:
            return None
        update_data = dto.model_dump(exclude_unset=True, by_alias=False)
        for key, value in update_data.items():
            setattr(bk, key, value)
        await db.flush()
        await db.refresh(bk)
        return BusinessKnowledgeResponse.model_validate(bk)

    @staticmethod
    async def delete(db: AsyncSession, id: int) -> bool:
        result = await db.execute(
            select(BusinessKnowledge).where(
                and_(BusinessKnowledge.id == id, BusinessKnowledge.is_deleted == 0)
            )
        )
        bk = result.scalar_one_or_none()
        if not bk:
            return False
        bk.is_deleted = 1
        await db.flush()
        return True

    @staticmethod
    async def set_recall(db: AsyncSession, id: int, is_recall: int) -> bool:
        result = await db.execute(
            select(BusinessKnowledge).where(
                and_(BusinessKnowledge.id == id, BusinessKnowledge.is_deleted == 0)
            )
        )
        bk = result.scalar_one_or_none()
        if not bk:
            return False
        bk.is_recall = is_recall
        await db.flush()
        return True

    @staticmethod
    async def retry_embedding(db: AsyncSession, id: int) -> bool:
        result = await db.execute(
            select(BusinessKnowledge).where(
                and_(BusinessKnowledge.id == id, BusinessKnowledge.is_deleted == 0)
            )
        )
        bk = result.scalar_one_or_none()
        if not bk:
            return False
        bk.embedding_status = "PENDING"
        bk.error_msg = None
        await db.flush()
        return True

    @staticmethod
    async def refresh_vector_store(db: AsyncSession, agent_id: int) -> bool:
        result = await db.execute(
            select(BusinessKnowledge).where(
                and_(
                    BusinessKnowledge.agent_id == agent_id,
                    BusinessKnowledge.is_deleted == 0,
                )
            )
        )
        for bk in result.scalars().all():
            bk.embedding_status = "PENDING"
            bk.error_msg = None
        await db.flush()
        return True
