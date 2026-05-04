"""
PromptConfig Pydantic Schemas — 对齐 Java PromptConfigDTO
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class PromptConfigCreate(BaseModel):
    """创建/更新 Prompt 配置请求 — 对齐 Java PromptConfigDTO"""
    id: Optional[str] = Field(None, description="配置ID (有则更新，无则新建)")
    name: str = Field(..., max_length=200, description="配置名称")
    prompt_type: str = Field(..., alias="promptType", max_length=50, description="提示词类型: report-generator/planner/sql-generator/python-generator/rewrite")
    agent_id: Optional[int] = Field(None, alias="agentId", description="Agent ID (null=全局)")
    optimization_prompt: str = Field(..., alias="optimizationPrompt", description="自定义系统提示词")
    enabled: Optional[bool] = Field(True, description="是否启用")
    description: Optional[str] = Field(None, description="配置描述")
    priority: Optional[int] = Field(0, description="优先级")
    display_order: Optional[int] = Field(0, alias="displayOrder", description="显示顺序")
    creator: Optional[str] = Field(None, max_length=100, description="创建者")

    model_config = ConfigDict(populate_by_name=True)


class PromptConfigUpdate(BaseModel):
    """更新 Prompt 配置 — 少量字段"""
    name: Optional[str] = Field(None, max_length=200, description="配置名称")
    optimization_prompt: Optional[str] = Field(None, alias="optimizationPrompt", description="系统提示词")
    enabled: Optional[bool] = Field(None, description="是否启用")
    description: Optional[str] = Field(None, description="配置描述")
    priority: Optional[int] = Field(None, description="优先级")
    display_order: Optional[int] = Field(None, alias="displayOrder", description="显示顺序")

    model_config = ConfigDict(populate_by_name=True)


class PromptConfigResponse(BaseModel):
    """Prompt 配置响应 — camelCase 对齐前端"""
    id: str
    name: str
    prompt_type: str = Field(..., alias="promptType")
    agent_id: Optional[int] = Field(None, alias="agentId")
    system_prompt: Optional[str] = Field(None, alias="systemPrompt")
    optimization_prompt: Optional[str] = Field(None, alias="optimizationPrompt")
    enabled: bool
    description: Optional[str] = None
    priority: int
    display_order: int = Field(..., alias="displayOrder")
    creator: Optional[str] = None
    create_time: datetime = Field(..., alias="createTime")
    update_time: datetime = Field(..., alias="updateTime")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# 对齐 Java: 支持的 Prompt 类型
SUPPORTED_PROMPT_TYPES = [
    "report-generator",
    "planner",
    "sql-generator",
    "python-generator",
    "rewrite",
]
