"""
WorkflowNode 基类 — Agent = Model + Harness 的最小约束单元

每个节点自声明:
  - I/O 契约 (requires/provides) → Harness 控制层做静态校验
  - SSE 输出 (format_sse)        → Controller 不再窥探节点内部
  - 适用范围 (applicable_data_sources) → 编排层路由依据

Harness 三层映射:
  控制层 → requires/provides 校验 + Langfuse 自动埋点
  记忆层 → state checkpointer (LangGraph 原生)
  编排层 → applicable_data_sources → graph.py 路由
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class SSEPayload:
    """节点对前端的自描述输出 — Controller 只转发，不解析

    Java 对应: GraphNodeResponse 的 text + textType 字段

    V3.0 新增字段 (全部可选, 向后兼容):
      - agent_name:  所属 Agent (Explorer/Analyst/Reporter)
      - tool_name:   当前 tool 名称 (get_schema / execute_sql / text_to_sql / ...)
      - tool_status: tool 执行状态 (pending / running / done / error)
      - tool_summary: tool 结果摘要 (单行, < 80 字符)
    """
    text: str
    text_type: str = "TEXT"  # SQL | JSON | HTML | MARK_DOWN | RESULT_SET | PYTHON | TEXT
    metrics_delta: Dict[str, Any] = field(default_factory=dict)
    # V3.0: Agent/Tool 归属声明 — Phase 2 前端直接读取, 不再需要 nodeName 硬编码推断
    agent_name: Optional[str] = None    # Explorer | Analyst | Reporter
    tool_name: Optional[str] = None     # get_schema | execute_sql | text_to_sql | ...
    tool_status: Optional[str] = None   # pending | running | done | error
    tool_summary: Optional[str] = None  # 单行结果摘要


class WorkflowNode(ABC):
    """Harness 增强的 LangGraph 节点基类

    子类只需实现:
      - execute(state) → dict         业务逻辑
      - format_sse(output) → SSEPayload | None  前端输出

    基类自动处理:
      - Langfuse span 埋点
      - sse_output 注入到 state update

    用法:
      class MyNode(WorkflowNode):
          name = "my_node"
          description = "做什么"
          requires = ["input_key"]
          provides = ["output_key"]

          async def execute(self, state): ...
          def format_sse(self, output): ...

      # LangGraph 兼容 — 实例可直接作为 node 函数
      graph.add_node("my_node", MyNode())
    """

    # ─── 子类必须定义 ───
    name: str = ""
    description: str = ""

    # ─── I/O 契约 ───
    requires: List[str] = []
    provides: List[str] = []

    # ─── 适用范围 — 编排层路由依据 ───
    applicable_data_sources: List[str] = ["*"]

    # ─── Harness 约束 ───
    max_retries: int = 0
    timeout_seconds: int = 30

    @abstractmethod
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """业务逻辑 — 子类唯一必须实现的

        Args:
            state: LangGraph WorkflowState 字典

        Returns:
            state update dict (会被 LangGraph 自动 merge 回 state)
        """
        ...

    def format_sse(self, output: Dict[str, Any]) -> Optional[SSEPayload]:
        """自描述 SSE 输出 — Controller 读取此方法的返回值发送给前端

        返回 None 表示此节点不产生用户可见输出（内部节点）。

        Args:
            output: execute() 的返回值（即本次 state update）

        Returns:
            SSEPayload 或 None
        """
        return None

    # ─── Langfuse 自动埋点 ───

    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """LangGraph 入口 — 自动 Langfuse 埋点 + SSE 注入

        LangGraph 调用 node(state) → 返回 state update dict
        基类在此自动:
          1. 创建 Langfuse trace span
          2. 调用 execute()
          3. 注入 sse_output 到返回值
          4. 记录 span 指标
        """
        from ..services.langfuse_service import get_langfuse_service

        # 单个节点的执行顺序:
        # 1. LangGraph 根据 graph.py 的边调用当前 WorkflowNode 实例。
        # 2. 基类先开启 Langfuse span，记录节点名和 I/O 契约。
        # 3. 子类 execute(state) 执行业务逻辑，只返回本节点新增或修改的 state update。
        # 4. 子类 format_sse(result) 把本节点希望前端看到的内容声明为 SSEPayload。
        # 5. 基类把 SSEPayload 注入 result["sse_output"]，Controller 再统一转成 SSE。
        langfuse = get_langfuse_service()
        trace_id = state.get("trace_thread_id") or state.get("agent_id", "unknown")

        span_id = langfuse.start_span(
            name=self.name,
            trace_id=str(trace_id),
            metadata={
                "node": self.name,
                "requires": self.requires,
                "provides": self.provides,
            },
        )

        try:
            result = await self.execute(state)

            # 自动注入 SSE 输出
            sse = self.format_sse(result)
            # [旧代码] 只注入 text + textType
            # if sse is not None:
            #     result["sse_output"] = {
            #         "text": sse.text,
            #         "textType": sse.text_type,
            #     }
            #     if sse.metrics_delta:
            #         result.setdefault("_metrics_delta", {}).update(sse.metrics_delta)
            if sse is not None:
                sse_dict = {
                    "text": sse.text,
                    "textType": sse.text_type,
                }
                # V3.0: 透传 Agent/Tool 归属声明到 Controller → 前端
                # 仅非 None 时注入, 避免 SSE 消息中出现 null 值字段
                if sse.agent_name:
                    sse_dict["agentName"] = sse.agent_name
                if sse.tool_name:
                    sse_dict["toolName"] = sse.tool_name
                if sse.tool_status:
                    sse_dict["toolStatus"] = sse.tool_status
                if sse.tool_summary:
                    sse_dict["toolSummary"] = sse.tool_summary
                result["sse_output"] = sse_dict
                # ★ 保留 metrics_delta: Controller 依赖此字段收集核心指标
                if sse.metrics_delta:
                    result.setdefault("_metrics_delta", {}).update(sse.metrics_delta)

            langfuse.finish_span(span_id, status="success")
            return result

        except Exception as e:
            langfuse.finish_span(span_id, status="error", metadata={"error": str(e)[:200]})
            logger.error(f"[Node] {self.name} failed: {e}")
            raise
