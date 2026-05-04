"""LogicalRelation Pydantic Schema — camelCase 对齐 Java LogicalRelation"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class LogicalRelationCreate(BaseModel):
    """创建逻辑外键 — 对齐 Java CreateLogicalRelationDTO"""
    source_table_name: str = Field(..., alias="sourceTableName", max_length=100)
    source_column_name: str = Field(..., alias="sourceColumnName", max_length=100)
    target_table_name: str = Field(..., alias="targetTableName", max_length=100)
    target_column_name: str = Field(..., alias="targetColumnName", max_length=100)
    relation_type: Optional[str] = Field(None, alias="relationType", max_length=20)
    description: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class LogicalRelationUpdate(BaseModel):
    """更新逻辑外键 — 对齐 Java UpdateLogicalRelationDTO"""
    source_table_name: Optional[str] = Field(None, alias="sourceTableName", max_length=100)
    source_column_name: Optional[str] = Field(None, alias="sourceColumnName", max_length=100)
    target_table_name: Optional[str] = Field(None, alias="targetTableName", max_length=100)
    target_column_name: Optional[str] = Field(None, alias="targetColumnName", max_length=100)
    relation_type: Optional[str] = Field(None, alias="relationType", max_length=20)
    description: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class LogicalRelationResponse(BaseModel):
    """逻辑外键响应 — camelCase 对齐 Java LogicalRelation"""
    id: int
    datasource_id: int = Field(..., alias="datasourceId")
    source_table_name: str = Field(..., alias="sourceTableName")
    source_column_name: str = Field(..., alias="sourceColumnName")
    target_table_name: str = Field(..., alias="targetTableName")
    target_column_name: str = Field(..., alias="targetColumnName")
    relation_type: Optional[str] = Field(None, alias="relationType")
    description: Optional[str] = None
    is_deleted: int = Field(0, alias="isDeleted")
    created_time: datetime = Field(..., alias="createdTime")
    updated_time: datetime = Field(..., alias="updatedTime")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
