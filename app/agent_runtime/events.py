# [Harness: Observability #6] V2 Agent Runtime — SSE 事件帧模型
#
# AgentSSEEvent 是唯一的 SSE data frame 类型。
# 每次 run 中的所有事件均为此模型的一个实例。
# 同时承载 V2 语义字段（新前端）和 V1 兼容字段（旧前端 fallback）。
#
# 序列化使用 camelCase alias，对齐前端 JS 命名规范。
#
# 本模块是 V2 Agent Runtime 的一部分。参考 CLAUDE.md 了解 Harness Engineering 理念。
#
# DO NOT:
#   - Import from app/api/（跨层调用禁止）
#   - Hardcode prompt templates（走 prompt_config service）

from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

# [SSOT] V2 eventType 枚举 — 与 docs/ARCHITECTURE.md §8、前端 types/graph.ts 保持一致
AgentEventType = Literal[
    "agent.think",
    "tool.call",
    "tool.result",
    "text.delta",
    "agent.complete",
    "clarification.requested",
    "run.complete",
    "error",
]

AGENT_EVENT_TYPES: tuple[str, ...] = get_args(AgentEventType)


class AgentSSEEvent(BaseModel):
    """Agent 执行过程中的一条 SSE 数据帧。

    [Harness: Observability #6] 双协议设计:
      - V2 前端读取: runId, eventType, agentName, action, status, summary, artifactRefs
      - V1 前端读取: agentId, threadId, nodeName, textType, text, error, complete

    序列化使用 camelCase alias，前端直接解构。
    """

    # ── V2 语义字段（新前端读取）──
    run_id: str | None = Field(default=None, alias="runId")
    event_type: AgentEventType | None = Field(default=None, alias="eventType")
    # Gateway / 澄清等场景可能无 agentName；已知 Agent 为 Explorer | Insight | Reporter
    agent_name: str | None = Field(default=None, alias="agentName")
    action: str | None = Field(default=None, alias="action")
    status: Literal["running", "ok", "error"] | None = Field(default=None, alias="status")
    summary: str | None = Field(
        default=None, alias="summary"
    )  # 人类可读摘要，≤ 200 字符
    artifact_refs: list[dict] | None = Field(default=None, alias="artifactRefs")
    # artifact_refs 格式: [{"id": "...", "type": "sql"}, ...]

    # ── V1 兼容字段（旧前端 fallback）──
    agent_id: int = Field(alias="agentId")
    thread_id: str = Field(alias="threadId")
    node_name: str = Field(alias="nodeName")  # 映射到最近的 V1 节点名
    text_type: str = Field(default="TEXT", alias="textType")
    text: str = Field(default="", alias="text")  # = summary，供 V1 前端 fallback
    error: str | None = Field(default=None, alias="error")
    complete: bool = Field(default=False, alias="complete")

    model_config = ConfigDict(
        populate_by_name=True,  # 构造函数同时接受 "run_id" 和 "runId"
        extra="forbid",  # 拒绝未知字段
    )

    @classmethod
    def create_v2_only(
        cls,
        run_id: str,
        event_type: AgentEventType,
        agent_id: int,
        thread_id: str,
        agent_name: str | None = None,
        status: str | None = None,
        summary: str | None = None,
        artifact_refs: list[dict] | None = None,
        error: str | None = None,
        text_type: str = "TEXT",
        text: str | None = None,
        action: str | None = None,
    ) -> "AgentSSEEvent":
        """工厂方法: 从 V2 字段创建事件，V1 兼容字段自动填充。

        node_name 和 text 由 agent_name 和 summary 自动派生，
        确保旧前端 fallback 到 V1 渲染路径时不会空白。

        参数:
            run_id: 本次 run 的 UUID
            event_type: 事件类型（agent.think | tool.call | tool.result | ...）
            agent_id: Agent 配置 ID
            thread_id: 会话 thread ID
            agent_name: Agent 名称（Explorer | Insight | Reporter），可选
            status: 状态（running | ok | error），可选
            summary: 人类可读摘要，可选
            artifact_refs: 产出的 Artifact 引用列表，可选
            error: 错误信息，可选
            text_type: V1 文本类型（如 RESULT_SET、SQL）
            text: V1 正文（默认用 summary）
            action: V2 工具名或动作

        返回:
            AgentSSEEvent 实例，V1 兼容字段已自动填充
        """
        body = text if text is not None else (summary or "")
        return cls(
            run_id=run_id,
            event_type=event_type,
            agent_name=agent_name,
            action=action,
            status=status or ("running" if event_type != "error" else "error"),
            summary=summary,
            artifact_refs=artifact_refs,
            agent_id=agent_id,
            thread_id=thread_id,
            node_name=agent_name or "UNDEFINED",
            text=body,
            text_type=text_type,
            error=error,
            complete=(event_type == "run.complete"),
        )
