"""
向量存储服务
封装 Chroma 向量数据库操作
"""
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from .config import settings
import logging

logger = logging.getLogger(__name__)


class VectorStore:
    """向量存储服务（使用 Chroma）"""

    def __init__(self):
        """初始化 Chroma 客户端"""
        # 使用持久化存储
        self.client = chromadb.Client(Settings(
            persist_directory="./chroma_db",
            anonymized_telemetry=False
        ))

        # 初始化 OpenAI 客户端用于生成 Embedding
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
