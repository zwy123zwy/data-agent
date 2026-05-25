# [阶段4] ToolDescriptor — Registry 单源，供 Agent 与 tools.available SSE（M4 里程碑）

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ToolDescriptor(BaseModel):
    """[阶段4] 工具元数据；与可执行 BaseTool 实例一一对应。"""

    name: str
    description: str
    parameters_schema: dict = Field(default_factory=dict)
    constraints_summary: str = ""
    requires_datasource: bool = False
    requires_files: bool = False

    model_config = ConfigDict(extra="forbid")
