"""
ModelConfig Pydantic Schema — 对齐 Java ModelConfig DTO (camelCase)
"""
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional
from datetime import datetime


class ModelConfigBase(BaseModel):
    """模型配置基础 Schema — field alias 对齐前端/Java camelCase"""
    provider: str = Field(..., max_length=255, description="厂商标识")
    base_url: str = Field(..., max_length=255, alias="baseUrl", description="API Base URL")
    api_key: str = Field(..., max_length=255, alias="apiKey", description="API Key")
    model_name: str = Field(..., max_length=255, alias="modelName", description="模型名称如 gpt-4")
    model_type: str = Field("CHAT", max_length=20, alias="modelType", description="模型类型: CHAT, EMBEDDING")
    temperature: float = Field(0.0, ge=0.0, le=2.0, description="温度参数")
    is_active: int = Field(0, alias="isActive", description="是否激活：0-否，1-是")
    max_tokens: Optional[int] = Field(2000, alias="maxTokens", description="最大 Token 数")
    completions_path: Optional[str] = Field(None, alias="completionsPath", description="对话补全路径")
    embeddings_path: Optional[str] = Field(None, alias="embeddingsPath", description="嵌入路径")
    proxy_enabled: int = Field(0, alias="proxyEnabled", description="代理开关：0-禁用，1-启用")
    proxy_host: Optional[str] = Field(None, alias="proxyHost", description="代理主机")
    proxy_port: Optional[int] = Field(None, alias="proxyPort", description="代理端口")
    proxy_username: Optional[str] = Field(None, alias="proxyUsername", description="代理用户名")
    proxy_password: Optional[str] = Field(None, alias="proxyPassword", description="代理密码")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("model_type", mode="before")
    @classmethod
    def normalize_type(cls, v: str) -> str:
        """chat → CHAT, embedding → EMBEDDING (对齐 Java)"""
        if isinstance(v, str):
            return v.upper()
        return v


class ModelConfigCreate(ModelConfigBase):
    """创建模型配置请求"""
    pass


class ModelConfigUpdate(BaseModel):
    """更新模型配置请求 — id 从 body 来 (对齐 Java PUT /update)"""
    id: Optional[int] = Field(None, description="模型配置ID")
    provider: Optional[str] = Field(None, max_length=255, description="厂商标识")
    base_url: Optional[str] = Field(None, max_length=255, alias="baseUrl", description="API Base URL")
    api_key: Optional[str] = Field(None, max_length=255, alias="apiKey", description="API Key")
    model_name: Optional[str] = Field(None, max_length=255, alias="modelName", description="模型名称")
    model_type: Optional[str] = Field(None, max_length=20, alias="modelType", description="模型类型")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="温度参数")
    is_active: Optional[int] = Field(None, alias="isActive", description="是否激活")
    max_tokens: Optional[int] = Field(None, alias="maxTokens", description="最大 Token 数")
    completions_path: Optional[str] = Field(None, alias="completionsPath", description="对话补全路径")
    embeddings_path: Optional[str] = Field(None, alias="embeddingsPath", description="嵌入路径")
    proxy_enabled: Optional[int] = Field(None, alias="proxyEnabled", description="代理开关")
    proxy_host: Optional[str] = Field(None, alias="proxyHost", description="代理主机")
    proxy_port: Optional[int] = Field(None, alias="proxyPort", description="代理端口")
    proxy_username: Optional[str] = Field(None, alias="proxyUsername", description="代理用户名")
    proxy_password: Optional[str] = Field(None, alias="proxyPassword", description="代理密码")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("model_type", mode="before")
    @classmethod
    def normalize_type(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.upper()
        return v


class ModelConfigResponse(BaseModel):
    """模型配置响应 — camelCase 对齐前端/Java"""
    id: int
    provider: Optional[str] = None
    base_url: Optional[str] = Field(None, alias="baseUrl")
    api_key: Optional[str] = Field(None, alias="apiKey")
    model_name: Optional[str] = Field(None, alias="modelName")
    model_type: Optional[str] = Field(None, alias="modelType")
    temperature: Optional[float] = None
    is_active: Optional[int] = Field(None, alias="isActive")
    max_tokens: Optional[int] = Field(None, alias="maxTokens")
    completions_path: Optional[str] = Field(None, alias="completionsPath")
    embeddings_path: Optional[str] = Field(None, alias="embeddingsPath")
    proxy_enabled: Optional[int] = Field(None, alias="proxyEnabled")
    proxy_host: Optional[str] = Field(None, alias="proxyHost")
    proxy_port: Optional[int] = Field(None, alias="proxyPort")
    proxy_username: Optional[str] = Field(None, alias="proxyUsername")
    proxy_password: Optional[str] = Field(None, alias="proxyPassword")
    created_time: Optional[datetime] = Field(None, alias="createTime")
    updated_time: Optional[datetime] = Field(None, alias="updateTime")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ModelTestRequest(BaseModel):
    """模型测试请求 — 对齐 Java /test"""
    prompt: Optional[str] = Field("Hello, how are you?", description="测试提示词")
    provider: Optional[str] = Field(None, description="提供商")
    api_key: Optional[str] = Field(None, alias="apiKey", description="API Key")
    base_url: Optional[str] = Field(None, alias="baseUrl", description="API Base URL")
    model_name: Optional[str] = Field(None, alias="modelName", description="模型名称")
    model_type: Optional[str] = Field(None, alias="modelType", description="模型类型")
    temperature: Optional[float] = Field(0.0)
    max_tokens: Optional[int] = Field(None, alias="maxTokens")

    model_config = ConfigDict(populate_by_name=True)
