"""
SemanticModel Pydantic Schema
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


class SemanticModelBase(BaseModel):
    """语义模型基础 Schema"""
    table_name: str = Field(..., max_length=100, description="表名")
    column_name: Optional[str] = Field(None, max_length=100, description="字段名（NULL表示表级别）")
    business_name: str = Field(..., max_length=200, description="业务名称")
    description: Optional[str] = Field(None, description="业务描述（存入business_description字段）")
    synonyms: Optional[List[str]] = Field(None, description="同义词列表（API层为List，存储为逗号分隔字符串）")
    column_comment: Optional[str] = Field(None, description="数据库字段原始注释（对齐Java）")
    data_type: Optional[str] = Field(None, max_length=50, description="物理数据类型（对齐Java）")
    sample_values: Optional[List[str]] = Field(None, description="示例值")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class SemanticModelCreate(SemanticModelBase):
    """创建语义模型请求 — 对齐 Java SemanticModelAddDTO"""
    agent_id: int = Field(..., alias="agentId", description="智能体ID")
    datasource_id: Optional[int] = Field(None, description="数据源ID")

    model_config = ConfigDict(populate_by_name=True)


class SemanticModelUpdate(BaseModel):
    """更新语义模型请求"""
    table_name: Optional[str] = Field(None, max_length=100, description="表名")
    column_name: Optional[str] = Field(None, max_length=100, description="字段名")
    business_name: Optional[str] = Field(None, max_length=200, description="业务名称")
    description: Optional[str] = Field(None, description="业务描述")
    synonyms: Optional[List[str]] = Field(None, description="同义词列表")
    column_comment: Optional[str] = Field(None, description="数据库字段原始注释")
    data_type: Optional[str] = Field(None, max_length=50, description="物理数据类型")
    sample_values: Optional[List[str]] = Field(None, description="示例值")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class SemanticModelResponse(SemanticModelBase):
    """语义模型响应"""
    id: int
    agent_id: int
    datasource_id: int
    status: int = 1
    created_at: datetime
    updated_at: datetime

    metadata: Optional[Dict[str, Any]] = Field(None, alias="metadata_")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class SemanticModelSearchRequest(BaseModel):
    """语义模型搜索请求"""
    query: str = Field(..., description="搜索查询（业务名称或同义词）")
    datasource_id: Optional[int] = Field(None, description="过滤数据源ID")
    table_name: Optional[str] = Field(None, description="过滤表名")


# ================================================================
# Batch Import — 对齐 Java SemanticModelBatchImportDTO / SemanticModelImportItem
# ================================================================

class SemanticModelImportItem(BaseModel):
    """单条导入项 — 对齐 Java SemanticModelImportItem"""
    table_name: str = Field(..., alias="tableName", description="表名")
    column_name: str = Field(..., alias="columnName", description="字段名")
    business_name: str = Field(..., alias="businessName", description="业务名称")
    data_type: str = Field(..., alias="dataType", description="数据类型")
    synonyms: Optional[str] = Field(None, description="同义词")
    business_description: Optional[str] = Field(None, alias="businessDescription", description="业务描述")
    column_comment: Optional[str] = Field(None, alias="columnComment", description="字段注释")
    create_time: Optional[datetime] = Field(None, alias="createTime", description="创建时间")

    model_config = ConfigDict(populate_by_name=True)


class SemanticModelBatchImportDTO(BaseModel):
    """批量导入请求 — 对齐 Java SemanticModelBatchImportDTO"""
    agent_id: int = Field(..., alias="agentId", description="智能体ID")
    items: list[SemanticModelImportItem] = Field(..., min_length=1, description="导入数据")

    model_config = ConfigDict(populate_by_name=True)


class BatchImportResult(BaseModel):
    """批量导入结果 — 对齐 Java BatchImportResult"""
    total: int = 0
    success_count: int = Field(0, alias="successCount")
    fail_count: int = Field(0, alias="failCount")
    errors: list[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)
