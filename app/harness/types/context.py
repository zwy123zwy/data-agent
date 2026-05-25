# [阶段2] Harness 运行时上下文模型（独立于 agent_runtime.context）
# [Harness: Memory #4]
#
# HarnessMode vs GatewayMode:
#   HarnessMode = GatewayMode + clarification
#   clarification 被排除在 GatewayMode 外，因为它不是 LLM 分类结果，
#   而是 routing.py 推导出的路由动作。但 RuntimeContext 需要知道当前跑的是澄清模式。
#
# RuntimeContext 设计:
#   frozen=True: 不可变，一次 Run 中上下文不变，避免中途被修改导致行为不一致
#   memory=[]:   H2 暂缓，恒为空列表。H2 恢复后从 chat_message 表填充历史轮次

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.harness.types.file_ref import FileRef

HarnessMode = Literal[
    "smart_query",
    "deep_research",
    "report",
    "chitchat",
    "clarification",
    "file_analysis",
]


class DatasetRef(BaseModel):
    """[阶段2] Agent 可用数据源表引用。"""

    datasource_id: int
    datasource_name: str
    database_name: str
    table_name: str
    dialect: str = "mysql"
    table_schema: str | None = None
    row_count: int | None = None

    model_config = ConfigDict(extra="forbid")


class Permissions(BaseModel):
    """[阶段2] Agent 操作权限边界。"""

    allow_write_operations: bool = False
    allow_python_execution: bool = True
    allow_file_output: bool = False
    max_sql_result_rows: int = 10000
    python_timeout_seconds: int = 30

    model_config = ConfigDict(extra="forbid")


class Message(BaseModel):
    """[阶段2] 对话历史单条消息。"""

    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: str | None = None

    model_config = ConfigDict(extra="forbid")


class RuntimeContext(BaseModel):
    """[阶段2] 单次 Run 只读上下文，由 harness/context/builder 装配。"""

    run_id: str
    thread_id: str
    agent_id: int
    user_query: str
    mode: HarnessMode

    datasets: list[DatasetRef] = Field(default_factory=list)
    semantic_model: dict = Field(default_factory=dict)
    business_knowledge: list[dict] = Field(default_factory=list)
    prompt_overrides: dict[str, str] = Field(default_factory=dict)
    permissions: Permissions = Field(default_factory=Permissions)
    # [阶段4] 会话附件；M3 由 builder 装配，M4.0 恒为空列表
    file_refs: list[FileRef] = Field(default_factory=list)
    # [暂缓] 多轮对话记忆；当前 Harness 不装配，恒为 []
    memory: list[Message] = Field(default_factory=list)
    memory_summarized: bool = False

    model_config = ConfigDict(frozen=True, extra="forbid")
