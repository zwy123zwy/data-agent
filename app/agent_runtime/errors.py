# [Harness: Tool #1 + Observability #6] V2 Agent Runtime — unified error hierarchy
#
# 每个运行时异常携带 machine-readable error_code（Observability #6）
# 和 severity（retryable vs fatal，Tool #1 契约要求）。
#
# 本模块是 V2 Agent Runtime 的一部分。参考 CLAUDE.md 了解 Harness Engineering 理念。
#
# DO NOT:
#   - Import from app/api/（跨层调用禁止）
#   - Hardcode prompt templates（走 prompt_config service）

from datetime import datetime
from typing import Literal


class AgentRuntimeError(Exception):
    """V2 Agent Runtime 统一异常基类。

    error_code: 机器可读，跨版本稳定（如 "LLM_TIMEOUT", "SQL_SYNTAX_ERROR"）
    severity:   retryable = 调用方可修改参数重试
                fatal     = 调用方必须中止当前执行路径
    timestamp:  异常发生时间（Observability #6 记录）
    context:    调试用结构化数据（不展示给用户）
    """

    error_code: str
    severity: Literal["retryable", "fatal"]
    message: str
    timestamp: datetime
    context: dict  # __init__ 中 None → {} 转换，运行时始终为 dict

    def __init__(
        self,
        error_code: str,
        severity: Literal["retryable", "fatal"],
        message: str,
        context: dict | None = None,
    ):
        self.error_code = error_code
        self.severity = severity
        self.message = message
        self.timestamp = datetime.now()
        self.context = context or {}
        super().__init__(message)

    def to_dict(self) -> dict:
        """序列化为 SSE error 事件和 DB 日志格式。"""
        return {
            "error_code": self.error_code,
            "severity": self.severity,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context,
        }


class ToolError(AgentRuntimeError):
    """BaseTool.execute() 失败时抛出。

    [Harness: Tool #1] 所有 tool 失败统一走此类型。
    Tool wrapper 捕获原始异常后转换为 ToolError，
    再构造 ToolResult(status="error")。
    """
    pass


class OrchestratorError(AgentRuntimeError):
    """Orchestrator 执行循环无法继续时抛出。

    示例: max_rounds 超限、Agent subgraph 返回无效状态、
          三路 SQL 投票全部失败。
    """
    pass


class GatewayError(AgentRuntimeError):
    """Gateway 意图分类不可恢复失败时抛出。

    示例: LLM 返回无法解析的 JSON、分类超时、
          所有路由路径耗尽。
    """
    pass


class ContextEngineError(AgentRuntimeError):
    """ContextEngine RuntimeContext 装配不可恢复失败时抛出。

    注意: ContextEngine 设计为优雅降级——单个 datasource
    失败不会抛此异常。仅在整体装配无效时抛出
    （如 agent_id 不存在）。
    """
    pass
