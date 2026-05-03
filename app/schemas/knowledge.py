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
    type: str = Field(..., max_length=50, description="知识类型: DOCUMENT/QA/FAQ（对齐Java）")
    question: Optional[str] = Field(None, description="FAQ/QA 问题（对齐Java）")
    is_recall: int = Field(1, description="业务状态: 1=召回, 0=非召回（对齐Java）")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    enabled: bool = Field(True, description="是否启用")


class KnowledgeCreate(KnowledgeBase):
    """创建知识库请求"""
    source_filename: Optional[str] = Field(None, max_length=255, description="源文件名")
    file_path: Optional[str] = Field(None, max_length=500, description="文件路径")
    file_size: Optional[int] = Field(None, description="文件大小（字节）")
    file_type: Optional[str] = Field(None, max_length=50, description="文件类型")
    splitter_type: Optional[str] = Field("token", max_length=50, description="分块策略")


class KnowledgeUpdate(BaseModel):
    """更新知识库请求"""
    title: Optional[str] = Field(None, max_length=200, description="知识标题")
    content: Optional[str] = Field(None, description="知识内容")
    type: Optional[str] = Field(None, max_length=50, description="知识类型")
    question: Optional[str] = Field(None, description="FAQ/QA 问题")
    is_recall: Optional[int] = Field(None, description="业务状态")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    enabled: Optional[bool] = Field(None, description="是否启用")


class KnowledgeResponse(KnowledgeBase):
    """知识库响应"""
    id: int
    agent_id: int
    embedding_id: Optional[str] = None
    embedding_status: Optional[str] = None
    error_msg: Optional[str] = None
    source_filename: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    splitter_type: Optional[str] = None
    is_deleted: int = 0
    is_resource_cleaned: int = 0
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
