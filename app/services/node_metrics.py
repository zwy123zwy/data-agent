"""
节点级执行指标追踪 — 对齐 Java NodeMetricsTracker

提供每个工作流节点的独立计时、状态追踪和结构化日志输出。
被 streaming_graph_controller 的 stream_workflow_execution 调用。

输出格式（结构化 JSON 日志）:
{
  "threadId": "uuid",
  "agentId": "1",
  "sessionId": "",
  "nodeName": "SqlGenerateNode",
  "startTime": "2026-05-05T22:30:00",
  "endTime": "2026-05-05T22:30:02",
  "durationMs": 2340,
  "status": "success",
  "retryCount": 1,
  "errorType": null,
  "errorMessage": null
}
"""
import time
import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class NodeMetrics:
    """单个节点的执行指标"""

    __slots__ = (
        "thread_id", "agent_id", "session_id", "node_name",
        "start_time", "end_time", "duration_ms",
        "status", "retry_count", "error_type", "error_message",
    )

    def __init__(
        self,
        thread_id: str,
        agent_id: int,
        node_name: str,
        session_id: str = "",
    ):
        self.thread_id = thread_id
        self.agent_id = str(agent_id)
        self.session_id = session_id
        self.node_name = node_name
        self.start_time: Optional[str] = None
        self.end_time: Optional[str] = None
        self.duration_ms: int = 0
        self.status: str = "running"
        self.retry_count: int = 0
        self.error_type: Optional[str] = None
        self.error_message: Optional[str] = None

    def start(self):
        self.start_time = datetime.now(timezone.utc).isoformat()

    def finish(self, status: str = "success", error: Optional[Exception] = None):
        self.end_time = datetime.now(timezone.utc).isoformat()
        if self.start_time:
            start_dt = datetime.fromisoformat(self.start_time)
            end_dt = datetime.fromisoformat(self.end_time)
            self.duration_ms = int((end_dt - start_dt).total_seconds() * 1000)
        self.status = status
        if error:
            self.error_type = type(error).__name__
            self.error_message = str(error)[:200]

    def to_dict(self) -> dict:
        return {
            "threadId": self.thread_id,
            "agentId": self.agent_id,
            "sessionId": self.session_id,
            "nodeName": self.node_name,
            "startTime": self.start_time or "",
            "endTime": self.end_time or "",
            "durationMs": self.duration_ms,
            "status": self.status,
            "retryCount": self.retry_count,
            "errorType": self.error_type,
            "errorMessage": self.error_message,
        }

    def log(self):
        """输出结构化 JSON 日志"""
        logger.info(f"[Metrics] {json.dumps(self.to_dict(), ensure_ascii=False)}")


class NodeMetricsTracker:
    """节点指标收集器 — 在 stream 循环中使用

    用法:
        tracker = NodeMetricsTracker(thread_id, agent_id, session_id)
        for node_name, node_output in astream_events:
            m = tracker.start_node(node_name)
            # ... process node ...
            m.finish("success")
            m.log()
    """

    def __init__(self, thread_id: str, agent_id: int, session_id: str = ""):
        self.thread_id = thread_id
        self.agent_id = agent_id
        self.session_id = session_id
        self.node_executions: list[NodeMetrics] = []

    def start_node(self, node_name: str, retry_count: int = 0) -> NodeMetrics:
        m = NodeMetrics(
            thread_id=self.thread_id,
            agent_id=self.agent_id,
            node_name=node_name,
            session_id=self.session_id,
        )
        m.retry_count = retry_count
        m.start()
        logger.info(f"[Metrics] start node {node_name}")
        self.node_executions.append(m)
        return m

    def summary(self) -> dict:
        """汇总所有节点执行指标"""
        total = len(self.node_executions)
        if total == 0:
            return {"totalNodes": 0}
        succeeded = sum(1 for m in self.node_executions if m.status == "success")
        failed = sum(1 for m in self.node_executions if m.status == "error")
        durations = [m.duration_ms for m in self.node_executions if m.duration_ms > 0]
        return {
            "threadId": self.thread_id,
            "agentId": str(self.agent_id),
            "sessionId": self.session_id,
            "totalNodes": total,
            "succeeded": succeeded,
            "failed": failed,
            "totalDurationMs": sum(durations),
            "avgDurationMs": sum(durations) // len(durations) if durations else 0,
            "maxDurationMs": max(durations) if durations else 0,
            "nodes": [m.to_dict() for m in self.node_executions],
        }

    def log_summary(self):
        """输出汇总指标日志"""
        s = self.summary()
        logger.info(
            f"[MetricsSummary] thread={s.get('threadId')} "
            f"nodes={s.get('totalNodes')} "
            f"ok={s.get('succeeded')} fail={s.get('failed')} "
            f"totalMs={s.get('totalDurationMs')} "
            f"avgMs={s.get('avgDurationMs')} "
            f"maxMs={s.get('maxDurationMs')}"
        )
