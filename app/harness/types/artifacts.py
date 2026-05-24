# [阶段2] Harness 产出物模型（独立于 agent_runtime.artifacts）
# [Harness: Observability #6]
#
# Artifact 是不可变的工具产出物，贯穿整个 Tool 链:
#   Provenance: 记录来源（哪个 Agent 的哪个 Tool 的哪次调用），用于追溯链
#   Artifact:   具体的产出（SQL、查询结果表、知识片段等），frozen=True 确保不可篡改
#
# Artifact type 枚举（当前使用）:
#   knowledge: search_knowledge 产出的业务知识 / Agent 知识
#   schema:    inspect_schema 产出的 DDL
#   sql:       generate_sql 产出的 SQL 语句
#   table:     execute_sql 产出的查询结果表
#   剩余类型预留给 Phase 3+ (python_code, chart, analysis, report, human_feedback)

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class Provenance(BaseModel):
    """[阶段2] Artifact 来源追溯。"""

    agent_name: str
    tool_name: str
    input_artifact_ids: list[str] = Field(default_factory=list)
    observation_id: str

    model_config = ConfigDict(frozen=True, extra="forbid")


class Artifact(BaseModel):
    """[阶段2] 不可变产出物。"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: Literal[
        "knowledge",
        "schema",
        "sql",
        "table",
        "python_code",
        "chart",
        "analysis",
        "report",
        "human_feedback",
    ]
    content: Any
    provenance: Provenance
    created_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(frozen=True, extra="forbid")

    def summary(self, max_len: int = 80) -> str:
        """[阶段2] 单行摘要供 SSE / 日志使用。"""
        if self.type == "sql":
            sql = str(self.content)
            return sql[:max_len] + "..." if len(sql) > max_len else sql
        if self.type == "table" and isinstance(self.content, dict):
            rows = len(self.content.get("rows", []))
            cols = len(self.content.get("columns", []))
            return f"Table: {rows} rows x {cols} columns"
        if self.type == "knowledge":
            return f"Knowledge: {len(self.content) if isinstance(self.content, list) else 1} item(s)"
        return str(self.content)[:max_len]
