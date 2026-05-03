"""
向量存储服务 — RAG 的语义检索引擎

【在系统中的地位】
  本服务是 RAG (Retrieval-Augmented Generation) 的底层引擎。
  它将文本转为向量 (embedding)，存入 Chroma 向量数据库，
  查询时将用户问题转为向量，通过余弦相似度找到最相关的知识。

【模块连接】
  上游 (谁调用 VectorStore):
    - services/knowledge_service.py → 唯一调用者
      - add_document()     → 创建知识时向量化并存储
      - update_document()  → 修改知识时更新向量
      - delete_document()  → 删除知识时移除向量
      - search()           → 用户查询时语义检索相关知识

  被依赖:
    - openai.AsyncOpenAI → 调用 Embedding API (text-embedding-3-small)
    - chromadb           → 向量存储引擎 (Chroma)

  Java 对应:
    VectorStore ≈ AgentVectorStoreService.java (简化版)
    Chroma 类似 Java 端的 SimpleVectorStore / PGVector

【向量检索流程】
  1. 用户提问 "查询本月销售额"
  2. generate_embedding("查询本月销售额") → [0.123, -0.456, ...] (1536维)
  3. collection.query(query_embeddings=[...], n_results=5)
  4. 返回 5 条最相似的知识文档 (按余弦距离排序)

【Chroma vs 其他向量库】
  - Chroma: 本地持久化，开箱即用 (当前选择)
  - PGVector: PostgreSQL 插件，与业务库合并 (Java 端默认)
  - Elasticsearch: 分布式，适合大规模
  - Redis: 内存级速度
"""
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from .config import settings
import logging

logger = logging.getLogger(__name__)


class VectorStore:
    """向量存储服务 — Chroma + OpenAI Embedding

    存储结构:
      Chroma 中的 collection (集合) 对应一个 Agent 的知识库
      collection 名: agent_{agent_id}_knowledge
      collection 中的每个 document 对应一条 Knowledge 记录
    """

    def __init__(self):
        """初始化 Chroma 客户端 + OpenAI Embedding 客户端"""
        self.client = chromadb.Client(Settings(
            persist_directory="./chroma_db",
            anonymized_telemetry=False
        ))

        self.openai_client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base
        )

        logger.info("VectorStore initialized with Chroma")

    async def generate_embedding(self, text: str) -> List[float]:
        """
        生成文本的 Embedding 向量

        Args:
            text: 输入文本

        Returns:
            Embedding 向量
        """
        try:
            response = await self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    def get_or_create_collection(self, collection_name: str) -> chromadb.Collection:
        """
        获取或创建集合

        Args:
            collection_name: 集合名称

        Returns:
            Chroma 集合对象
        """
        try:
            collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}  # 使用余弦相似度
            )
            return collection
        except Exception as e:
            logger.error(f"Failed to get/create collection {collection_name}: {e}")
            raise

    async def add_document(
        self,
        collection_name: str,
        doc_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        添加文档到向量库

        Args:
            collection_name: 集合名称
            doc_id: 文档 ID
            text: 文档文本
            metadata: 元数据

        Returns:
            文档 ID
        """
        try:
            # 生成 Embedding
            embedding = await self.generate_embedding(text)

            # 获取集合
            collection = self.get_or_create_collection(collection_name)

            # 添加文档
            collection.add(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[metadata] if metadata else None
            )

            logger.info(f"Added document {doc_id} to collection {collection_name}")
            return doc_id
        except Exception as e:
            logger.error(f"Failed to add document: {e}")
            raise

    async def update_document(
        self,
        collection_name: str,
        doc_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        更新文档

        Args:
            collection_name: 集合名称
            doc_id: 文档 ID
            text: 新文本
            metadata: 新元数据
        """
        try:
            # 生成新的 Embedding
            embedding = await self.generate_embedding(text)

            # 获取集合
            collection = self.get_or_create_collection(collection_name)

            # 更新文档
            collection.update(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[metadata] if metadata else None
            )

            logger.info(f"Updated document {doc_id} in collection {collection_name}")
        except Exception as e:
            logger.error(f"Failed to update document: {e}")
            raise

    def delete_document(self, collection_name: str, doc_id: str):
        """
        删除文档

        Args:
            collection_name: 集合名称
            doc_id: 文档 ID
        """
        try:
            collection = self.get_or_create_collection(collection_name)
            collection.delete(ids=[doc_id])
            logger.info(f"Deleted document {doc_id} from collection {collection_name}")
        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            raise

    async def search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        向量检索

        Args:
            collection_name: 集合名称
            query: 查询文本
            top_k: 返回结果数量
            filter_metadata: 元数据过滤条件

        Returns:
            检索结果列表
        """
        try:
            # 生成查询向量
            query_embedding = await self.generate_embedding(query)

            # 获取集合
            collection = self.get_or_create_collection(collection_name)

            # 执行检索
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=filter_metadata
            )

            # 格式化结果
            formatted_results = []
            if results["ids"] and results["ids"][0]:
                for i in range(len(results["ids"][0])):
                    formatted_results.append({
                        "id": results["ids"][0][i],
                        "document": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else None,
                        "distance": results["distances"][0][i] if results.get("distances") else None
                    })

            logger.info(f"Search in {collection_name} returned {len(formatted_results)} results")
            return formatted_results
        except Exception as e:
            logger.error(f"Failed to search: {e}")
            raise

    def delete_collection(self, collection_name: str):
        """
        删除集合

        Args:
            collection_name: 集合名称
        """
        try:
            self.client.delete_collection(name=collection_name)
            logger.info(f"Deleted collection {collection_name}")
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            raise


# 全局单例
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """获取向量存储服务单例"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
