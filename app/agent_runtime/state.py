# [Harness: A2A #2 + Routing #3] V2 Agent Runtime — LangGraph State 类型定义
#
# AgentRunState 是 Orchestrator StateGraph 中流转的全局状态 TypedDict。
# 与 V1 WorkflowState（60+ key，平坦结构）不同，新 state 按逻辑分组，
# 内嵌 RuntimeContext、Observations、Artifacts 等结构化字段。
#
# 本模块是 V2 Agent Runtime 的一部分。参考 CLAUDE.md 了解 Harness Engineering 理念。
#
# DO NOT:
#   - Import from app/api/（跨层调用禁止）
#   - Hardcode prompt templates（走 prompt_config service）

from typing import NotRequired, Required, TypedDict


class RunMetrics(TypedDict, total=False):
    """单次 run 的聚合指标。由 Orchestrator 在 run 结束时收集。

    [Harness: Observability #6 + Routing #3]
    """

    total_llm_calls: int  # LLM 调用总次数
    total_tokens: int  # token 消耗总量
    total_duration_ms: int  # 从开始到结束的总耗时
    tools_called: list[str]  # 被调用的工具名称列表（去重）
    errors_count: int  # ToolResult(status="error") 的数量


class AgentRunState(TypedDict, total=False):
    """V2 Agent Runtime LangGraph 全局状态。

    [Harness: A2A #2, Routing #3] 此 state 在 Orchestrator 的 StateGraph 中流转。
    每个节点读取/写入特定的 key。

    total=False 使大部分字段可选，但 Controller 必须提供的 5 个 input 字段
    用 Required 标记。

    与 V1 WorkflowState 的关键区别:
      - 结构化: 相关字段分组为 RuntimeContext、IntentState
      - Observability 原生: observations 和 artifacts 是一等公民
      - 熔断内建: round_count、max_rounds、total_tokens 强制执行
      - HITL 原生: 人工审批字段是 state 的一部分，非临时 hack
    """

    # ── INPUT（Controller 设置，必须提供）──
    agent_id: Required[int]
    user_query: Required[str]
    thread_id: Required[str]
    mode: Required[str]  # smart_query | deep_research | report | chitchat | clarification
    run_id: Required[str]  # 本次 run 的 UUID（Observability #6）

    # ── ASSEMBLED（ContextEngine 节点设置）──
    runtime: NotRequired[dict | None]  # RuntimeContext 序列化为 dict（LangGraph state 约束）

    # ── ROUTING（Gateway 节点设置）──
    intent: NotRequired[dict | None]  # IntentState 序列化为 dict

    # ── PLANNING（Orchestrator Plan 阶段设置）──
    plan: NotRequired[list[dict]]  # 执行计划: [{"step": 1, "description": "...", "agent": "Explorer"}]
    current_step: NotRequired[int]  # 1-based 当前步骤索引

    # ── EXECUTION LOGS（Agent 追加，Report Agent 读取）──
    observations: NotRequired[list[dict]]  # Observation 记录列表（dict 形式）
    artifacts: NotRequired[list[dict]]  # Artifact 记录列表（dict 形式）

    # ── AGENT OUTPUTS ──
    sql_results: NotRequired[list[dict]]  # 累积的 SQL 执行结果
    python_results: NotRequired[list[dict]]  # 累积的 Python 分析结果

    # ── FINAL OUTPUT ──
    final_answer: NotRequired[str | None]  # 最终回复文本
    report_html: NotRequired[str | None]  # HTML 报告
    report_markdown: NotRequired[str | None]  # Markdown 报告

    # ── CIRCUIT BREAKER [Harness: Routing #3] ──
    round_count: NotRequired[int]  # 每次 React 循环递增
    max_rounds: NotRequired[int]  # 硬限制: 10 (smart_query) / 30 (deep_research)
    total_tokens: NotRequired[int]  # 运行中累计，与预算比较
    total_cost_estimate: NotRequired[float]  # 粗略费用估算（USD）

    # ── HITL [Harness: Sandbox #5] ──
    needs_human_approval: NotRequired[bool]  # 设置为 True 触发 interrupt()
    human_approval_granted: NotRequired[bool | None]  # None = 尚未响应
    human_feedback: NotRequired[str | None]  # 用户反馈文本

    # ── ERROR ──
    error: NotRequired[str | None]  # 致命错误消息，设置后 → 路由到 END

    # ── TRACE ──
    metrics: NotRequired[RunMetrics | None]  # run.complete 时填充
