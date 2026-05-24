# [阶段2] search_knowledge — KnowledgeService + LLM 重写，无 workflows 依赖
# [Harness: Tool Access #1] 知识检索工具，召回业务术语与 Agent 知识。
#
# 检索策略（4 类知识，按业务重要性分配 top_k）:
#   BUSINESS_TERM (top_k=5): 业务术语映射（如「库存 → t_ods_stock_movement_di」），
#     这是最重要的知识类型，直接决定 NL2SQL 的准确率
#   DOCUMENT      (top_k=5): 文档类知识，包含业务规则、计算公式等
#   FAQ           (top_k=3): 常见问答，帮助理解用户意图
#   QA            (top_k=3): 历史问答对，提供上下文参考
# 总计最多 16 条知识，按类型分组后拼接为 structured prompt 注入 state["recalled_knowledge"]
#
# 查询重写: 先用 LLM 将用户口语化查询改写为独立检索查询，提升向量检索命中率。
#   例如 "上个月的库存怎么样？" → "库存数据 2026年4月"，去掉指代词和口语表述。

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.harness.tools.base import BaseTool, ToolResult
from app.harness.types.artifacts import Artifact, Provenance
from app.harness.types.context import RuntimeContext
from app.core.llm import llm_service
from app.core.text_utils import clean_code_block
from app.schemas.knowledge import KnowledgeSearchRequest
from app.services.knowledge_service import KnowledgeService

logger = logging.getLogger(__name__)

_EVIDENCE_REWRITE_SYSTEM = """你是一个查询重写助手。将用户问题改写为更适合检索的独立查询。
返回 JSON: {"standalone_query": "...", "rewritten": false}"""


def _extract_standalone_query(llm_output: str) -> str | None:
    try:
        text = clean_code_block(llm_output, lang="json")
        data = json.loads(text)
        return data.get("standalone_query")
    except (json.JSONDecodeError, TypeError, KeyError):
        return None


class HarnessSearchKnowledgeTool(BaseTool):
    """[阶段2] 召回业务知识与 Agent 知识。"""

    name = "search_knowledge"

    async def run(
        self,
        ctx: RuntimeContext,
        state: dict[str, Any],
        db: AsyncSession,
    ) -> ToolResult:
        search_query = ctx.user_query
        try:
            rewrite_prompt = f"用户问题: {ctx.user_query}"
            llm_out = await llm_service.chat(_EVIDENCE_REWRITE_SYSTEM, rewrite_prompt)
            standalone = _extract_standalone_query(llm_out)
            if standalone:
                search_query = standalone
        except Exception as exc:
            logger.warning("[阶段2][search_knowledge] 查询重写失败: %s", exc)

        business_results: list = []
        agent_results: list = []
        try:
            business_results = await KnowledgeService.search_knowledge(
                db,
                ctx.agent_id,
                KnowledgeSearchRequest(
                    query=search_query,
                    top_k=5,
                    type="BUSINESS_TERM",
                    enabled_only=True,
                ),
            )
            agent_results = await KnowledgeService.search_knowledge(
                db,
                ctx.agent_id,
                KnowledgeSearchRequest(
                    query=search_query,
                    top_k=5,
                    type="DOCUMENT",
                    enabled_only=True,
                ),
            )
            for kt in ("FAQ", "QA"):
                agent_results.extend(
                    await KnowledgeService.search_knowledge(
                        db,
                        ctx.agent_id,
                        KnowledgeSearchRequest(
                            query=search_query,
                            top_k=3,
                            type=kt,
                            enabled_only=True,
                        ),
                    )
                )
        except Exception as exc:
            logger.error("[阶段2][search_knowledge] 检索失败: %s", exc)
            return ToolResult(
                status="error",
                tool_name=self.name,
                summary=str(exc)[:200],
                error_code="KNOWLEDGE_RECALL_ERROR",
                error_severity="retryable",
            )

        business_content = "\n".join(r.content for r in business_results if r)
        agent_content = "\n".join(
            f"[{getattr(r, 'title', '知识')}] {r.content}" for r in agent_results if r
        )
        recalled = ""
        if business_content:
            recalled += f"## 业务知识\n{business_content}"
        if agent_content:
            if recalled:
                recalled += "\n\n"
            recalled += f"## 智能体知识\n{agent_content}"
        if not recalled.strip():
            recalled = "无"

        state["recalled_knowledge"] = recalled
        # TODO(H2): multi_turn_context 恒为 ""。H2 后应从 ctx.memory 拼接，
        #   注入查询重写 prompt，提升多轮场景下的检索精度。
        # 答：与 generate_sql/explorer 同源。H2 在 rewrite_prompt 中加「对话历史」段，
        #   避免「它/上次」指代不明导致检索 query 偏离。
        state["multi_turn_context"] = ""

        obs_id = str(uuid4())
        artifacts: list[Artifact] = []
        if recalled != "无":
            artifacts.append(
                Artifact(
                    type="knowledge",
                    content=recalled,
                    provenance=Provenance(
                        agent_name="Explorer",
                        tool_name=self.name,
                        observation_id=obs_id,
                    ),
                )
            )

        return ToolResult(
            status="ok",
            tool_name=self.name,
            data={"recalled_knowledge": recalled},
            summary=f"知识召回完成（{len(artifacts)} 条）",
            artifacts=artifacts,
            v1_text=recalled,
            v1_text_type="TEXT",
        )
