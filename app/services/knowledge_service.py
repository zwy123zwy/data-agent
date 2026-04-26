"""
Knowledge Service
知识库服务，包含 CRUD 和向量检索功能
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import List, Optional, Dict, Any
from ..models.knowledge import Knowledge
from ..schemas.knowledge import KnowledgeCreate, KnowledgeUpdate, KnowledgeSearchRequest, KnowledgeSearchResult
from ..core.vector_store import get_vector_store
import logging

logger = logging.getLogger(__name__)


class KnowledgeService:
    """知识库服务"""

    @staticmethod
    def _get_collection_name(agent_id: int) -> str:
        """获取 Agent 的向量集合名称"""
        return f"agent_{agent_id}_knowledge"

    @staticmethod
    async def create_knowledge(
        db: AsyncSession,
        agent_id: int,
        knowledge_data: KnowledgeCreate
    ) -> Knowledge:
        """
        创建知识

        Args:
            db: 数据库会话
            agent_id: Agent ID
            knowledge_data: 知识数据

        Returns:
            创建的知识对象
        """
        # 创建知识记录
        knowledge = Knowledge(
            agent_id=agent_id,
            title=knowledge_data.title,
            content=knowledge_data.content,
            type=knowledge_data.type,
            metadata_=knowledge_data.metadata,
            enabled=knowledge_data.enabled
        )

        db.add(knowledge)
        await db.flush()  # 获取 ID

        # 添加到向量库
        try:
            vector_store = get_vector_store()
            collection_name = KnowledgeService._get_collection_name(agent_id)

            # 使用 title + content 作为向量化文本
            text = f"{knowledge_data.title}\n{knowledge_data.content}"
            embedding_id = f"knowledge_{knowledge.id}"

            await vector_store.add_document(
                collection_name=collection_name,
                doc_id=embedding_id,
                text=text,
                metadata={
                    "knowledge_id": knowledge.id,
                    "type": knowledge_data.type,
                    "title": knowledge_data.title
                }
            )

            # 更新 embedding_id
            knowledge.embedding_id = embedding_id
            await db.commit()
            await db.refresh(knowledge)

            logger.info(f"Created knowledge {knowledge.id} for agent {agent_id}")
            return knowledge

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to create knowledge: {e}")
            raise

    @staticmethod
    async def get_knowledge(db: AsyncSession, knowledge_id: int) -> Optional[Knowledge]:
        """获取知识详情"""
        result = await db.execute(
            select(Knowledge).where(Knowledge.id == knowledge_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_knowledge(
        db: AsyncSession,
        agent_id: int,
        type: Optional[str] = None,
        enabled_only: bool = False,
        skip: int = 0,
        limit: int = 20
    ) -> tuple[List[Knowledge], int]:
        """
        列出知识

        Returns:
            (知识列表, 总数)
        """
        # 构建查询条件
        conditions = [Knowledge.agent_id == agent_id]
        if type:
            conditions.append(Knowledge.type == type)
        if enabled_only:
            conditions.append(Knowledge.enabled == True)

        # 查询总数
        count_result = await db.execute(select(func.count(Knowledge.id)).where(and_(*conditions)))
        total = count_result.scalar() or 0

        # 查询列表
        result = await db.execute(
            select(Knowledge)
            .where(and_(*conditions))
            .order_by(Knowledge.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        knowledge_list = result.scalars().all()

        return list(knowledge_list), total

    @staticmethod
    async def update_knowledge(
        db: AsyncSession,
        knowledge_id: int,
        knowledge_data: KnowledgeUpdate
    ) -> Optional[Knowledge]:
        """更新知识"""
        knowledge = await KnowledgeService.get_knowledge(db, knowledge_id)
        if not knowledge:
            return None

        # 更新字段
        update_data = knowledge_data.model_dump(exclude_unset=True)
        if "metadata" in update_data:
            update_data["metadata_"] = update_data.pop("metadata")
        for field, value in update_data.items():
            setattr(knowledge, field, value)

        # 如果内容或标题变化，更新向量
        if "title" in update_data or "content" in update_data:
            try:
                vector_store = get_vector_store()
                collection_name = KnowledgeService._get_collection_name(knowledge.agent_id)

                text = f"{knowledge.title}\n{knowledge.content}"
                await vector_store.update_document(
                    collection_name=collection_name,
                    doc_id=knowledge.embedding_id,
                    text=text,
                    metadata={
                        "knowledge_id": knowledge.id,
                        "type": knowledge.type,
                        "title": knowledge.title
                    }
                )
            except Exception as e:
                logger.error(f"Failed to update vector: {e}")
                # 继续更新数据库，不因向量更新失败而回滚

        await db.commit()
        await db.refresh(knowledge)

        logger.info(f"Updated knowledge {knowledge_id}")
        return knowledge

    @staticmethod
    async def delete_knowledge(db: AsyncSession, knowledge_id: int) -> bool:
        """删除知识"""
        knowledge = await KnowledgeService.get_knowledge(db, knowledge_id)
        if not knowledge:
            return False

        # 从向量库删除
        try:
            vector_store = get_vector_store()
            collection_name = KnowledgeService._get_collection_name(knowledge.agent_id)
            vector_store.delete_document(collection_name, knowledge.embedding_id)
        except Exception as e:
            logger.error(f"Failed to delete vector: {e}")
            # 继续删除数据库记录

        # 从数据库删除
        await db.delete(knowledge)
        await db.commit()

        logger.info(f"Deleted knowledge {knowledge_id}")
        return True

    @staticmethod
    async def search_knowledge(
        db: AsyncSession,
        agent_id: int,
        search_request: KnowledgeSearchRequest
    ) -> List[KnowledgeSearchResult]:
        """
        向量检索知识

        Args:
            db: 数据库会话
            agent_id: Agent ID
            search_request: 搜索请求

        Returns:
            搜索结果列表
        """
        try:
            vector_store = get_vector_store()
            collection_name = KnowledgeService._get_collection_name(agent_id)

            # 构建过滤条件
            filter_metadata = {}
            if search_request.type:
                filter_metadata["type"] = search_request.type

            # 执行向量检索
            results = await vector_store.search(
                collection_name=collection_name,
                query=search_request.query,
                top_k=search_request.top_k,
                filter_metadata=filter_metadata if filter_metadata else None
            )

            # 获取知识详情
            search_results = []
            for result in results:
                result_metadata = result.get("metadata") or {}
                knowledge_id = result_metadata.get("knowledge_id")
                if knowledge_id is None:
                    logger.warning("Skip vector result without knowledge_id metadata: %s", result)
                    continue
                knowledge = await KnowledgeService.get_knowledge(db, knowledge_id)

                if knowledge and (not search_request.enabled_only or knowledge.enabled):
                    search_results.append(KnowledgeSearchResult(
                        id=knowledge.id,
                        title=knowledge.title,
                        content=knowledge.content,
                        type=knowledge.type,
                        metadata=knowledge.metadata_,
                        distance=result.get("distance")
                    ))

            logger.info(f"Search returned {len(search_results)} results for agent {agent_id}")
            return search_results

        except Exception as e:
            logger.error(f"Failed to search knowledge: {e}")
            raise
