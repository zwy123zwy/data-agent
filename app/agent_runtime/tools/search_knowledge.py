# [阶段1] search_knowledge Tool — 包装 V1 KnowledgeRecallNode

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.artifacts import Artifact, Provenance
from app.agent_runtime.context import RuntimeContext
from app.agent_runtime.tools.base import BaseTool, ToolResult
from app.workflows.nodes.knowledge_recall import knowledge_recall_node


class SearchKnowledgeTool(BaseTool):
    """[阶段1] 召回业务知识与 Agent 知识，供后续 SQL 生成使用。"""

    name = "search_knowledge"

    async def run(
        self,
        ctx: RuntimeContext,
        state: dict[str, Any],
        db: AsyncSession,
    ) -> ToolResult:
        merged = {**state, "agent_id": ctx.agent_id, "user_query": ctx.user_query}
        if ctx.memory:
            merged["multi_turn_context"] = "\n".join(
                f"{m.role}: {m.content}" for m in ctx.memory[-6:]
            )

        output = await knowledge_recall_node.execute(merged)
        state.update(output)

        knowledge = output.get("recalled_knowledge", "")
        obs_id = str(uuid4())
        artifacts: list[Artifact] = []
        if knowledge and knowledge != "无":
            artifacts.append(
                Artifact(
                    type="knowledge",
                    content=knowledge,
                    provenance=Provenance(
                        agent_name="Explorer",
                        tool_name=self.name,
                        observation_id=obs_id,
                    ),
                )
            )

        if output.get("error"):
            return ToolResult(
                status="error",
                tool_name=self.name,
                summary=str(output["error"])[:200],
                error_code="KNOWLEDGE_RECALL_ERROR",
                error_severity="retryable",
            )

        return ToolResult(
            status="ok",
            tool_name=self.name,
            data=output,
            summary=f"知识召回完成（{len(artifacts)} 条证据）",
            artifacts=artifacts,
            v1_text=knowledge if isinstance(knowledge, str) else json.dumps(knowledge, ensure_ascii=False),
            v1_text_type="TEXT",
        )
