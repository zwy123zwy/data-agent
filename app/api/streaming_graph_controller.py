"""
流式查询 API

【在系统中的地位】
  这是整个后端最重要的 API 文件。前端的所有数据分析请求都通过这里的
  SSE (Server-Sent Events) 端点进入，驱动 LangGraph 工作流执行。

【SSE 格式 — 对齐 Java ServerSentEvent<GraphNodeResponse>】
  Java 后端使用 Spring Flux<ServerSentEvent<GraphNodeResponse>> 发送 SSE:
    - 所有数据消息: plain SSE data: (无 event: 前缀) → 前端 EventSource.onmessage 接收
    - 完成事件: event: complete → 前端 addEventListener('complete', ...)
    - 错误事件: event: error

  GraphNodeResponse 结构:
    {agentId, threadId, nodeName, textType, text, error, complete}

  TextType 枚举值: SQL, JSON, HTML, MARK_DOWN, RESULT_SET, PYTHON, TEXT
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from langgraph.types import Command
from ..core.database import get_db
from ..schemas.query import QueryRequest
from ..workflows.graph import get_compiled_workflow
from ..workflows.state import WorkflowState
from ..services.agent_service import AgentService
from ..services.agent_datasource_service import AgentDatasourceService
from ..services.semantic_model_service import SemanticModelService
from ..services.node_metrics import NodeMetricsTracker
from ..services.metrics_aggregation_service import MetricsAggregationService
import asyncio
import json
import logging
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["流式查询"])

# ============================================================================
# Python → Java 节点名映射
# 前端通过 nodeName 分组展示消息块，更换 nodeName 时创建新的消息块
# Java 节点名来自 Constant.java 的 *_NODE 常量，但 Spring AI output.node()
# 返回的是类简单名称（如 ReportGeneratorNode），前端根据此值做特殊处理
# ============================================================================
NODE_NAME_MAP = {
    "intent_recognition": "IntentRecognitionNode",
    "knowledge_recall": "EvidenceRecallNode",
    "query_rewrite": "QueryEnhanceNode",
    "schema_recall": "SchemaRecallNode",
    "table_relation": "TableRelationNode",
    "feasibility": "FeasibilityAssessmentNode",
    "planner": "PlannerNode",
    "plan_executor": "PlanExecutorNode",
    "sql_generate": "SqlGenerateNode",
    "semantic_consistency": "SemanticConsistencyNode",
    "sql_execute": "SqlExecuteNode",
    "python_generate": "PythonGenerateNode",
    "python_execute": "PythonExecuteNode",
    "python_analyze": "PythonAnalyzeNode",
    "report_generator": "ReportGeneratorNode",
    "human_feedback": "HumanFeedbackNode",
}

# TextType 枚举 — 对齐 Java TextType enum 和前端 TextType enum
# 前端定义: JSON='JSON', PYTHON='PYTHON', SQL='SQL', HTML='HTML',
#           MARK_DOWN='MARK_DOWN', RESULT_SET='RESULT_SET', TEXT='TEXT'
TEXT_TYPE_SQL = "SQL"
TEXT_TYPE_JSON = "JSON"
TEXT_TYPE_HTML = "HTML"
TEXT_TYPE_MARK_DOWN = "MARK_DOWN"
TEXT_TYPE_RESULT_SET = "RESULT_SET"
TEXT_TYPE_PYTHON = "PYTHON"
TEXT_TYPE_TEXT = "TEXT"


def _build_graph_response(
    agent_id: int,
    thread_id: str,
    node_name: str,
    text: str,
    text_type: str = "TEXT",
    error: bool = False,
    complete: bool = False,
) -> dict:
    """构建 GraphNodeResponse 响应"""
    return {
        "agentId": str(agent_id),
        "threadId": thread_id or "",
        "nodeName": node_name,
        "textType": text_type,
        "text": text or "",
        "error": error,
        "complete": complete,
    }


def _format_sse_data(data: dict) -> str:
    """纯 data: 格式 (无 event: 前缀) — 前端 EventSource.onmessage 接收"""
    payload = json.dumps(data, ensure_ascii=False)
    return f"data: {payload}\n\n"


def _format_sse_event(event: str, data: dict) -> str:
    """命名 event: 格式 — 前端 addEventListener(event, ...) 接收"""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _build_initial_state(
    agent_id: int,
    user_query: str,
    nl2sql_only: bool = False,
    human_review: bool = False,
    multi_turn_context: str = "",
    semantic_model_prompt: str = "",
) -> WorkflowState:
    """构建初始 WorkflowState — 对齐 Java GraphRequest 字段映射"""
    return {
        "agent_id": agent_id,
        "user_query": user_query,
        "is_only_nl2sql": nl2sql_only,
        "human_review_enabled": human_review,
        "multi_turn_context": multi_turn_context,
        "semantic_model_prompt": semantic_model_prompt,
        "sql_retry_count": 0,
        "sql_generate_count": 0,
        "python_tries_count": 0,
        "plan_repair_count": 0,
        "plan_current_step": 1,
    }


async def stream_workflow_execution(
    agent_id: int,
    user_query: str,
    db: AsyncSession,
    thread_id: str | None = None,
    human_feedback: bool = False,
    human_feedback_content: str | None = None,
    rejected_plan: bool = False,
    nl2sql_only: bool = False,
):
    """流式执行工作流

    SSE 格式对齐 Java:
      - 每个节点输出 → 一条 data: GraphNodeResponse JSON (无 event: 前缀)
      - 流程完成 → event: complete + GraphNodeResponse(complete=true)
      - 流程错误 → event: error + GraphNodeResponse(error=true)
    """
    if not thread_id:
        thread_id = str(uuid.uuid4())

    config = {"configurable": {"thread_id": thread_id}}

    try:
        # 检查 Agent
        agent = await AgentService.get_agent(db, agent_id)
        if not agent:
            yield _format_sse_event("error", _build_graph_response(
                agent_id, thread_id, "", "Agent 不存在", TEXT_TYPE_TEXT, error=True
            ))
            await MetricsAggregationService.record_execution(
                db, thread_id=thread_id, agent_id=agent_id, status="error",
                total_duration_ms=0, total_nodes=0, succeeded_nodes=0, failed_nodes=1,
            )
            return

        # 检查数据源 — 获取激活的数据源及其 select_tables
        agent_ds_list = await AgentDatasourceService.list_agent_datasources(db, agent_id)
        active_agent_ds = next((item for item in agent_ds_list if item.is_active == 1), None)
        if not active_agent_ds:
            yield _format_sse_event("error", _build_graph_response(
                agent_id, thread_id, "", "没有激活的数据源", TEXT_TYPE_TEXT, error=True
            ))
            await MetricsAggregationService.record_execution(
                db, thread_id=thread_id, agent_id=agent_id, status="error",
                total_duration_ms=0, total_nodes=0, succeeded_nodes=0, failed_nodes=1,
            )
            return
        datasource_id = active_agent_ds.datasource_id
        select_tables = active_agent_ds.select_tables

        # 构建语义模型 Prompt
        semantic_model_prompt = ""
        if select_tables:
            parts = []
            for table_name in select_tables:
                info = await SemanticModelService.get_table_semantic_info(
                    db, agent_id, datasource_id, table_name
                )
                if info:
                    parts.append(info)
            semantic_model_prompt = "\n".join(parts)
            if semantic_model_prompt:
                logger.info(f"[Stream] Built semantic model prompt for {len(select_tables)} tables ({len(semantic_model_prompt)} chars)")

        # 构建初始状态
        initial_state = _build_initial_state(
            agent_id=agent_id,
            user_query=user_query,
            nl2sql_only=nl2sql_only,
            human_review=human_feedback,
            semantic_model_prompt=semantic_model_prompt,
        )

        # ===== 恢复路径：处理 HumanFeedback resume =====
        if thread_id and human_feedback_content:
            action = "reject" if rejected_plan else "approve"
            resume_cmd = Command(
                resume={"action": action, "reason": human_feedback_content},
            )
            graph_input = resume_cmd
        else:
            graph_input = initial_state

        # ===== 使用 astream(stream_mode="updates")  =====
        # Python 没有 Java 的 Token 级 StreamingOutput，每次 node 执行完毕
        # 产生一个完整的 state update，我们将其映射为一条 GraphNodeResponse
        # 只对用户可见的节点发送 SSE — 对齐 Java 版本行为
        # Java 中仅部分节点返回 StreamingOutput (Flux)，其余节点只返回 state 更新
        # 内部节点 (RAG、Schema、校验等) 不应暴露给前端
        user_visible_nodes = {
            "intent_recognition",
            "knowledge_recall",
            "query_rewrite",
            "schema_recall",
            "table_relation",
            "feasibility",
            "planner",
            "plan_executor",
            "sql_generate",
            "semantic_consistency",
            "sql_execute",
            "python_generate",
            "python_execute",
            "python_analyze",
            "report_generator",
            "human_feedback",
        }

        # ===== 节点指标追踪 — 对齐 Java NodeMetrics =====
        tracker = NodeMetricsTracker(thread_id, agent_id)

        # ===== Phase 7 核心指标收集 =====
        metrics_state: dict[str, bool | int | str | None] = {
            "intent_classification": None,
            "sql_generated": False,
            "sql_executed": False,
            "sql_success": False,
            "sql_semantic_pass": False,
            "python_executed": False,
            "python_success": False,
            "plan_first_pass": False,
            "plan_repair_count": 0,
            "report_generated": False,
            "hf_enabled": human_feedback,
            "hf_rejected": rejected_plan,
            "hf_reject_count": 0,
            "hf_final_status": None,
            "schema_tables_expected": len(select_tables) if select_tables else None,
        }

        async def _record_metrics(status: str = "success") -> None:
            """记录本次执行指标到数据库 (非致命)"""
            try:
                summary = tracker.summary()
                node_durations = {
                    m.node_name: m.duration_ms
                    for m in tracker.node_executions
                    if m.duration_ms > 0
                }
                await MetricsAggregationService.record_execution(
                    db,
                    thread_id=thread_id,
                    agent_id=agent_id,
                    status=status,
                    total_duration_ms=summary.get("totalDurationMs", 0),
                    total_nodes=summary.get("totalNodes", 0),
                    succeeded_nodes=summary.get("succeeded", 0),
                    failed_nodes=summary.get("failed", 0),
                    intent_classification=metrics_state.get("intent_classification"),
                    sql_generated=bool(metrics_state.get("sql_generated")),
                    sql_executed=bool(metrics_state.get("sql_executed")),
                    sql_success=bool(metrics_state.get("sql_success")),
                    sql_semantic_pass=bool(metrics_state.get("sql_semantic_pass")),
                    python_executed=bool(metrics_state.get("python_executed")),
                    python_success=bool(metrics_state.get("python_success")),
                    plan_first_pass=bool(metrics_state.get("plan_first_pass")),
                    plan_repair_count=int(metrics_state.get("plan_repair_count", 0)),
                    report_generated=bool(metrics_state.get("report_generated")),
                    hf_enabled=bool(metrics_state.get("hf_enabled")),
                    hf_rejected=bool(metrics_state.get("hf_rejected")),
                    hf_reject_count=int(metrics_state.get("hf_reject_count", 0)),
                    hf_final_status=metrics_state.get("hf_final_status"),
                    node_durations=node_durations,
                    schema_tables_expected=metrics_state.get("schema_tables_expected"),
                )
            except Exception:
                logger.exception("[Metrics] Non-fatal error recording execution metrics")

        compiled_workflow = await get_compiled_workflow()
        async for event in compiled_workflow.astream(graph_input, config, stream_mode="updates"):
            # ★ Handle LangGraph interrupt (HumanFeedback pause)
            # When human_feedback_node calls interrupt(), LangGraph yields
            # {"__interrupt__": (Interrupt(value),)} instead of the node output.
            # We must handle this BEFORE the user_visible_nodes check below.
            if "__interrupt__" in event:
                interrupt_data = event["__interrupt__"]
                interrupt_value = None
                if isinstance(interrupt_data, (list, tuple)) and len(interrupt_data) > 0:
                    interrupt_value = interrupt_data[0].value if hasattr(interrupt_data[0], 'value') else interrupt_data[0]
                elif hasattr(interrupt_data, 'value'):
                    interrupt_value = interrupt_data.value
                else:
                    interrupt_value = interrupt_data

                logger.info(f"[Stream] Interrupt: {interrupt_value}")

                # Send human_feedback node output as SSE data
                if isinstance(interrupt_value, dict):
                    java_name = NODE_NAME_MAP.get("human_feedback", "HumanFeedbackNode")
                    text = json.dumps(interrupt_value, ensure_ascii=False)
                    yield _format_sse_data(_build_graph_response(
                        agent_id, thread_id, java_name, text, TEXT_TYPE_JSON
                    ))

                # Send paused event so frontend knows this is a normal pause, not an error
                yield _format_sse_event("paused", _build_graph_response(
                    agent_id, thread_id, NODE_NAME_MAP.get("human_feedback", ""), "", TEXT_TYPE_TEXT
                ))
                tracker.log_summary()
                await _record_metrics("paused")
                return

            for node_name, node_output in event.items():
                if node_output is None:
                    logger.warning(f"[Stream] Node {node_name} returned None, skipping")
                    continue

                logger.info(f"[Stream] Node: {node_name}")
                m = tracker.start_node(NODE_NAME_MAP.get(node_name, node_name))

                if node_name not in user_visible_nodes:
                    m.finish("success")
                    m.log()
                    continue
                java_name = NODE_NAME_MAP.get(node_name, node_name)

                # ===== 意图识别 — 对齐 Java IntentRecognitionNode 流式输出 =====
                if node_name == "intent_recognition":
                    intent = node_output.get("intent", "")
                    classification = node_output.get("classification", "")
                    metrics_state["intent_classification"] = intent  # Phase 7: 记录意图分类
                    # 对齐 Java: "正在进行意图识别..." + JSON + "\n意图识别完成！"
                    json_part = json.dumps({"classification": classification}, ensure_ascii=False)
                    if intent == "data_analysis":
                        text = f"正在进行意图识别...{json_part}\n意图识别完成！"
                    else:
                        text = f"正在进行意图识别...{json_part}\n意图识别完成！"
                    yield _format_sse_data(_build_graph_response(
                        agent_id, thread_id, java_name, text, TEXT_TYPE_TEXT
                    ))
                    m.finish("success")
                    m.log()
                    if intent != "data_analysis":
                        yield _format_sse_event("complete", _build_graph_response(
                            agent_id, thread_id, "", "", TEXT_TYPE_TEXT, complete=True
                        ))
                        tracker.log_summary()
                        await _record_metrics("success")
                        return

                # ===== 知识召回 (对齐 Java EvidenceRecallNode 流式输出) =====
                elif node_name == "knowledge_recall":
                    knowledge_items = node_output.get("knowledge_items", [])
                    recalled = node_output.get("recalled_knowledge", "")
                    count = len(knowledge_items)
                    # 对齐 Java: "已找到 N 条相关证据文档"
                    if count:
                        lines = [f"正在检索相关知识...已找到 {count} 条相关证据文档"]
                        # 输出证据预览 (前3条，各限100字)
                        for idx, item in enumerate(knowledge_items[:3]):
                            content_preview = (item.get("content") or "")[:100]
                            lines.append(f"证据{idx + 1}: {content_preview}...")
                        text = "\n".join(lines)
                    elif recalled and recalled != "无":
                        text = f"正在检索相关知识...\n{recalled[:500]}"
                    else:
                        text = "正在检索相关知识...未找到证据文档"
                    yield _format_sse_data(_build_graph_response(
                        agent_id, thread_id, java_name, text, TEXT_TYPE_TEXT
                    ))
                    m.finish("success")
                    m.log()

                # ===== 查询改写 =====
                elif node_name == "query_rewrite":
                    rewritten = node_output.get("rewritten_query", "")
                    text = f"正在优化查询...\n{rewritten}" if rewritten else f"正在优化查询...(使用原始查询)"
                    yield _format_sse_data(_build_graph_response(
                        agent_id, thread_id, java_name, text, TEXT_TYPE_TEXT
                    ))
                    m.finish("success")
                    m.log()

                # ===== Schema 召回 =====
                elif node_name == "schema_recall":
                    schema_info = node_output.get("schema_info", {})
                    tables = schema_info.get("tables", []) if isinstance(schema_info, dict) else []
                    table_count = len(tables)
                    text = f"正在加载数据库表结构...找到 {table_count} 张表" if table_count else "正在加载数据库表结构..."
                    yield _format_sse_data(_build_graph_response(
                        agent_id, thread_id, java_name, text, TEXT_TYPE_TEXT
                    ))
                    m.finish("success")
                    m.log()

                # ===== 表关系分析 =====
                elif node_name == "table_relation":
                    schema_info = node_output.get("schema_info", {})
                    if isinstance(schema_info, dict):
                        relations = schema_info.get("relations", [])
                        table_count = len(schema_info.get("tables", []))
                        rel_count = len(relations)
                        text = f"正在分析表关系...{table_count} 张表, {rel_count} 条关系" if table_count else "正在分析表关系..."
                    else:
                        text = "正在分析表关系..."
                    yield _format_sse_data(_build_graph_response(
                        agent_id, thread_id, java_name, text, TEXT_TYPE_TEXT
                    ))
                    m.finish("success")
                    m.log()

                # ===== 可行性评估 =====
                elif node_name == "feasibility":
                    result = node_output.get("feasibility_result", {})
                    if isinstance(result, dict):
                        feasible = result.get("feasible", True)
                        reason = result.get("reason", "")
                        text = f"正在评估查询可行性...{'可行' if feasible else '不可行: ' + reason}"
                    else:
                        text = "正在评估查询可行性..."
                    yield _format_sse_data(_build_graph_response(
                        agent_id, thread_id, java_name, text, TEXT_TYPE_TEXT
                    ))
                    m.finish("success")
                    m.log()

                # ===== 计划生成 =====
                elif node_name == "planner":
                    plan_raw = node_output.get("query_plan", "")
                    try:
                        plan = json.loads(plan_raw) if isinstance(plan_raw, str) else plan_raw
                        steps = plan.get("execution_plan", []) if isinstance(plan, dict) else []
                        step_count = len(steps)
                        text = f"正在制定执行计划...共 {step_count} 个步骤"
                        # Phase 7: Plan首次校验通过 (Planner成功产出合法Plan)
                        if steps:
                            metrics_state["plan_first_pass"] = True
                    except (json.JSONDecodeError, TypeError):
                        text = "正在制定执行计划..."
                    yield _format_sse_data(_build_graph_response(
                        agent_id, thread_id, java_name, text, TEXT_TYPE_TEXT
                    ))
                    m.finish("success")
                    m.log()

                # ===== 计划执行调度 =====
                elif node_name == "plan_executor":
                    next_node = node_output.get("plan_next_node", "")
                    current_step = node_output.get("plan_current_step", 1)
                    repair_count = node_output.get("plan_repair_count", 0)
                    metrics_state["plan_repair_count"] = max(
                        int(metrics_state.get("plan_repair_count", 0)), int(repair_count)
                    )  # Phase 7
                    if next_node:
                        text = f"正在执行步骤 {current_step}..."
                    else:
                        text = "正在执行计划..."
                    yield _format_sse_data(_build_graph_response(
                        agent_id, thread_id, java_name, text, TEXT_TYPE_TEXT
                    ))
                    m.finish("success")
                    m.log()

                # ===== SQL 生成 =====
                elif node_name == "sql_generate":
                    sql = node_output.get("generated_sql", "")
                    if sql:
                        metrics_state["sql_generated"] = True  # Phase 7
                        yield _format_sse_data(_build_graph_response(
                            agent_id, thread_id, java_name, sql, TEXT_TYPE_SQL
                        ))
                    m.finish("success")
                    m.log()

                # ===== SQL 执行 =====
                elif node_name == "sql_execute":
                    error = node_output.get("sql_error")
                    result = node_output.get("sql_result")
                    sql_status = "error" if error else "success"
                    metrics_state["sql_executed"] = True  # Phase 7
                    metrics_state["sql_success"] = not error  # Phase 7
                    if error:
                        yield _format_sse_data(_build_graph_response(
                            agent_id, thread_id, java_name, f"SQL 执行错误: {error}", TEXT_TYPE_TEXT
                        ))
                        m.error_type = "SqlExecuteError"
                        m.error_message = error[:200]
                    elif result is not None:
                        text = json.dumps(result, ensure_ascii=False)
                        yield _format_sse_data(_build_graph_response(
                            agent_id, thread_id, java_name, text, TEXT_TYPE_RESULT_SET
                        ))
                    m.finish(sql_status)
                    m.log()

                # ===== 语义一致性校验 =====
                elif node_name == "semantic_consistency":
                    passed = node_output.get("semantic_consistency_result", False)
                    score = node_output.get("semantic_consistency_score", 0)
                    if passed:
                        metrics_state["sql_semantic_pass"] = True  # Phase 7
                    text = f"正在校验 SQL 语义...{'✓ 通过' if passed else '⚠ 未通过'}"
                    yield _format_sse_data(_build_graph_response(
                        agent_id, thread_id, java_name, text, TEXT_TYPE_TEXT
                    ))
                    m.finish("success" if passed else "error")
                    m.log()

                # ===== Python 代码生成 =====
                elif node_name == "python_generate":
                    code = node_output.get("python_code", "")
                    if code:
                        yield _format_sse_data(_build_graph_response(
                            agent_id, thread_id, java_name, code, TEXT_TYPE_PYTHON
                        ))
                    m.finish("success")
                    m.log()

                # ===== Python 代码执行 =====
                elif node_name == "python_execute":
                    is_success = node_output.get("python_is_success", False)
                    error = node_output.get("python_error", "")
                    metrics_state["python_executed"] = True  # Phase 7
                    metrics_state["python_success"] = is_success  # Phase 7
                    if is_success:
                        yield _format_sse_data(_build_graph_response(
                            agent_id, thread_id, java_name, "Python 代码执行成功", TEXT_TYPE_TEXT
                        ))
                    else:
                        yield _format_sse_data(_build_graph_response(
                            agent_id, thread_id, java_name, f"Python 代码执行失败: {error[:200]}" if error else "Python 代码执行中...", TEXT_TYPE_TEXT
                        ))
                    m.finish("success" if is_success else "error")
                    m.log()

                # ===== Python 分析 =====
                elif node_name == "python_analyze":
                    analysis = node_output.get("python_analysis", "")
                    yield _format_sse_data(_build_graph_response(
                        agent_id, thread_id, java_name, analysis or "", TEXT_TYPE_TEXT
                    ))
                    m.finish("success")
                    m.log()

                # ===== 报告生成 =====
                elif node_name == "report_generator":
                    html_report = node_output.get("html_report", "")
                    report = node_output.get("report", "")
                    markdown_report = node_output.get("markdown_report", "")
                    if html_report or markdown_report or report:
                        metrics_state["report_generated"] = True  # Phase 7

                    if html_report:
                        yield _format_sse_data(_build_graph_response(
                            agent_id, thread_id, java_name, html_report, TEXT_TYPE_HTML
                        ))
                    elif markdown_report:
                        yield _format_sse_data(_build_graph_response(
                            agent_id, thread_id, java_name, markdown_report, TEXT_TYPE_MARK_DOWN
                        ))
                    elif report:
                        yield _format_sse_data(_build_graph_response(
                            agent_id, thread_id, java_name, report, TEXT_TYPE_MARK_DOWN
                        ))
                    m.finish("success")
                    m.log()

                # ===== Human Feedback (interrupt 会在此暂停) =====
                elif node_name == "human_feedback":
                    if isinstance(node_output, dict) and node_output.get("type") == "human_feedback":
                        # Phase 7: 记录 HumanFeedback 状态
                        hf_action = node_output.get("action", "")
                        hf_reject_count_val = node_output.get("reject_count", 0)
                        metrics_state["hf_reject_count"] = int(hf_reject_count_val)
                        if hf_action == "reject":
                            metrics_state["hf_rejected"] = True
                        elif hf_action == "approve":
                            metrics_state["hf_final_status"] = "approved"
                        text = json.dumps(node_output, ensure_ascii=False)
                        yield _format_sse_data(_build_graph_response(
                            agent_id, thread_id, java_name, text, TEXT_TYPE_JSON
                        ))
                        # 发送 paused 事件 — 前端据此区分「正常暂停」和「连接异常断开」
                        # 前端 graph.ts 通过 addEventListener('paused', ...) 接收
                        yield _format_sse_event("paused", _build_graph_response(
                            agent_id, thread_id, java_name, "", TEXT_TYPE_TEXT
                        ))
                        m.finish("paused")
                        m.log()
                        tracker.log_summary()
                        await _record_metrics("paused")
                        # LangGraph interrupt 在此触发，流自然暂停
                        return

        # 发送完成事件 — 对齐 Java handleStreamComplete
        logger.info(f"[Stream] Complete, threadId={thread_id}")
        tracker.log_summary()
        await _record_metrics("success")
        yield _format_sse_event("complete", _build_graph_response(
            agent_id, thread_id, "", "", TEXT_TYPE_TEXT, complete=True
        ))

    except asyncio.CancelledError:
        logger.info(f"[Stream] Client disconnected, threadId={thread_id}, releasing resources")
        tracker.log_summary()
        await _record_metrics("cancelled")
        # 前端关闭 EventSource → 正常释放，不发送额外 SSE
        return
    except Exception as e:
        import traceback as tb
        tb.print_exc()
        logger.error(f"[Stream] Error for threadId={thread_id}: {e}\n{tb.format_exc()}")
        tracker.log_summary()
        await _record_metrics("error")
        yield _format_sse_event("error", _build_graph_response(
            agent_id, thread_id, "", str(e), TEXT_TYPE_TEXT, error=True
        ))


# ========== API 端点 ==========

@router.post("/query/stream")
async def stream_query(
    query_request: QueryRequest,
    db: AsyncSession = Depends(get_db),
):
    """流式查询接口（SSE）— Python 扩展接口

    这是 Python 版独有的 POST 端点，使用 JSON Body 传参（QueryRequest schema）。
    前端主链路以 GET /api/stream/search 为准（兼容 Java 前端）。

    SSE 格式与 GET /api/stream/search 完全一致:
      - 节点输出 → data: {GraphNodeResponse JSON}
      - 完成 → event: complete + data: {complete:true}
      - 错误 → event: error + data: {error:true}

    适用场景: 内部调用、测试、非浏览器客户端。
    """
    return StreamingResponse(
        stream_workflow_execution(
            agent_id=query_request.agent_id,
            user_query=query_request.query,
            db=db,
            thread_id=query_request.workflow_id,
            human_feedback=query_request.human_feedback,
            human_feedback_content=query_request.human_feedback_content,
            rejected_plan=query_request.rejected_plan,
            nl2sql_only=query_request.nl2sql_only,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/stream/search")
async def stream_search_legacy(
    agentId: int = Query(..., description="Agent ID"),
    query: str = Query(..., min_length=1, description="用户问题"),
    threadId: str | None = Query(None, description="会话线程ID"),
    humanFeedback: bool = Query(False, description="是否启用人工反馈"),
    humanFeedbackContent: str | None = Query(None, description="人工反馈内容"),
    rejectedPlan: bool = Query(False, description="是否拒绝计划"),
    nl2sqlOnly: bool = Query(False, description="仅NL2SQL模式"),
    db: AsyncSession = Depends(get_db),
):
    """兼容 Java 路径: GET /api/stream/search — 对齐 Java GraphController"""
    return StreamingResponse(
        stream_workflow_execution(
            agent_id=agentId,
            user_query=query,
            db=db,
            thread_id=threadId,
            human_feedback=humanFeedback,
            human_feedback_content=humanFeedbackContent,
            rejected_plan=rejectedPlan,
            nl2sql_only=nl2sqlOnly,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
