from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator


class DatasourceBase(BaseModel):
    """Datasource 基础模型 — camelCase 对齐前端/Java"""
    name: str = Field(..., max_length=255, description="数据源名称")
    type: str = Field(..., pattern="^(mysql|postgresql|sqlite)$", description="数据库类型")
    database_name: str = Field(..., max_length=255, alias="databaseName", description="数据库名")

    model_config = ConfigDict(populate_by_name=True)


class DatasourceCreate(DatasourceBase):
    """创建 Datasource 请求 — 前端字段名对齐"""
    host: Optional[str] = Field(None, max_length=255, description="主机地址")
    port: Optional[int] = Field(None, ge=1, le=65535, description="端口号")
    username: Optional[str] = Field(None, max_length=255, description="用户名")
    password: Optional[str] = Field(None, max_length=255, description="密码")
    connection_url: Optional[str] = Field(None, max_length=1000, alias="connectionUrl", description="连接字符串（SQLite）")
    description: Optional[str] = Field(None, description="数据源描述")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """验证数据库类型"""
        allowed_types = ["mysql", "postgresql", "sqlite"]
        if v not in allowed_types:
            raise ValueError(f"type must be one of {allowed_types}")
        return v


class DatasourceUpdate(BaseModel):
    """更新 Datasource 请求 — 前端字段名对齐"""
    name: Optional[str] = Field(None, max_length=255, description="数据源名称")
    host: Optional[str] = Field(None, max_length=255, description="主机地址")
    port: Optional[int] = Field(None, ge=1, le=65535, description="端口号")
    username: Optional[str] = Field(None, max_length=255, description="用户名")
    password: Optional[str] = Field(None, max_length=255, description="密码")
    connection_url: Optional[str] = Field(None, max_length=1000, alias="connectionUrl", description="连接字符串")
    database_name: Optional[str] = Field(None, max_length=255, alias="databaseName", description="数据库名")
    description: Optional[str] = Field(None, description="数据源描述")
    status: Optional[str] = Field(None, pattern="^(active|inactive|deleted)$", description="通用状态")

    model_config = ConfigDict(populate_by_name=True)


class DatasourceResponse(BaseModel):
    """Datasource 响应 — camelCase 对齐前端"""
    id: int
    name: Optional[str] = None
    type: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    database_name: Optional[str] = Field(None, alias="databaseName")
    username: Optional[str] = None
    connection_url: Optional[str] = Field(None, alias="connectionUrl")
    status: Optional[str] = "inactive"
    test_status: Optional[str] = Field(None, alias="testStatus")
    description: Optional[str] = None
    creator_id: Optional[int] = Field(None, alias="creatorId")
    create_time: Optional[datetime] = Field(None, alias="createTime")
    update_time: Optional[datetime] = Field(None, alias="updateTime")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class DatasourceListResponse(BaseModel):
    """Datasource 列表响应"""
    total: int
    items: list[DatasourceResponse]


class DatasourceTestResponse(BaseModel):
    """数据源测试响应"""
    success: bool
    message: str
    test_status: str
