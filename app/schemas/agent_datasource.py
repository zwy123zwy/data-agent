"""
AgentDatasource Pydantic Schemas — camelCase 对齐前端 AgentDatasource 接口
"""
from datetime import datetime
from typing import Optional, Union
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


class TableInfo(BaseModel):
    """表信息 — 前端可能发 {name, comment} 对象"""
    name: str
    comment: str = ""


class UpdateDatasourceTablesRequest(BaseModel):
    """更新选中的数据表 — 对齐 Java UpdateDatasourceTablesDTO

    兼容前端两种格式:
      - 字符串: ["order_info", "patient"]
      - 对象:   [{"name": "order_info", "comment": ""}, ...]
    """
    datasource_id: int = Field(..., alias="datasourceId")
    tables: list[Union[str, TableInfo]] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)

    def get_table_names(self) -> list[str]:
        return [t if isinstance(t, str) else t.name for t in self.tables]


class AgentDatasourceResponse(BaseModel):
    """Agent-Datasource 关联响应 — 对齐前端 AgentDatasource 接口全部 8 个字段

    Python 字段名使用 ORM 属性名 (create_time/update_time)，通过 alias 输出 camelCase。
    isActive 输出 int (0/1) 对齐 Java Integer 类型。
    """
    id: int
    agent_id: int = Field(..., alias="agentId")
    datasource_id: int = Field(..., alias="datasourceId")
    is_active: int = Field(..., alias="isActive", description="0=禁用, 1=启用")
    create_time: Optional[datetime] = Field(None, alias="createTime")
    update_time: Optional[datetime] = Field(None, alias="updateTime")
    datasource: Optional[DatasourceResponse] = None
    select_tables: list[str] = Field(default_factory=list, alias="selectTables")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
