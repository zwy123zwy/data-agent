"""
ModelConfig Pydantic Schema — 对齐 Java ModelConfig DTO (camelCase)
"""
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, Dict, Any
from datetime import datetime


class ModelConfigBase(BaseModel):
    """模型配置基础 Schema — field alias 对齐前端/Java camelCase"""
    name: Optional[str] = Field(None, max_length=100, description="模型名称(自动生成)")
    type: str = Field(..., max_length=50, alias="modelType", description="模型类型: CHAT, EMBEDDING")
    provider: str = Field(..., max_length=50, description="提供商: openai, deepseek, qwen")
    model_id: str = Field(..., max_length=100, alias="modelName", description="模型名称如 gpt-4")
    api_key: Optional[str] = Field(None, max_length=255, alias="apiKey", description="API Key")
    api_base: Optional[str] = Field(None, max_length=255, alias="baseUrl", description="API Base URL")
    temperature: float = Field(0.0, ge=0.0, le=2.0, description="温度参数")
    max_tokens: Optional[int] = Field(None, ge=1, alias="maxTokens", description="最大 Token 数")
    enabled: bool = Field(True, description="是否启用")
    is_default: bool = Field(False, alias="isActive", description="是否激活/默认")
    # 代理和路径字段 (Java 有, 暂存 metadata)
    completions_path: Optional[str] = Field(None, alias="completionsPath", description="对话补全路径")
    embeddings_path: Optional[str] = Field(None, alias="embeddingsPath", description="嵌入路径")
    proxy_enabled: Optional[bool] = Field(None, alias="proxyEnabled", description="代理开关")
    proxy_host: Optional[str] = Field(None, alias="proxyHost", description="代理主机")
    proxy_port: Optional[int] = Field(None, alias="proxyPort", description="代理端口")
    proxy_username: Optional[str] = Field(None, alias="proxyUsername", description="代理用户名")
    proxy_password: Optional[str] = Field(None, alias="proxyPassword", description="代理密码")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v: str) -> str:
        """CHAT → chat, EMBEDDING → embedding"""
        if isinstance(v, str):
            return v.lower()
        return v


class ModelConfigCreate(ModelConfigBase):
    """创建模型配置请求"""
    pass


class ModelConfigUpdate(BaseModel):
    """更新模型配置请求 — id 从 body 来 (对齐 Java PUT /update)"""
    id: Optional[int] = Field(None, description="模型配置ID")
    name: Optional[str] = Field(None, max_length=100, description="模型名称")
    type: Optional[str] = Field(None, max_length=50, alias="modelType", description="模型类型")
    provider: Optional[str] = Field(None, max_length=50, description="提供商")
    model_id: Optional[str] = Field(None, max_length=100, alias="modelName", description="模型名称")
    api_key: Optional[str] = Field(None, max_length=255, alias="apiKey", description="API Key")
    api_base: Optional[str] = Field(None, max_length=255, alias="baseUrl", description="API Base URL")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="温度参数")
    max_tokens: Optional[int] = Field(None, ge=1, alias="maxTokens", description="最大 Token 数")
    enabled: Optional[bool] = Field(None, description="是否启用")
    is_default: Optional[bool] = Field(None, alias="isActive", description="是否激活/默认")
    completions_path: Optional[str] = Field(None, alias="completionsPath", description="对话补全路径")
    embeddings_path: Optional[str] = Field(None, alias="embeddingsPath", description="嵌入路径")
    proxy_enabled: Optional[bool] = Field(None, alias="proxyEnabled", description="代理开关")
    proxy_host: Optional[str] = Field(None, alias="proxyHost", description="代理主机")
    proxy_port: Optional[int] = Field(None, alias="proxyPort", description="代理端口")
    proxy_username: Optional[str] = Field(None, alias="proxyUsername", description="代理用户名")
    proxy_password: Optional[str] = Field(None, alias="proxyPassword", description="代理密码")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.lower()
        return v


class ModelConfigResponse(BaseModel):
    """模型配置响应 — camelCase 对齐前端"""
    id: int
    name: Optional[str] = None
    provider: Optional[str] = None
    model_id: Optional[str] = Field(None, alias="modelName")
    type: Optional[str] = Field(None, alias="modelType")
    api_key: Optional[str] = Field(None, alias="apiKey")
    api_base: Optional[str] = Field(None, alias="baseUrl")
    temperature: Optional[float] = None
    max_tokens: Optional[int] = Field(None, alias="maxTokens")
    enabled: Optional[bool] = None
    is_default: Optional[bool] = Field(None, alias="isActive")
    completions_path: Optional[str] = Field(None, alias="completionsPath")
    embeddings_path: Optional[str] = Field(None, alias="embeddingsPath")
    proxy_enabled: Optional[bool] = Field(None, alias="proxyEnabled")
    proxy_host: Optional[str] = Field(None, alias="proxyHost")
    proxy_port: Optional[int] = Field(None, alias="proxyPort")
    proxy_username: Optional[str] = Field(None, alias="proxyUsername")
    proxy_password: Optional[str] = Field(None, alias="proxyPassword")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator("type", mode="before")
    @classmethod
    def denormalize_type(cls, v: Optional[str]) -> Optional[str]:
        """chat → CHAT, embedding → EMBEDDING (对齐 Java)"""
        if isinstance(v, str):
            return v.upper()
        return v


class ModelTestRequest(BaseModel):
    """模型测试请求 — 对齐 Java /test"""
    prompt: Optional[str] = Field("Hello, how are you?", description="测试提示词")
    provider: Optional[str] = Field(None, description="提供商")
    api_key: Optional[str] = Field(None, alias="apiKey", description="API Key")
    api_base: Optional[str] = Field(None, alias="baseUrl", description="API Base URL")
    model_id: Optional[str] = Field(None, alias="modelName", description="模型名称")
    type: Optional[str] = Field(None, alias="modelType", description="模型类型")
    temperature: Optional[float] = Field(0.0)
    max_tokens: Optional[int] = Field(None, alias="maxTokens")

    model_config = ConfigDict(populate_by_name=True)
