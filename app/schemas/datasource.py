from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator


class DatasourceBase(BaseModel):
    """Datasource 基础模型"""
    name: str = Field(..., max_length=100, description="数据源名称")
    type: str = Field(..., pattern="^(mysql|postgresql|sqlite)$", description="数据库类型")
    database: str = Field(..., max_length=100, description="数据库名")


class DatasourceCreate(DatasourceBase):
    """创建 Datasource 请求"""
    host: Optional[str] = Field(None, max_length=255, description="主机地址")
    port: Optional[int] = Field(None, ge=1, le=65535, description="端口号")
    username: Optional[str] = Field(None, max_length=100, description="用户名")
    password: Optional[str] = Field(None, max_length=255, description="密码")
    connection_url: Optional[str] = Field(None, max_length=500, description="连接字符串（SQLite）")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """验证数据库类型"""
        allowed_types = ["mysql", "postgresql", "sqlite"]
        if v not in allowed_types:
            raise ValueError(f"type must be one of {allowed_types}")
        return v


class DatasourceUpdate(BaseModel):
    """更新 Datasource 请求"""
    name: Optional[str] = Field(None, max_length=100, description="数据源名称")
    host: Optional[str] = Field(None, max_length=255, description="主机地址")
    port: Optional[int] = Field(None, ge=1, le=65535, description="端口号")
    username: Optional[str] = Field(None, max_length=100, description="用户名")
    password: Optional[str] = Field(None, max_length=255, description="密码")
    connection_url: Optional[str] = Field(None, max_length=500, description="连接字符串")


class DatasourceResponse(DatasourceBase):
    """Datasource 响应（不包含密码）"""
    id: int
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    connection_url: Optional[str] = None
    test_status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasourceListResponse(BaseModel):
    """Datasource 列表响应"""
    total: int
    items: list[DatasourceResponse]


class DatasourceTestResponse(BaseModel):
    """数据源测试响应"""
    success: bool
    message: str
    test_status: str
