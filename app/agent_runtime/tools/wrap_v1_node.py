# [阶段2] 通用 V1 WorkflowNode → V2 Tool 包装器

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.artifacts import Artifact, Provenance
from app.agent_runtime.context import RuntimeContext
from app.agent_runtime.tools.base import BaseTool, ToolResult
from app.workflows.node_base import WorkflowNode


def _state_from_context(ctx: RuntimeContext, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """[阶段2] 将 RuntimeContext 转为 V1 WorkflowState 初始片段。"""
    state: dict[str, Any] = {
        "agent_id": ctx.agent_id,
        "user_query": ctx.user_query,
        "multi_turn_context": "\n".join(m.content for m in ctx.memory[-6:]),
        "semantic_model_prompt": ctx.semantic_model.get("prompt", ""),
        "sql_generate_count": 0,
        "plan_current_step": 1,
    }
    if extra:
        state.update(extra)
    return state


class V1NodeTool(BaseTool):
    """[阶段2] 包装任意 WorkflowNode 为 ToolResult 契约。"""

    def __init__(
        self,
        tool_name: str,
        node: WorkflowNode,
        agent_name: str = "Explorer",
        artifact_type: str | None = None,
        summary_fn: Any | None = None,
    ) -> None:
        self.name = tool_name
        self._node = node
        self._agent_name = agent_name
        self._artifact_type = artifact_type
        self._summary_fn = summary_fn

    async def run(
        self,
        ctx: RuntimeContext,
        state: dict[str, Any],
        db: AsyncSession,
    ) -> ToolResult:
        merged = _state_from_context(ctx, state)
        output = await self._node.execute(merged)
        state.update(output)
        state.setdefault("semantic_model_prompt", ctx.semantic_model.get("prompt", ""))
        state.setdefault(
            "multi_turn_context",
            "\n".join(m.content for m in ctx.memory[-6:]),
        )

        if self.name == "validate_sql" and output.get("semantic_consistency_result") is False:
            reason = output.get("sql_regenerate_reason") or "语义校验未通过"
            return ToolResult(
                status="error",
                tool_name=self.name,
                summary=str(reason)[:200],
                error_code="SEMANTIC_VALIDATION_FAILED",
                error_severity="retryable",
            )

        if output.get("error"):
            return ToolResult(
                status="error",
                tool_name=self.name,
                summary=str(output["error"])[:200],
                error_code=f"{self.name.upper()}_ERROR",
                error_severity="retryable",
            )

        summary = self._summary_fn(output) if self._summary_fn else f"{self.name} 完成"
        artifacts: list[Artifact] = []
        if self._artifact_type:
            content = output.get(self._artifact_type) or output
            obs_id = str(uuid4())
            artifacts.append(
                Artifact(
                    type=self._artifact_type,  # type: ignore[arg-type]
                    content=content,
                    provenance=Provenance(
                        agent_name=self._agent_name,
                        tool_name=self.name,
                        observation_id=obs_id,
                    ),
                )
            )

        sse = self._node.format_sse(output)
        v1_text = sse.text if sse else summary
        v1_type = sse.text_type if sse else "TEXT"

        return ToolResult(
            status="ok",
            tool_name=self.name,
            data=output,
            summary=summary[:200],
            artifacts=artifacts,
            v1_text=v1_text,
            v1_text_type=v1_type,
        )
