# [Harness: Memory #4] V2 Agent Runtime — 结构化运行时上下文
#
# RuntimeContext 由 ContextEngine.build_context() 在 Agent 执行前一次性装配。
# 所有 Agent 和 Tool 均读取此对象，Tool 无需直接查 DB。
# 装配后不可修改（frozen），防止并发读写副作用。
#
# 本模块是 V2 Agent Runtime 的一部分。参考 CLAUDE.md 了解 Harness Engineering 理念。
#
# DO NOT:
#   - Import from app/api/（跨层调用禁止）
#   - Hardcode prompt templates（走 prompt_config service）

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DatasetRef(BaseModel):
    """Agent 可用的一个数据源表引用。

    由 agent_datasource + datasource 表 join 填充。
    """

    datasource_id: int  # 数据源 ID
    datasource_name: str  # 数据源名称（人类可读）
    database_name: str  # 数据库名（来自 datasource.database_name）
    table_name: str  # 表名
    dialect: str = "mysql"  # mysql | postgresql | sqlite | clickhouse
    table_schema: str | None = None  # DDL 或列清单，由 schema_service 加载
    row_count: int | None = None  # 近似行数，用于成本估算

    model_config = ConfigDict(extra="forbid")  # 拒绝未知字段


class Permissions(BaseModel):
    """Agent 的操作权限边界。

    由 Agent 配置填充。Sandbox #5 强制执行。
    """

    allow_write_operations: bool = False  # INSERT/UPDATE/DELETE 需 HITL 审批
    allow_python_execution: bool = True  # 是否允许执行 Python 代码
    allow_file_output: bool = False  # 是否允许输出文件
    max_sql_result_rows: int = 10000  # 单次 SQL 最大返回行数
    python_timeout_seconds: int = 30  # Python 代码超时限制

    model_config = ConfigDict(extra="forbid")  # 拒绝未知字段


class Message(BaseModel):
    """对话历史中的一条消息。"""

    role: Literal["user", "assistant", "system"]  # 角色
    content: str  # 消息内容
    timestamp: str | None = None  # ISO 格式时间戳

    model_config = ConfigDict(extra="forbid")  # 拒绝未知字段


class RuntimeContext(BaseModel):
    """一次 Agent Run 的完整上下文。

    [Harness: Memory #4] 由 ContextEngine.build_context() 创建。
    所有 Agent 和 Tool 读取此对象，Tool 从其中提取所需子集。
    装配后不可修改。
    """

    # ── 身份标识 ──
    run_id: str  # UUID，每次 run 唯一
    thread_id: str  # 会话 thread = chat_session.id
    agent_id: int  # Agent 配置 ID
    user_query: str  # 用户原始输入（不变）
    mode: Literal["smart_query", "deep_research", "report", "chitchat", "clarification"]

    # ── 数据环境 ──
    datasets: list[DatasetRef] = []  # Agent 可查询的表清单
    semantic_model: dict = {}  # 业务术语 → table.column 映射
    business_knowledge: list[dict] = []  # 行业知识、指标定义等

    # ── 配置 ──
    prompt_overrides: dict[str, str] = {}  # 针对此 Agent 的自定义 prompt 片段
    permissions: Permissions = Field(default_factory=Permissions)

    # ── 对话 ──
    memory: list[Message] = []  # 近期对话消息，过长时自动摘要
    memory_summarized: bool = False  # True = memory 已压缩为摘要（非原文）

    model_config = ConfigDict(frozen=True, extra="forbid")  # 装配后不可修改，拒绝未知字段
