"""
ModelConfig Pydantic Schema
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime


class ModelConfigBase(BaseModel):
    """模型配置基础 Schema"""
    name: str = Field(..., max_length=100, description="模型名称")
    type: str = Field(..., max_length=50, description="模型类型: chat, embedding")
    provider: str = Field(..., max_length=50, description="提供商: openai, anthropic, qwen")
    model_id: str = Field(..., max_length=100, description="模型ID")
    api_key: Optional[str] = Field(None, max_length=255, description="API Key")
    api_base: Optional[str] = Field(None, max_length=255, description="API Base URL")
    temperature: float = Field(0.0, ge=0.0, le=2.0, description="温度参数")
    max_tokens: Optional[int] = Field(None, ge=1, description="最大 Token 数")
    enabled: bool = Field(True, description="是否启用")
    is_default: bool = Field(False, description="是否默认")
    metadata: Optional[Dict[str, Any]] = Field(None, description="其他配置")


class ModelConfigCreate(ModelConfigBase):
    """创建模型配置请求"""
    pass


class ModelConfigUpdate(BaseModel):
    """更新模型配置请求"""
    name: Optional[str] = Field(None, max_length=100, description="模型名称")
    type: Optional[str] = Field(None, max_length=50, description="模型类型")
    provider: Optional[str] = Field(None, max_length=50, description="提供商")
    model_id: Optional[str] = Field(None, max_length=100, description="模型ID")
    api_key: Optional[str] = Field(None, max_length=255, description="API Key")
    api_base: Optional[str] = Field(None, max_length=255, description="API Base URL")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="温度参数")
    max_tokens: Optional[int] = Field(None, ge=1, description="最大 Token 数")
    enabled: Optional[bool] = Field(None, description="是否启用")
    is_default: Optional[bool] = Field(None, description="是否默认")
    metadata: Optional[Dict[str, Any]] = Field(None, description="其他配置")


class ModelConfigResponse(ModelConfigBase):
    """模型配置响应"""
    id: int
    created_at: datetime
    updated_at: datetime

    metadata: Optional[Dict[str, Any]] = Field(None, alias="metadata_")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ModelTestRequest(BaseModel):
    """模型测试请求"""
    prompt: str = Field("Hello, how are you?", description="测试提示词")
