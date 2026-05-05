"""Knowledge Pydantic Schemas — 对齐 Java AgentKnowledgeVO / DTOs"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
# 基类
# ═══════════════════════════════════════════════════════════════

class KnowledgeBase(BaseModel):
    """知识库公共字段 — 对齐 Java AgentKnowledge"""
    title: str = Field(..., max_length=200, description="知识标题")
    content: str = Field(..., description="知识内容")
    type: str = Field(..., max_length=50, description="知识类型: DOCUMENT/QA/FAQ")
    question: Optional[str] = Field(None, description="FAQ/QA 问题")
    is_recall: int = Field(1, alias="isRecall", description="业务状态: 1=召回, 0=非召回")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    enabled: int = Field(1, description="是否启用: 0/1")

    model_config = ConfigDict(populate_by_name=True)


# ═══════════════════════════════════════════════════════════════
# Request
# ═══════════════════════════════════════════════════════════════

class KnowledgeCreateRequest(KnowledgeBase):
    """创建知识库请求 — 对齐 Java CreateKnowledgeDTO"""
    source_filename: Optional[str] = Field(None, alias="sourceFilename", max_length=255, description="源文件名")
    file_path: Optional[str] = Field(None, alias="filePath", max_length=500, description="文件路径")
    file_size: Optional[int] = Field(None, alias="fileSize", description="文件大小（字节）")
    file_type: Optional[str] = Field(None, alias="fileType", max_length=50, description="文件类型")
    splitter_type: Optional[str] = Field("token", alias="splitterType", max_length=50, description="分块策略")


class KnowledgeUpdateRequest(BaseModel):
    """更新知识库请求 — 对齐 Java UpdateKnowledgeDTO"""
    title: Optional[str] = Field(None, max_length=200, description="知识标题")
    content: Optional[str] = Field(None, description="知识内容")
    type: Optional[str] = Field(None, max_length=50, description="知识类型")
    question: Optional[str] = Field(None, description="FAQ/QA 问题")
    is_recall: Optional[int] = Field(None, alias="isRecall", description="业务状态")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    enabled: Optional[int] = Field(None, description="是否启用: 0/1")

    model_config = ConfigDict(populate_by_name=True)


class KnowledgeQueryRequest(BaseModel):
    """分页查询请求 — 对齐 Java AgentKnowledgeQueryDTO"""
    agent_id: int = Field(..., alias="agentId")
    title: Optional[str] = None
    type: Optional[str] = None
    embedding_status: Optional[str] = Field(None, alias="embeddingStatus")
    page_num: int = Field(1, alias="pageNum", ge=1)
    page_size: int = Field(10, alias="pageSize", ge=1)

    model_config = ConfigDict(populate_by_name=True)


# ═══════════════════════════════════════════════════════════════
# Response
# ═══════════════════════════════════════════════════════════════

class KnowledgeResponse(BaseModel):
    """知识库响应 — camelCase 对齐 Java AgentKnowledgeVO"""
    id: int
    agent_id: int = Field(..., alias="agentId")
    title: str
    content: str
    type: str
    question: Optional[str] = None
    is_recall: int = Field(..., alias="isRecall")
    enabled: int
    embedding_id: Optional[str] = Field(None, alias="embeddingId")
    embedding_status: Optional[str] = Field(None, alias="embeddingStatus")
    error_msg: Optional[str] = Field(None, alias="errorMsg")
    source_filename: Optional[str] = Field(None, alias="sourceFilename")
    file_path: Optional[str] = Field(None, alias="filePath")
    file_size: Optional[int] = Field(None, alias="fileSize")
    file_type: Optional[str] = Field(None, alias="fileType")
    splitter_type: Optional[str] = Field(None, alias="splitterType")
    is_deleted: int = Field(0, alias="isDeleted")
    is_resource_cleaned: int = Field(0, alias="isResourceCleaned")
    created_time: datetime = Field(..., alias="createTime")
    updated_time: datetime = Field(..., alias="updateTime")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ═══════════════════════════════════════════════════════════════
# Search (独立用途)
# ═══════════════════════════════════════════════════════════════

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
