"""
知识召回节点 — RAG 证据检索入口，对齐 Java EvidenceRecallNode

【模块连接】
  上游: intent_recognition → intent == "data_analysis" 时路由而来
  下游: state["recalled_knowledge"], state["recalled_business_terms"], state["recalled_agent_knowledge"]
  路由: → query_rewrite (无条件)

【对齐 Java EvidenceRecallNode 的关键改进】
  1. LLM 先重写查询 (evidence-query-rewrite) 再检索
  2. 分别检索业务知识 (business_terms) 和智能体知识 (agent_knowledge)
  3. 格式化输出含来源归属 [来源: xxx]
  4. FAQ/QA 类型知识特殊处理为 Q/A 格式
"""
from typing import Dict, Any
from ..state import WorkflowState
from ...core.llm import llm_service
from ...services.knowledge_service import KnowledgeService
from ...schemas.knowledge import KnowledgeSearchRequest
from ...core.database import get_db
from ...core.text_utils import clean_code_block
import logging
import json

logger = logging.getLogger(__name__)

# 对齐 Java evidence-query-rewrite.txt
EVIDENCE_QUERY_REWRITE_PROMPT = """你是一个查询重写助手。你的任务是将用户的问题改写为更适合检索知识的独立查询。

规则:
1. 如果用户问题包含多轮对话上下文，将其融合为一个独立的查询
2. 将口语化表达改写为更精确的检索关键词
3. 保持原意，不要添加或删除信息
4. 如果问题本身已经很清晰，直接返回原问题

返回 JSON 格式:
{
  "standalone_query": "重写后的查询",
  "rewritten": false
}
"""


def _extract_standalone_query(llm_output: str) -> str | None:
    """从 LLM 输出中提取独立查询"""
    try:
        text = clean_code_block(llm_output, lang="json")
        data = json.loads(text)
        return data.get("standalone_query")
    except (json.JSONDecodeError, Exception):
        return None


def _build_business_knowledge_content(results: list) -> str:
    """构建业务知识内容 — 对齐 Java buildBusinessKnowledgeContent"""
    if not results:
        return ""
    parts = []
    for r in results:
        parts.append(r.content)
    return "\n".join(parts)


def _build_agent_knowledge_content(results: list) -> str:
    """构建智能体知识内容 — 对齐 Java buildAgentKnowledgeContent

    FAQ/QA 类型特殊处理: [来源: xxx] Q: xxx A: xxx
    DOCUMENT 类型: [来源: title-filename] content
    """
    if not results:
        return ""
    parts = []
    for i, r in enumerate(results):
        source_info = r.title or "知识库"
        if getattr(r, 'source_filename', None):
            source_info += f"-{r.source_filename}"

        if r.type in ("FAQ", "QA"):
            question = getattr(r, 'question', None) or r.title
            parts.append(
                f"{i + 1}. [来源: {source_info}] Q: {question} A: {r.content}"
            )
        else:
            parts.append(
                f"{i + 1}. [来源: {source_info}] {r.content}"
            )
    return "\n".join(parts)


async def knowledge_recall_node(state: WorkflowState) -> Dict[str, Any]:
    """知识召回节点 — 对齐 Java EvidenceRecallNode.apply()

    流程:
      1. LLM 查询重写 (evidence-query-rewrite)
      2. 分别检索业务知识和智能体知识
      3. 格式化输出 (含来源归属)
    """
    user_query = state["user_query"]
    agent_id = state["agent_id"]
    multi_turn = state.get("multi_turn_context", "")

    logger.info(f"[EvidenceRecall] Rewriting query for evidence: {user_query}")

    # Step 1: LLM 查询重写 — 对齐 Java evidence-query-rewrite
    standalone_query = None
    try:
        rewrite_prompt = (
            f"多轮对话上下文: {multi_turn or '(无)'}\n"
            f"用户问题: {user_query}"
        )
        llm_output = await llm_service.chat(EVIDENCE_QUERY_REWRITE_PROMPT, rewrite_prompt)
        standalone_query = _extract_standalone_query(llm_output)
    except Exception as e:
        logger.warning(f"[EvidenceRecall] Query rewrite failed, using original query: {e}")

    search_query = standalone_query or user_query
    logger.info(f"[EvidenceRecall] Standalone query: {search_query}")

    # Step 2: 分别检索业务知识和智能体知识
    business_results = []
    agent_knowledge_results = []

    try:
        async for db in get_db():
            # 检索业务知识 (business_term) — 对齐 Java getDocumentsForAgent(BUSINESS_TERM)
            business_request = KnowledgeSearchRequest(
                query=search_query,
                top_k=5,
                type="BUSINESS_TERM",
                enabled_only=True
            )
            business_results = await KnowledgeService.search_knowledge(db, agent_id, business_request)

            # 检索智能体知识 (agent_knowledge) — 对齐 Java getDocumentsForAgent(AGENT_KNOWLEDGE)
            agent_request = KnowledgeSearchRequest(
                query=search_query,
                top_k=5,
                type="DOCUMENT",
                enabled_only=True
            )
            agent_knowledge_results = await KnowledgeService.search_knowledge(db, agent_id, agent_request)

            # 也检索 FAQ/QA 类型
            for kt in ("FAQ", "QA"):
                faq_request = KnowledgeSearchRequest(
                    query=search_query,
                    top_k=3,
                    type=kt,
                    enabled_only=True
                )
                faq_results = await KnowledgeService.search_knowledge(db, agent_id, faq_request)
                agent_knowledge_results.extend(faq_results)
    except Exception as e:
        logger.error(f"[EvidenceRecall] Search error: {e}")

    # Step 3: 格式化证据内容 — 对齐 Java buildFormattedEvidenceContent
    business_content = _build_business_knowledge_content(business_results)
    agent_content = _build_agent_knowledge_content(agent_knowledge_results)

    all_results = business_results + agent_knowledge_results
    all_docs = [r for r in all_results if r is not None]

    if not all_docs:
        logger.info("[EvidenceRecall] No evidence documents found")
        return {
            "recalled_knowledge": "无",
            "recalled_business_terms": "",
            "recalled_agent_knowledge": "",
            "knowledge_items": [],
        }

    # 使用 PromptHelper 风格模板渲染
    recalled_knowledge = ""
    if business_content:
        recalled_knowledge += f"## 业务知识\n{business_content}"
    if agent_content:
        if recalled_knowledge:
            recalled_knowledge += "\n\n"
        recalled_knowledge += f"## 智能体知识\n{agent_content}"

    # 如果使用了重写查询，把重写结果写入 state 供 query_rewrite 节点参考
    result = {
        "recalled_knowledge": recalled_knowledge,
        "recalled_business_terms": business_content,
        "recalled_agent_knowledge": agent_content,
        "knowledge_items": [
            {
                "id": r.id,
                "title": r.title,
                "content": r.content,
                "type": r.type,
                "distance": r.distance
            }
            for r in all_docs
        ],
    }

    if standalone_query and standalone_query != user_query:
        result["canonical_query"] = standalone_query

    logger.info(f"[EvidenceRecall] Found {len(all_docs)} evidence documents "
                f"(business: {len(business_results)}, agent: {len(agent_knowledge_results)})")
    return result
