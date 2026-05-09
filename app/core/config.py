"""
应用配置中心 — 所有模块的配置来源

【在系统中的地位】
  本文件是整个后端的配置中枢。所有模块的配置都从这里读取，
  通过 Pydantic Settings 从 .env 文件和环境变量自动加载。

【模块连接】
  被依赖者 (谁 import settings):
    - core/database.py          → settings.database_url (MySQL 连接串)
    - core/llm.py               → settings.openai_* (LLM API 配置)
    - core/vector_store.py      → settings.openai_* (Embedding API)
    - core/model_registry.py    → settings.openai_* (模型测试)
    - workflows/graph.py        → settings.max_sql_retry_count (重试次数)
    - workflows/nodes/*.py      → settings.* (各种业务配置)
    - services/hybrid_search.py → settings.vector_store.* (检索参数)
    - main.py                   → settings.host, settings.port (服务绑定)

  Java 对应:
    Settings ≈ Spring Boot application.yml 中的 spring.ai.alibaba.data-agent.* 配置

【配置优先级】
  .env 文件 > 环境变量 > 代码默认值

【子配置分组】
  Settings
    ├── code_executor: CodeExecutorSettings  → Python 代码执行 (executor_type, timeout, memory)
    ├── file_storage: FileStorageSettings    → 文件存储 (local / OSS)
    ├── vector_store: VectorStoreSettings    → 向量检索 (topk, threshold, hybrid)
    └── langfuse: LangfuseSettings           → 可观测性追踪
"""
from pydantic_settings import BaseSettings
from typing import Optional


class CodeExecutorSettings(BaseSettings):
    """Python 代码执行器配置 — 被 core/code_executor.py 使用

    executor_type 选项:
      - "local"  : 本地 subprocess 执行 Python (默认)
      - "docker" : Docker 容器隔离执行
      - "ai-sim" : LLM 模拟执行 (不实际运行代码)
    """
    executor_type: str = "local"
    python_max_tries_count: int = 5
    code_timeout: int = 60
    limit_memory: str = "512M"

    class Config:
        env_file = ".env"
        case_sensitive = False
        env_prefix = "CODE_EXECUTOR_"
        extra = "ignore"


class FileStorageSettings(BaseSettings):
    """文件存储配置 — 被文件上传/下载相关 API 使用"""
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
    """向量存储配置 — 被 services/hybrid_search.py 使用

    table_topk_limit / table_similarity_threshold: 表召回专用 (更宽松)
    default_topk_limit / default_similarity_threshold: 知识召回通用
    """
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
    """Langfuse 可观测性配置 — 被 services/langfuse_service.py 使用

    开启后，所有 LLM 调用的 trace 会发送到 Langfuse 平台
    用于调试 prompt、追踪 token 消耗、分析延迟
    """
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
    """应用配置 — 全局单例 settings 对象

    配置来源: .env 文件 (python-agent-v2/.env) + 环境变量
    """

    # 应用
    app_name: str = "Python Agent V2"
    app_version: str = "0.2.0"
    debug: bool = True

    # 数据库 — 被 core/database.py 读取
    database_url: str = "mysql+aiomysql://root:123456@localhost:3306/dataagent"

    # LLM (Chat) — 被 core/llm.py 读取
    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4"
    openai_temperature: float = 0.0
    llm_service_type: str = "stream"  # stream / block

    # Embedding — 被 core/vector_store.py 读取 (Ollama bge-m3)
    embedding_api_key: str = "ollama"
    embedding_api_base: str = "http://localhost:11434/v1"
    embedding_model: str = "bge-m3"

    # Chroma 向量库 — Docker 实例
    chroma_host: str = "localhost"
    chroma_port: int = 8000

    # 服务 — 被 main.py 读取
    host: str = "0.0.0.0"
    port: int = 8100

    # 日志
    log_level: str = "INFO"

    # DataAgent 业务配置 — 被 workflows/* 读取
    max_sql_retry_count: int = 10       # SQL 生成最大重试次数
    max_plan_repair_count: int = 3      # 计划修复最大尝试次数
    max_turn_history: int = 5           # 多轮对话历史最大保留轮数
    enable_sql_result_chart: bool = True # 是否自动生成图表推荐
    enrich_sql_result_timeout: int = 30  # SQL 结果丰富超时

    # Checkpointer 配置 — 被 workflows/graph.py 使用
    # "memory": MemorySaver (默认, 进程重启丢失)
    # "sqlite": SqliteSaver (持久化到 checkpoints.db, 跨重启保留)
    checkpointer_type: str = "sqlite"
    checkpointer_db_path: str = "checkpoints.db"

    # 子配置
    code_executor: CodeExecutorSettings = CodeExecutorSettings()
    file_storage: FileStorageSettings = FileStorageSettings()
    vector_store: VectorStoreSettings = VectorStoreSettings()
    langfuse: LangfuseSettings = LangfuseSettings()

    class Config:
        env_file = ".env"
        case_sensitive = False


# 全局单例 — 所有模块通过 from core.config import settings 获取
settings = Settings()
