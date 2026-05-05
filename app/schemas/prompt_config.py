"""PromptConfig Pydantic Schemas — 对齐 Java PromptConfigDTO / UserPromptConfig"""
from pydantic import BaseModel, Field, ConfigDict, computed_field
from typing import Optional
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
# 基类
# ═══════════════════════════════════════════════════════════════

class PromptConfigBase(BaseModel):
    """Prompt 配置公共字段 — 对齐 Java UserPromptConfig"""
    name: str = Field(..., max_length=200, description="配置名称")
    prompt_type: str = Field(..., alias="promptType", max_length=50, description="提示词类型")
    agent_id: Optional[int] = Field(None, alias="agentId", description="Agent ID (null=全局)")
    enabled: int = Field(1, description="是否启用: 0/1")
    description: Optional[str] = Field(None, description="配置描述")
    priority: int = Field(0, description="优先级")
    display_order: int = Field(0, alias="displayOrder", description="显示顺序")
    creator: Optional[str] = Field(None, max_length=100, description="创建者")

    model_config = ConfigDict(populate_by_name=True)


# ═══════════════════════════════════════════════════════════════
# Request
# ═══════════════════════════════════════════════════════════════

class PromptConfigSaveRequest(PromptConfigBase):
    """创建/更新配置 — 对齐 Java PromptConfigDTO (POST /save)"""
    id: Optional[str] = Field(None, description="配置ID (有则更新，无则新建)")
    optimization_prompt: str = Field(..., alias="optimizationPrompt", description="自定义系统提示词")


class PromptConfigUpdateRequest(BaseModel):
    """更新 Prompt 配置"""
    name: Optional[str] = Field(None, max_length=200, description="配置名称")
    optimization_prompt: Optional[str] = Field(None, alias="optimizationPrompt", description="系统提示词")
    enabled: Optional[int] = Field(None, description="是否启用: 0/1")
    description: Optional[str] = Field(None, description="配置描述")
    priority: Optional[int] = Field(None, description="优先级")
    display_order: Optional[int] = Field(None, alias="displayOrder", description="显示顺序")

    model_config = ConfigDict(populate_by_name=True)


class PriorityUpdateRequest(BaseModel):
    """更新优先级 — 对齐 Java POST /{id}/priority"""
    priority: int = Field(..., description="优先级")


class DisplayOrderUpdateRequest(BaseModel):
    """更新显示顺序 — 对齐 Java POST /{id}/display-order"""
    display_order: int = Field(..., alias="displayOrder", description="显示顺序")

    model_config = ConfigDict(populate_by_name=True)


# ═══════════════════════════════════════════════════════════════
# Response
# ═══════════════════════════════════════════════════════════════

class PromptConfigResponse(BaseModel):
    """Prompt 配置响应 — camelCase 对齐 Java UserPromptConfig"""
    id: str
    name: str
    prompt_type: str = Field(..., alias="promptType")
    agent_id: Optional[int] = Field(None, alias="agentId")
    system_prompt: Optional[str] = Field(None, alias="systemPrompt")
    enabled: int
    description: Optional[str] = None
    priority: int
    display_order: int = Field(..., alias="displayOrder")
    creator: Optional[str] = None
    create_time: datetime = Field(..., alias="createTime")
    update_time: datetime = Field(..., alias="updateTime")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @computed_field(alias="optimizationPrompt")
    def optimization_prompt(self) -> Optional[str]:
        """Java 兼容：optimizationPrompt 与 systemPrompt 同值"""
        return self.system_prompt


# ═══════════════════════════════════════════════════════════════
# 兼容别名
# ═══════════════════════════════════════════════════════════════

SUPPORTED_PROMPT_TYPES = [
    "report-generator",
    "planner",
    "sql-generator",
    "python-generator",
    "rewrite",
]
