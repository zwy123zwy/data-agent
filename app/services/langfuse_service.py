"""
Langfuse 可观测性服务 — 对齐 Java LangfuseService
Span 追踪、Token 统计、Trace 管理
"""
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from ..core.config import settings
import logging
import time
import uuid

logger = logging.getLogger(__name__)


class TraceSpan:
    """Trace Span — 对齐 Java Langfuse Span"""

    def __init__(
        self,
        name: str,
        trace_id: str,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.trace_id = trace_id
        self.parent_id = parent_id
        self.metadata = metadata or {}
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.input_tokens = 0
        self.output_tokens = 0
        self.status = "running"

    def finish(self, status: str = "success", metadata: Optional[Dict[str, Any]] = None):
        self.end_time = time.time()
        self.status = status
        if metadata:
            self.metadata.update(metadata)

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return (time.time() - self.start_time) * 1000

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class LangfuseService:
    """Langfuse 可观测性服务 — 对齐 Java LangfuseService

    功能:
    - Trace 管理（创建、结束）
    - Span 追踪（node 级别）
    - Token 统计
    """

    def __init__(self):
        self.enabled = settings.langfuse.enabled
        self.traces: Dict[str, Dict[str, Any]] = {}
        self.spans: Dict[str, TraceSpan] = {}
        if self.enabled:
            logger.info("[Langfuse] Observability enabled")
        else:
            logger.info("[Langfuse] Disabled (set LANGFUSE_ENABLED=true to enable)")

    # ===== Trace =====

    def create_trace(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """创建 Trace — 对齐 Java LangfuseService.createTrace()"""
        trace_id = str(uuid.uuid4())
        self.traces[trace_id] = {
            "id": trace_id,
            "name": name,
            "metadata": metadata or {},
            "start_time": time.time(),
            "status": "running",
            "spans": [],
        }
        if self.enabled:
            logger.info(f"[Langfuse] Trace created: {trace_id} ({name})")
        return trace_id

    def finish_trace(self, trace_id: str, status: str = "success"):
        """结束 Trace"""
        if trace_id in self.traces:
            self.traces[trace_id]["status"] = status
            self.traces[trace_id]["end_time"] = time.time()
            duration = (self.traces[trace_id]["end_time"] - self.traces[trace_id]["start_time"]) * 1000
            if self.enabled:
                logger.info(f"[Langfuse] Trace finished: {trace_id} ({status}, {duration:.0f}ms)")

    # ===== Span =====

    def start_span(
        self,
        name: str,
        trace_id: str,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """开始 Span — 对齐 Java LangfuseService.startSpan()"""
        span = TraceSpan(name=name, trace_id=trace_id, parent_id=parent_id, metadata=metadata)
        self.spans[span.id] = span
        if trace_id in self.traces:
            self.traces[trace_id]["spans"].append(span.id)
        if self.enabled:
            logger.debug(f"[Langfuse] Span started: {span.id} ({name})")
        return span.id

    def finish_span(
        self,
        span_id: str,
        status: str = "success",
        metadata: Optional[Dict[str, Any]] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ):
        """结束 Span — 对齐 Java LangfuseService.finishSpan()"""
        span = self.spans.get(span_id)
        if span:
            span.input_tokens = input_tokens
            span.output_tokens = output_tokens
            span.finish(status, metadata)
            if self.enabled:
                logger.debug(
                    f"[Langfuse] Span finished: {span_id} ({status}, "
                    f"{span.duration_ms:.0f}ms, {span.total_tokens} tokens)"
                )

    # ===== Token 统计 =====

    def log_generation(
        self,
        trace_id: str,
        name: str,
        input_tokens: int,
        output_tokens: int,
        model: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """记录一次 LLM 调用 — 对齐 Java LangfuseService.logGeneration()"""
        if not self.enabled:
            return
        logger.info(
            f"[Langfuse] Generation: {name} | model={model} | "
            f"input={input_tokens} output={output_tokens} | trace={trace_id}"
        )

    # ===== 查询 =====

    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """获取 Trace 信息"""
        return self.traces.get(trace_id)

    def get_trace_summary(self, trace_id: str) -> Dict[str, Any]:
        """获取 Trace 摘要"""
        trace = self.traces.get(trace_id)
        if not trace:
            return {"error": "Trace not found"}

        span_ids = trace.get("spans", [])
        total_tokens = sum(
            self.spans[sid].total_tokens for sid in span_ids if sid in self.spans
        )
        total_duration = sum(
            self.spans[sid].duration_ms for sid in span_ids if sid in self.spans
        )

        return {
            "trace_id": trace_id,
            "name": trace["name"],
            "status": trace["status"],
            "span_count": len(span_ids),
            "total_tokens": total_tokens,
            "total_duration_ms": total_duration,
        }


# 全局实例
_langfuse_service: Optional[LangfuseService] = None


def get_langfuse_service() -> LangfuseService:
    global _langfuse_service
    if _langfuse_service is None:
        _langfuse_service = LangfuseService()
    return _langfuse_service
