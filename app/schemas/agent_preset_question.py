"""AgentPresetQuestion Schema — 对齐 Java AgentPresetQuestion Entity"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


# ═══════════════════════════════════════════════════════════════
# 基类
# ═══════════════════════════════════════════════════════════════

class PresetQuestionBase(BaseModel):
    """预设问题公共字段"""
    question: str = Field(..., description="问题内容")
    is_active: int = Field(1, alias="isActive", description="是否启用: 0/1")
    sort_order: int = Field(0, alias="sortOrder", description="排序顺序")

    model_config = ConfigDict(populate_by_name=True)


# ═══════════════════════════════════════════════════════════════
# Request
# ═══════════════════════════════════════════════════════════════

class PresetQuestionSaveRequest(BaseModel):
    """批量保存预设问题 — 对齐 Java POST /{agentId}/preset-questions"""
    questions: List[PresetQuestionBase] = Field(..., description="预设问题列表")

    model_config = ConfigDict(populate_by_name=True)


# ═══════════════════════════════════════════════════════════════
# Response
# ═══════════════════════════════════════════════════════════════

class PresetQuestionResponse(BaseModel):
    """预设问题响应 — camelCase 对齐前端/Java"""
    id: int
    agent_id: int = Field(..., alias="agentId")
    question: str
    sort_order: int = Field(0, alias="sortOrder")
    is_active: int = Field(0, alias="isActive")
    create_time: datetime = Field(..., alias="createTime")
    update_time: datetime = Field(..., alias="updateTime")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ========== 兼容别名 ==========
AgentPresetQuestionCreate = PresetQuestionBase
AgentPresetQuestionResponse = PresetQuestionResponse
