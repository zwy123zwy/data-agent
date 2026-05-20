# [Harness: Observability #6] V2 Agent Runtime — 不可变、可追溯产出物体系
#
# Artifact  = 每次有意义的输出（SQL、表格、图表、分析、报告）→ "是什么"
# Observation = 每次工具调用记录 → "怎么产生的"
# Provenance  = 创建链追溯 → "从哪来的"
#
# 本模块是 V2 Agent Runtime 的一部分。参考 CLAUDE.md 了解 Harness Engineering 理念。
#
# DO NOT:
#   - Import from app/api/（跨层调用禁止）
#   - Hardcode prompt templates（走 prompt_config service）

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Provenance(BaseModel):
    """创建 Artifact 的来源追溯。

    [Harness: Observability #6] 每个 Artifact 携带完整 lineage。
    provenance 链支持: "报告结论 X 来源自分析 Y，分析 Y 使用了 SQL Z，SQL Z 查询了表 T。"
    """

    agent_name: str  # Explorer | Insight | Reporter
    tool_name: str  # generate_sql | execute_sql | ...
    input_artifact_ids: list[str] = []  # 上游 Artifact ID 列表
    observation_id: str  # 关联的 Observation 记录 ID

    model_config = ConfigDict(frozen=True, extra="forbid")  # 不可变，拒绝未知字段


class Artifact(BaseModel):
    """Agent 执行过程中产生的不可变、带类型、可追溯的输出。

    [Harness: Observability #6] Artifact 记录"是什么"——实际数据。
    Observation 记录"怎么产生的"——工具调用过程。
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: Literal[
        "knowledge",  # 召回的行业知识
        "schema",  # 表/字段元数据
        "sql",  # 生成的 SQL 文本
        "table",  # SQL 执行结果（rows + columns）
        "python_code",  # 生成的 Python 代码
        "chart",  # 图表文件路径/URL
        "analysis",  # Python 分析输出文本
        "report",  # 最终报告（HTML 或 Markdown）
        "human_feedback",  # 人工确认输入
    ]
    content: Any  # 实际数据，结构因 type 而异
    provenance: Provenance
    created_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(frozen=True, extra="forbid")  # 创建后不可修改，拒绝未知字段

    def summary(self, max_len: int = 80) -> str:
        """生成单行摘要，用于 SSE 展示和 Observation output_summary。"""
        if self.type == "sql":
            sql = str(self.content)
            return sql[:max_len] + "..." if len(sql) > max_len else sql
        if self.type == "table":
            if isinstance(self.content, dict):
                rows = len(self.content.get("rows", []))
                cols = len(self.content.get("columns", []))
                return f"Table: {rows} rows x {cols} columns"
            return f"Table: {type(self.content).__name__}"
        if self.type == "knowledge":
            items = len(self.content) if isinstance(self.content, list) else 1
            return f"Knowledge: {items} item(s)"
        if self.type == "chart":
            return f"Chart: {self.content}"
        return str(self.content)[:max_len]


class Observation(BaseModel):
    """一次工具调用的完整记录。

    [Harness: Observability #6] 每次工具调用无论成功失败都产生 Observation。
    Orchestrator 收集全部 Observation 用于 per-run 指标统计
    （总 token、总 LLM 调用次数、每步耗时分布）。
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    tool_name: str  # 调用了哪个工具
    agent_name: str  # 哪个 Agent 发起的调用
    input_summary: str  # 输入摘要（截断 ≤ 200 字符）
    output_summary: str  # 输出摘要（截断 ≤ 200 字符）
    status: Literal["ok", "error"]
    artifact_ids: list[str] = []  # 本次调用产出的 Artifact ID 列表
    error_code: str | None = None  # 来自 AgentRuntimeError，status="error" 时填充
    error_severity: Literal["retryable", "fatal"] | None = None
    duration_ms: int  # 工具调用实际耗时（ms）
    tokens_used: int = 0  # LLM token 消耗（非 LLM 工具为 0）
    timestamp: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(frozen=True, extra="forbid")  # 创建后不可修改，拒绝未知字段

    @model_validator(mode="after")
    def validate_error_fields(self):
        """status="error" 时 error_code 必填；status="ok" 时 error_code 必须为 None。"""
        if self.status == "error" and not self.error_code:
            raise ValueError("Observation with status='error' must have error_code")
        if self.status == "ok" and self.error_code:
            raise ValueError("Observation with status='ok' must not have error_code")
        return self
