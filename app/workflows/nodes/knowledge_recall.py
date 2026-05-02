"""
知识召回节点（Knowledge Recall Node）
从向量数据库检索相关知识
"""
from typing import Dict, Any
from ..state import AgentState
from ..services.knowledge_service import KnowledgeService
from ..schemas.knowledge import KnowledgeSearchRequest
from ..core.database import get_db
import logging

logger = logging.getLogger(__name__)


async def knowledge_recall_node(state: AgentState) -> Dict[str, Any]:
    """
    知识召回节点

    从向量数据库检索与用户查询相关的知识

    Args:
        state: 工作流状态

    Returns:
        更新后的状态
    """
    user_query = state["user_query"]
    agent_id = state["agent_id"]

    logger.info(f"[KnowledgeRecall] Recalling knowledge for query: {user_query}")

    try:
        # 获取数据库会话
        async for db in get_db():
            # 构建搜索请求
            search_request = KnowledgeSearchRequest(
                query=user_query,
                top_k=5,
                enabled_only=True
            )

            # 执行向量检索
            results = await KnowledgeService.search_knowledge(db, agent_id, search_request)

            # 格式化知识为文本
            knowledge_text = ""
            if results:
                knowledge_text = "相关知识:\n"
                for i, result in enumerate(results, 1):
                    knowledge_text += f"\n{i}. {result.title}\n"
                    knowledge_text += f"   类型: {result.type}\n"
                    knowledge_text += f"   内容: {result.content}\n"
                    if result.distance is not None:
                        knowledge_text += f"   相似度: {1 - result.distance:.2f}\n"

            logger.info(f"[KnowledgeRecall] Found {len(results)} relevant knowledge items")

            return {
                "recalled_knowledge": knowledge_text,
                "knowledge_items": [
                    {
                        "id": r.id,
                        "title": r.title,
                        "content": r.content,
                        "type": r.type,
                        "distance": r.distance
                    }
                    for r in results
                ]
            }

    except Exception as e:
        logger.error(f"[KnowledgeRecall] Error: {e}")
        return {
            "recalled_knowledge": "",
            "knowledge_items": []
        }
