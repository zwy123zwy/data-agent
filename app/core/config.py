from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # 应用
    app_name: str = "Python Agent V2"
    app_version: str = "0.1.0"
    debug: bool = True

    # 数据库
    database_url: str = "mysql+aiomysql://root:123456@localhost:3306/dataagent"

    # LLM
    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4"
    openai_temperature: float = 0.0

    # 服务
    host: str = "0.0.0.0"
    port: int = 8100

    # 日志
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
