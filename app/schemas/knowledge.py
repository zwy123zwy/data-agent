"""
Knowledge Pydantic Schema
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime


class KnowledgeBase(BaseModel):
    """知识库基础 Schema"""
    title: str = Field(..., max_length=200, description="知识标题")
    content: str = Field(..., description="知识内容")
    type: str = Field(..., max_length=50, description="知识类型: business_term, query_example, business_rule")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    enabled: bool = Field(True, description="是否启用")


class KnowledgeCreate(KnowledgeBase):
    """创建知识库请求"""
    pass


class KnowledgeUpdate(BaseModel):
    """更新知识库请求"""
    title: Optional[str] = Field(None, max_length=200, description="知识标题")
    content: Optional[str] = Field(None, description="知识内容")
    type: Optional[str] = Field(None, max_length=50, description="知识类型")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    enabled: Optional[bool] = Field(None, description="是否启用")


class KnowledgeResponse(KnowledgeBase):
    """知识库响应"""
    id: int
    agent_id: int
    embedding_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    metadata: Optional[Dict[str, Any]] = Field(None, alias="metadata_")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class KnowledgeSearchRequest(BaseModel):
    """知识库搜索请求"""
    query: str = Field(..., description="搜索查询")
    top_k: int = Field(5, ge=1, le=20, description="返回结果数量")
    type: Optional[str] = Field(None, description="过滤知识类型")
    enabled_only: bool = Field(True, description="仅搜索启用的知识")


class KnowledgeSearchResult(BaseModel):
    """知识库搜索结果"""
    id: int
    title: str
    content: str
    type: str
    metadata: Optional[Dict[str, Any]] = None
    distance: Optional[float] = Field(None, description="相似度距离（越小越相似）")
