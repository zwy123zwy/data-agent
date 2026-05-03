from pydantic_settings import BaseSettings
from typing import Optional


class CodeExecutorSettings(BaseSettings):
    """Python 代码执行器配置"""
    executor_type: str = "local"  # local / docker / ai-sim
    python_max_tries_count: int = 5
    code_timeout: int = 60
    limit_memory: str = "512M"

    class Config:
        env_file = ".env"
        case_sensitive = False
        env_prefix = "CODE_EXECUTOR_"
        extra = "ignore"


class FileStorageSettings(BaseSettings):
    """文件存储配置"""
    type: str = "local"  # local / oss
    path_prefix: str = "data-agent"
    path: str = "uploads"
    url_prefix: str = "/uploads"
    image_size: int = 2097152

    class Config:
        env_file = ".env"
        case_sensitive = False
        env_prefix = "FILE_"
        extra = "ignore"


class VectorStoreSettings(BaseSettings):
    """向量存储配置"""
    table_topk_limit: int = 10
    table_similarity_threshold: float = 0.2
    default_topk_limit: int = 8
    default_similarity_threshold: float = 0.4
    hybrid_search_enabled: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = False
        env_prefix = "VECTOR_STORE_"
        extra = "ignore"


class LangfuseSettings(BaseSettings):
    """Langfuse 可观测性配置"""
    enabled: bool = False
    host: str = ""
    public_key: str = ""
    secret_key: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False
        env_prefix = "LANGFUSE_"
        extra = "ignore"


class Settings(BaseSettings):
    """应用配置"""

    # 应用
    app_name: str = "Python Agent V2"
    app_version: str = "0.2.0"
    debug: bool = True

    # 数据库
    database_url: str = "mysql+aiomysql://root:123456@localhost:3306/dataagent"

    # LLM
    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4"
    openai_temperature: float = 0.0
    llm_service_type: str = "stream"  # stream / block

    # 服务
    host: str = "0.0.0.0"
    port: int = 8100

    # 日志
    log_level: str = "INFO"

    # DataAgent 业务配置
    max_sql_retry_count: int = 10
    max_plan_repair_count: int = 3
    max_turn_history: int = 5
    enable_sql_result_chart: bool = True
    enrich_sql_result_timeout: int = 30

    # 子配置
    code_executor: CodeExecutorSettings = CodeExecutorSettings()
    file_storage: FileStorageSettings = FileStorageSettings()
    vector_store: VectorStoreSettings = VectorStoreSettings()
    langfuse: LangfuseSettings = LangfuseSettings()

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
