"""
Knowledge Service — 知识库服务，连接数据库与向量存储的桥梁

【在系统中的地位】
  本服务是 RAG (Retrieval-Augmented Generation) 的核心实现。
  它同时操作两个存储系统:
    1. MySQL 数据库 → 存储知识元数据 (Knowledge 表)
    2. 向量存储     → 存储文本向量 (用于语义检索)

【模块连接】
  上游 (谁调用 KnowledgeService):
    - agent_knowledge_controller.py  → CRUD API: create/update/delete/list/search
    - knowledge_recall.py (workflow) → 工作流中调 search_knowledge() 召回相关知识
    - query_rewrite.py (workflow)    → 工作流中可能使用知识增强查询

  中层 (KnowledgeService 依赖):
    - models/knowledge.py            → Knowledge ORM 模型 (MySQL 表映射)
    - core/vector_store.py           → VectorStore 抽象层 (向量存储接口)
    - schemas/knowledge.py           → Pydantic DTO (请求/响应验证)

  下游 (向量存储实现):
    - core/vector_store.py → SimpleVectorStore (内存) / ES / Redis / PGVector

  Java 对应:
    KnowledgeService ≈ AgentKnowledgeService.java + AgentVectorStoreService.java (简化版)

【RAG 流程 (从用户提问到知识召回)】
  1. 用户提问 → knowledge_recall_node 调用 search_knowledge()
  2. search_knowledge() → vector_store.search() 语义检索
  3. 返回 top_k 条最相关的知识
  4. 知识内容注入 LLM prompt → 提升 SQL/Python 生成质量

【双写一致性】
  create/update 时同时写入 MySQL 和向量库，失败时回滚。
  delete 时先删向量库再删 MySQL (向量库删除失败不阻塞数据库删除)。
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
    """知识库服务 — 同时管理 MySQL Knowledge 表和向量库中的文档

    每个 Agent 在向量库中有独立的 collection: agent_{agent_id}_knowledge
    这样不同 Agent 的知识在向量空间中隔离，避免检索混淆。
    """

    @staticmethod
    def _get_collection_name(agent_id: int) -> str:
        """获取 Agent 的向量集合名称 — 每个 Agent 独立 collection 实现隔离"""
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
