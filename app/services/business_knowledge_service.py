"""BusinessKnowledgeService — 对齐 Java BusinessKnowledgeService"""
import logging
from typing import Optional, List
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.business_knowledge import BusinessKnowledge
from ..schemas.business_knowledge import BusinessKnowledgeCreateRequest, BusinessKnowledgeUpdateRequest, BusinessKnowledgeResponse
from ..core.vector_store import get_vector_store

logger = logging.getLogger(__name__)


class BusinessKnowledgeService:

    @staticmethod
    def _get_collection_name(agent_id: int) -> str:
        return f"agent_{agent_id}_business_knowledge"

    @staticmethod
    def _build_embedding_text(business_term: str, synonyms: Optional[str], description: Optional[str]) -> str:
        parts = [business_term]
        if synonyms:
            parts.append(synonyms)
        if description:
            parts.append(description)
        return "\n".join(parts)

    @staticmethod
    async def list_by_agent(
        db: AsyncSession, agent_id: int, keyword: Optional[str] = None
    ) -> List[BusinessKnowledgeResponse]:
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

        # 向量化
        try:
            vs = get_vector_store()
            text = BusinessKnowledgeService._build_embedding_text(
                dto.business_term, dto.synonyms, dto.description
            )
            await vs.add_document(
                collection_name=BusinessKnowledgeService._get_collection_name(dto.agent_id),
                doc_id=f"bk_{bk.id}",
                text=text,
                metadata={"bk_id": bk.id, "business_term": dto.business_term}
            )
            bk.embedding_status = "COMPLETED"
            logger.info("BusinessKnowledge %d embedded successfully", bk.id)
        except Exception as e:
            bk.embedding_status = "FAILED"
            bk.error_msg = str(e)
            logger.error("BusinessKnowledge %d embedding failed: %s", bk.id, e)

        await db.commit()
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
        term_changed = "business_term" in update_data
        desc_changed = "description" in update_data
        syn_changed = "synonyms" in update_data

        for key, value in update_data.items():
            setattr(bk, key, value)

        # 内容变化时更新向量
        if term_changed or desc_changed or syn_changed:
            try:
                vs = get_vector_store()
                text = BusinessKnowledgeService._build_embedding_text(
                    bk.business_term, bk.synonyms, bk.description
                )
                await vs.update_document(
                    collection_name=BusinessKnowledgeService._get_collection_name(bk.agent_id),
                    doc_id=f"bk_{bk.id}",
                    text=text,
                    metadata={"bk_id": bk.id, "business_term": bk.business_term}
                )
                bk.embedding_status = "COMPLETED"
            except Exception as e:
                bk.embedding_status = "FAILED"
                bk.error_msg = str(e)
                logger.error("BusinessKnowledge %d update embedding failed: %s", bk.id, e)

        await db.commit()
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

        # 删除向量
        try:
            vs = get_vector_store()
            vs.delete_document(
                BusinessKnowledgeService._get_collection_name(bk.agent_id),
                f"bk_{bk.id}"
            )
        except Exception as e:
            logger.error("Failed to delete vector for bk %d: %s", bk.id, e)

        bk.is_deleted = 1
        bk.is_resource_cleaned = 1
        await db.commit()
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
        await db.commit()
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

        try:
            vs = get_vector_store()
            text = BusinessKnowledgeService._build_embedding_text(
                bk.business_term, bk.synonyms, bk.description
            )
            await vs.add_document(
                collection_name=BusinessKnowledgeService._get_collection_name(bk.agent_id),
                doc_id=f"bk_{bk.id}",
                text=text,
                metadata={"bk_id": bk.id, "business_term": bk.business_term}
            )
            bk.embedding_status = "COMPLETED"
            bk.error_msg = None
            logger.info("BusinessKnowledge %d retry embedding succeeded", bk.id)
        except Exception as e:
            bk.embedding_status = "FAILED"
            bk.error_msg = str(e)
            logger.error("BusinessKnowledge %d retry embedding failed: %s", bk.id, e)

        await db.commit()
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
        rows = list(result.scalars().all())
        if not rows:
            return True

        vs = get_vector_store()
        collection_name = BusinessKnowledgeService._get_collection_name(agent_id)

        for bk in rows:
            try:
                text = BusinessKnowledgeService._build_embedding_text(
                    bk.business_term, bk.synonyms, bk.description
                )
                await vs.add_document(
                    collection_name=collection_name,
                    doc_id=f"bk_{bk.id}",
                    text=text,
                    metadata={"bk_id": bk.id, "business_term": bk.business_term}
                )
                bk.embedding_status = "COMPLETED"
                bk.error_msg = None
            except Exception as e:
                bk.embedding_status = "FAILED"
                bk.error_msg = str(e)
                logger.error("BusinessKnowledge %d refresh embedding failed: %s", bk.id, e)

        await db.commit()
        logger.info("Refreshed vector store for agent %d: %d items", agent_id, len(rows))
        return True
