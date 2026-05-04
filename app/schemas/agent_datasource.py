"""
AgentDatasource Pydantic Schemas — camelCase 对齐前端 AgentDatasource 接口
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from .datasource import DatasourceResponse


class AgentDatasourceCreate(BaseModel):
    """创建 Agent-Datasource 关联请求"""
    is_active: bool = Field(True, description="是否激活")


class ToggleDatasourceRequest(BaseModel):
    """切换数据源激活状态 — 对齐 Java ToggleDatasourceDTO"""
    datasource_id: int = Field(..., alias="datasourceId")
    is_active: bool = Field(..., alias="isActive")

    model_config = ConfigDict(populate_by_name=True)


class UpdateDatasourceTablesRequest(BaseModel):
    """更新选中的数据表 — 对齐 Java UpdateDatasourceTablesDTO"""
    datasource_id: int = Field(..., alias="datasourceId")
    tables: list[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class AgentDatasourceResponse(BaseModel):
    """Agent-Datasource 关联响应 — 对齐前端 AgentDatasource 接口全部 8 个字段

    Python 字段名使用 ORM 属性名 (created_at/updated_at)，通过 alias 输出 camelCase。
    """
    id: int
    agent_id: int = Field(..., alias="agentId")
    datasource_id: int = Field(..., alias="datasourceId")
    is_active: bool = Field(..., alias="isActive")
    created_at: Optional[datetime] = Field(None, alias="createTime")
    updated_at: Optional[datetime] = Field(None, alias="updateTime")
    datasource: Optional[DatasourceResponse] = None
    select_tables: list[str] = Field(default_factory=list, alias="selectTables")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
