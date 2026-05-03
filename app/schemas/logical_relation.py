"""LogicalRelation Pydantic Schema"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class LogicalRelationCreate(BaseModel):
    datasource_id: int
    source_table_name: str = Field(..., max_length=100)
    source_column_name: str = Field(..., max_length=100)
    target_table_name: str = Field(..., max_length=100)
    target_column_name: str = Field(..., max_length=100)
    relation_type: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = None


class LogicalRelationResponse(BaseModel):
    id: int
    datasource_id: int
    source_table_name: str
    source_column_name: str
    target_table_name: str
    target_column_name: str
    relation_type: Optional[str] = None
    description: Optional[str] = None
    is_deleted: int = 0
    created_time: datetime
    updated_time: datetime

    model_config = ConfigDict(from_attributes=True)
