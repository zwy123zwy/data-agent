"""
混合检索服务 — 对齐 Java AgentVectorStoreService

【在系统中的地位】
  本服务实现 RAG 的多路检索 + 融合排序。单独使用向量检索或关键词检索
  都有缺陷，混合检索结合两者优势:
    - 向量检索: 语义理解强，能匹配同义词/近义词
    - 关键词检索: 精确匹配强，不会漏掉专有名词

【模块连接】
  上游 (谁调用 HybridSearchService):
    - workflows/nodes/knowledge_recall.py → 工作流中召回相关知识
    - services/knowledge_service.py       → (可选) 高级知识检索

  被依赖:
    - core/vector_store.py  → 向量检索 + 关键词检索的底层实现
    - core/config.py        → vector_store.* 配置参数

  Java 对应:
    HybridSearchService ≈ AgentVectorStoreService.java 中的 hybridSearch() 方法

【RRF 融合算法】
  RRF (Reciprocal Rank Fusion) 是业界标准的融合排序算法:
    RRF_score(d) = Σ 1 / (k + rank_i(d))
  其中:
    - d: 候选文档
    - k: 常数 (默认 60)，防止低排名文档得分过高
    - rank_i(d): 文档 d 在第 i 个检索结果中的排名

  相比简单的 WeightedAverage，RRF 不需要分数归一化，对排名差异不敏感。
"""
from typing import List, Dict, Any, Optional
from ..core.config import settings
import logging

logger = logging.getLogger(__name__)


class HybridSearchService:
    """混合检索服务 — 对齐 Java AgentVectorStoreService.hybridSearch()"""

    def __init__(self):
        self.topk_limit = settings.vector_store.default_topk_limit
        self.similarity_threshold = settings.vector_store.default_similarity_threshold
        self.hybrid_enabled = settings.vector_store.hybrid_search_enabled

    async def hybrid_search(
        self,
        query: str,
        topk: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """混合检索 — 对齐 Java hybridSearch()

        策略:
        1. 向量检索: 基于 embedding 相似度
        2. 关键词检索: 基于 BM25 或简单文本匹配
        3. RRF (Reciprocal Rank Fusion) 融合排序

        Args:
            query: 查询文本
            topk: 返回条数（默认使用配置）
            similarity_threshold: 相似度阈值
            metadata_filter: 元数据过滤条件

        Returns:
            排序后的检索结果列表
        """
        k = topk or self.topk_limit
        threshold = similarity_threshold or self.similarity_threshold

        results = []

        try:
            # 向量检索
            vector_results = await self._vector_search(query, k * 2, threshold, metadata_filter)

            # 关键词检索
            keyword_results = await self._keyword_search(query, k, metadata_filter)

            # RRF 融合
            results = self._rrf_fusion(vector_results, keyword_results, k)

            logger.info(
                f"[HybridSearch] Query: {query[:50]}..., "
                f"vector={len(vector_results)}, keyword={len(keyword_results)}, "
                f"fused={len(results)}"
            )

        except Exception as e:
            logger.error(f"[HybridSearch] Error: {e}")
            # 降级: 仅向量检索
            results = await self._vector_search(query, k, threshold, metadata_filter)

        return results

    async def _vector_search(
        self,
        query: str,
        topk: int,
        threshold: float,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """向量检索 — 对齐 Java vectorSearch()"""
        from ..core.vector_store import get_vector_store
        store = get_vector_store()
        if not store:
            logger.warning("[HybridSearch] No vector store available")
            return []
        try:
            results = await store.search(
                query=query,
                top_k=topk,
                similarity_threshold=threshold,
                metadata_filter=metadata_filter,
            )
            # 为 RRF 标记来源
            for r in results:
                r["_source"] = "vector"
            return results
        except Exception as e:
            logger.error(f"[HybridSearch] Vector search error: {e}")
            return []

    async def _keyword_search(
        self,
        query: str,
        topk: int,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """关键词检索 — 对齐 Java keywordSearch() (BM25 / 简单分词匹配)"""
        from ..core.vector_store import get_vector_store
        store = get_vector_store()
        if not store:
            return []

        try:
            results = await store.keyword_search(
                query=query,
                top_k=topk,
                metadata_filter=metadata_filter,
            )
            for r in results:
                r["_source"] = "keyword"
            return results
        except Exception as e:
            logger.warning(f"[HybridSearch] Keyword search error: {e}")
            return []

    def _rrf_fusion(
        self,
        vector_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]],
        k: int,
        rrf_k: int = 60,
    ) -> List[Dict[str, Any]]:
        """RRF (Reciprocal Rank Fusion) 融合排序 — 对齐 Java RRFStrategy

        RRF_score(d) = Σ 1 / (k + rank_i(d))
        """
        scores: Dict[str, float] = {}
        docs: Dict[str, Dict[str, Any]] = {}

        for rank, doc in enumerate(vector_results, start=1):
            doc_id = doc.get("id", str(rank))
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (rrf_k + rank)
            docs[doc_id] = doc

        for rank, doc in enumerate(keyword_results, start=1):
            doc_id = doc.get("id", str(rank + 10000))
            keyword_id = doc.get("text", "")
            # 去重: 如果向量结果中有相似内容，合并分数
            matched = False
            for vid, vdoc in docs.items():
                if vdoc.get("text", "") == keyword_id:
                    scores[vid] = scores.get(vid, 0.0) + 1.0 / (rrf_k + rank)
                    matched = True
                    break
            if not matched:
                scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (rrf_k + rank)
                docs[doc_id] = doc

        # 按 RRF 分数排序
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        return [docs[doc_id] for doc_id in sorted_ids[:k]]


# 全局实例
_hybrid_search: Optional[HybridSearchService] = None


def get_hybrid_search_service() -> HybridSearchService:
    global _hybrid_search
    if _hybrid_search is None:
        _hybrid_search = HybridSearchService()
    return _hybrid_search
