# [阶段2] Harness SSE 事件帧（字段与前端 types/graph.ts 对齐，独立于 agent_runtime.events）
# [Harness: Observability #6]
#
# 双工厂方法说明:
#   create()         — 完整构造，从 V2 字段填充 V1 兼容字段（nodeName, text, textType, complete）
#   create_v2_only() — 薄封装，参数签名与 AgentSSEEvent.create_v2_only 对齐，方便调用方迁移
#   两者最终走同一 create() 路径，产物完全一致。create_v2_only 是为与旧 agent_runtime
#   AgentSSEEvent 保持 API 一致性的适配层。

from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

HarnessEventType = Literal[
    "agent.think",
    "tool.call",
    "tool.result",
    "tools.available",
    "text.delta",
    "agent.complete",
    "clarification.requested",
    "run.complete",
    "error",
]

HARNESS_EVENT_TYPES: tuple[str, ...] = get_args(HarnessEventType)


class HarnessSSEEvent(BaseModel):
    """[阶段2] V2 SSE data 帧；序列化 camelCase alias 供前端消费。"""

    run_id: str | None = Field(default=None, alias="runId")
    event_type: HarnessEventType | None = Field(default=None, alias="eventType")
    agent_name: str | None = Field(default=None, alias="agentName")
    action: str | None = Field(default=None, alias="action")
    status: Literal["running", "ok", "error"] | None = Field(default=None, alias="status")
    summary: str | None = Field(default=None, alias="summary")
    artifact_refs: list[dict] | None = Field(default=None, alias="artifactRefs")

    agent_id: int = Field(alias="agentId")
    thread_id: str = Field(alias="threadId")
    node_name: str = Field(alias="nodeName")
    text_type: str = Field(default="TEXT", alias="textType")
    text: str = Field(default="", alias="text")
    error: str | None = Field(default=None, alias="error")
    complete: bool = Field(default=False, alias="complete")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        event_type: HarnessEventType,
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
    ) -> "HarnessSSEEvent":
        """[阶段2] 从 V2 字段创建事件并填充 V1 兼容字段。"""
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
            node_name=agent_name or "Harness",
            text=body,
            text_type=text_type,
            error=error,
            complete=(event_type == "run.complete"),
        )

    @classmethod
    def create_v2_only(
        cls,
        run_id: str,
        event_type: HarnessEventType,
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
    ) -> "HarnessSSEEvent":
        """[阶段2] 工厂方法：与 AgentSSEEvent.create_v2_only 字段对齐。"""
        return cls.create(
            run_id=run_id,
            event_type=event_type,
            agent_id=agent_id,
            thread_id=thread_id,
            agent_name=agent_name,
            status=status,
            summary=summary,
            artifact_refs=artifact_refs,
            error=error,
            text_type=text_type,
            text=text,
            action=action,
        )
