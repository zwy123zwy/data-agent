# [阶段4] ExplorerState — Tool 间共享状态（M4.2 替代裸 dict）

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.harness.types.context import RuntimeContext


class ExplorerState(BaseModel):
    """[阶段4] Agent 循环内 Tool 读写的工作流状态。"""

    model_config = ConfigDict(extra="allow")

    semantic_model_prompt: str = ""
    multi_turn_context: str = ""
    recalled_knowledge: str = ""
    schema: str = ""
    schema_info: dict[str, Any] = Field(default_factory=dict)
    db_dialect_type: str = ""
    query_plan: Any = None
    plan_current_step: int = 1
    generated_sql: str = ""
    sql_regenerate_reason: dict[str, Any] | None = None
    sql_generate_count: int = 0
    sql_result: list[Any] = Field(default_factory=list)

    @classmethod
    def from_context(cls, ctx: RuntimeContext) -> ExplorerState:
        """[阶段4] 从 RuntimeContext 初始化。"""
        return cls(
            semantic_model_prompt=ctx.semantic_model.get("prompt", ""),
            multi_turn_context="",
        )

    def as_tool_state(self) -> dict[str, Any]:
        """[阶段4] 供 BaseTool.run 使用的可变 dict（原地更新）。"""
        return self.model_dump(mode="python", by_alias=True)

    @classmethod
    def from_tool_state(cls, data: dict[str, Any]) -> ExplorerState:
        """[阶段4] Tool 执行后回写。"""
        return cls.model_validate(data)

    def has_sql_result(self) -> bool:
        """[阶段4] 是否已有可回答的查询结果。"""
        return bool(self.sql_result)
