"""BusinessKnowledge Pydantic Schemas — camelCase 对齐 Java BusinessKnowledgeVO"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class BusinessKnowledgeCreateRequest(BaseModel):
    """创建业务知识请求 — 对齐 Java CreateBusinessKnowledgeDTO"""
    business_term: str = Field(..., alias="businessTerm", max_length=255, description="业务名词")
    description: Optional[str] = Field(None, description="描述")
    synonyms: Optional[str] = Field(None, description="同义词，逗号分隔")
    agent_id: int = Field(..., alias="agentId", description="Agent ID")
    is_recall: int = Field(1, alias="isRecall", description="是否召回: 1=是, 0=否")

    model_config = ConfigDict(populate_by_name=True)


class BusinessKnowledgeUpdateRequest(BaseModel):
    """更新业务知识请求 — 对齐 Java UpdateBusinessKnowledgeDTO"""
    business_term: Optional[str] = Field(None, alias="businessTerm", max_length=255)
    description: Optional[str] = None
    synonyms: Optional[str] = None
    is_recall: Optional[int] = Field(None, alias="isRecall")

    model_config = ConfigDict(populate_by_name=True)


class BusinessKnowledgeResponse(BaseModel):
    """业务知识响应 — camelCase 对齐 Java BusinessKnowledgeVO"""
    id: int
    business_term: str = Field(..., alias="businessTerm")
    description: Optional[str] = None
    synonyms: Optional[str] = None
    is_recall: int = Field(..., alias="isRecall")
    agent_id: int = Field(..., alias="agentId")
    embedding_status: Optional[str] = Field(None, alias="embeddingStatus")
    error_msg: Optional[str] = Field(None, alias="errorMsg")
    is_deleted: int = Field(..., alias="isDeleted")
    created_time: Optional[datetime] = Field(None, alias="createdTime")
    updated_time: Optional[datetime] = Field(None, alias="updatedTime")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
