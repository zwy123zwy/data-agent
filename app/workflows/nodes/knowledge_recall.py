"""
知识召回节点 — 对齐 Java EvidenceRecallNode

Harness 角色: RAG 证据检索入口。LLM 重写查询后进行混合检索（业务知识 + 智能体知识），
格式化证据内容供后续节点使用。

I/O 契约:
  requires: user_query, agent_id, multi_turn_context
  provides: recalled_knowledge, recalled_business_terms, recalled_agent_knowledge, knowledge_items
"""
from typing import Dict, Any
from ..state import WorkflowState
from ..node_base import WorkflowNode, SSEPayload
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


class KnowledgeRecallNode(WorkflowNode):
    """知识召回 — 对齐 Java EvidenceRecallNode.apply()

    RAG 证据检索入口。流程:
      1. LLM 查询重写 (evidence-query-rewrite)
      2. 分别检索业务知识和智能体知识
      3. 格式化输出 (含来源归属)
    """

    name = "knowledge_recall"
    description = "RAG 证据检索 — 混合搜索业务知识+智能体知识，格式化含来源归属"
    requires = ["user_query", "agent_id", "multi_turn_context"]
    provides = ["recalled_knowledge", "recalled_business_terms", "recalled_agent_knowledge", "knowledge_items"]
    applicable_data_sources = ["*"]

    async def execute(self, state: WorkflowState) -> Dict[str, Any]:
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
                # 检索业务知识 (business_term)
                business_request = KnowledgeSearchRequest(
                    query=search_query,
                    top_k=5,
                    type="BUSINESS_TERM",
                    enabled_only=True
                )
                business_results = await KnowledgeService.search_knowledge(db, agent_id, business_request)

                # 检索智能体知识 (agent_knowledge)
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

        # Step 3: 格式化证据内容
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

    def format_sse(self, output: Dict[str, Any]) -> SSEPayload | None:
        knowledge_items = output.get("knowledge_items", [])
        recalled = output.get("recalled_knowledge", "")
        count = len(knowledge_items)
        if count:
            lines = [f"正在检索相关知识...已找到 {count} 条相关证据文档"]
            for idx, item in enumerate(knowledge_items[:3]):
                content_preview = (item.get("content") or "")[:100]
                lines.append(f"证据{idx + 1}: {content_preview}...")
            text = "\n".join(lines)
        elif recalled and recalled != "无":
            text = f"正在检索相关知识...\n{recalled[:500]}"
        else:
            text = "正在检索相关知识...未找到证据文档"
        # [旧代码] 不声明 Agent/Tool
        # return SSEPayload(text=text, text_type="TEXT", metrics_delta={"knowledge_count": count})
        # V3.0: 声明 Explorer 归属 + search_knowledge tool
        return SSEPayload(
            text=text, text_type="TEXT",
            metrics_delta={"knowledge_count": count},
            agent_name="Explorer", tool_name="search_knowledge",
            tool_status="done", tool_summary=f"召回 {count} 条知识",
        )


# LangGraph 兼容实例
knowledge_recall_node = KnowledgeRecallNode()
