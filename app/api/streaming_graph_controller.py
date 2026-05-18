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
from ..services.multi_turn import get_multi_turn_manager
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
    "chitchat_node": "ChitchatNode",
}

# ★ 对用户可见的节点（其余为内部管线节点——RAG、Schema 回收等）
# LangGraph 中所有节点都会产生 state update，但只有这些节点向前端推送 SSE 消息
USER_VISIBLE_NODES = frozenset({
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
    "chitchat_node",
})

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

# 节点对用户的可见文本由各节点的 format_sse() 方法自描述输出，
# Controller 不再维护硬编码的文案映射。详见 app/workflows/node_base.py SSEPayload


def _build_graph_response(
    agent_id: int,
    thread_id: str,
    node_name: str,
    text: str,
    text_type: str = "TEXT",
    error: bool = False,
    complete: bool = False,
    # V3.0: Agent/Tool 归属 — Phase 2 后端主动发送, 前端直接读取
    agent_name: str | None = None,
    tool_name: str | None = None,
    tool_status: str | None = None,
    tool_summary: str | None = None,
) -> dict:
    """构建 GraphNodeResponse 响应

    V3.0 新增字段仅非 None 时序列化, 向后兼容 Phase 1 前端.
    """
    # [旧代码] 仅包含 V2.0 7 个固定字段
    # return {
    #     "agentId": str(agent_id),
    #     "threadId": thread_id or "",
    #     "nodeName": node_name,
    #     "textType": text_type,
    #     "text": text or "",
    #     "error": error,
    #     "complete": complete,
    # }
    response = {
        "agentId": str(agent_id),
        "threadId": thread_id or "",
        "nodeName": node_name,
        "textType": text_type,
        "text": text or "",
        "error": error,
        "complete": complete,
    }
    # V3.0 可选字段: 仅非 None 时序列化, 避免向前端发送 null 值
    if agent_name is not None:
        response["agentName"] = agent_name
    if tool_name is not None:
        response["toolName"] = tool_name
    if tool_status is not None:
        response["toolStatus"] = tool_status
    if tool_summary is not None:
        response["toolSummary"] = tool_summary
    return response


def _format_sse_data(data: dict) -> str:
    """纯 data: 格式 (无 event: 前缀) — 前端 EventSource.onmessage 接收"""
    payload = json.dumps(data, ensure_ascii=False)
    return f"data: {payload}\n\n"


def _format_sse_event(event: str, data: dict) -> str:
    """命名 event: 格式 — 前端 addEventListener(event, ...) 接收"""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _log_sse_response(event: str, data: dict) -> None:
    """Print a compact SSE response summary to the terminal.

    Streaming responses are produced inside the async generator, so uvicorn's
    normal access log only shows the initial 200 response. This log records the
    actual SSE messages without dumping large report bodies into the terminal.
    """
    text = str(data.get("text") or "")
    preview = text.replace("\r", " ").replace("\n", " ")[:200]
    suffix = "..." if len(text) > 200 else ""
    logger.info(
        "[Stream] SSE "
        f"event={event}, nodeName={data.get('nodeName')}, textType={data.get('textType')}, "
        f"chars={len(text)}, error={data.get('error')}, complete={data.get('complete')}, "
        f"text={preview}{suffix}"
    )


def _format_logged_sse_data(data: dict) -> str:
    _log_sse_response("message", data)
    return _format_sse_data(data)


def _format_logged_sse_event(event: str, data: dict) -> str:
    _log_sse_response(event, data)
    return _format_sse_event(event, data)


def _build_initial_state(
    agent_id: int,
    user_query: str,
    nl2sql_only: bool = False,
    human_review: bool = False,
    multi_turn_context: str = "",
    semantic_model_prompt: str = "",
) -> WorkflowState:
    """构建初始 WorkflowState """
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
        "intent_retry_count": 0,
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

    logger.info(f"[Stream] Start, agentId={agent_id}, query={user_query}, threadId={thread_id}")
    if not thread_id:
        thread_id = str(uuid.uuid4())
        
    config = {"configurable": {"thread_id": thread_id}}

    try:
        # =====================================================================
        # 资源准备：按路径分流，只在需要时获取对应资源
        #   - HumanFeedback resume → 跳过所有 DB 查询，直接从 checkpoint 恢复
        #   - 新请求             → Agent → Datasource → SemanticModel 按依赖顺序加载
        # =====================================================================

        if thread_id and human_feedback_content:
            # ===== 恢复路径：LangGraph 从 checkpoint 恢复状态，不需要任何外部资源 =====
            action = "reject" if rejected_plan else "approve"
            graph_input = Command(resume={"action": action, "reason": human_feedback_content})
            select_tables = []
        else:
            # ===== 新请求路径：按依赖顺序获取资源 =====

            # 1. 校验 Agent 存在性 — 提前失败，避免后续白查数据源
            agent = await AgentService.get_agent(db, agent_id)
            if not agent:
                yield _format_logged_sse_event("error", _build_graph_response(
                    agent_id, thread_id, "", "Agent 不存在", TEXT_TYPE_TEXT, error=True
                ))
                await MetricsAggregationService.record_execution(
                    db, thread_id=thread_id, agent_id=agent_id, status="error",
                    total_duration_ms=0, total_nodes=0, succeeded_nodes=0, failed_nodes=1,
                )
                return

            # 2. 获取激活的数据源及其 select_tables（只查一次）
            agent_ds_list = await AgentDatasourceService.list_agent_datasources(db, agent_id)
            active_agent_ds = next((item for item in agent_ds_list if item.is_active == 1), None)

            # 3. 按条件构建语义模型 Prompt
            datasource_id = None
            select_tables = []
            semantic_model_prompt = ""
            if active_agent_ds is None:
                # 无激活数据源 → 不在此报错，让 workflow 正常启动
                # intent_recognition 先判断意图：闲聊直接回，数据分析走到 schema_recall 时
                # 由 schema_recall 告知用户"请先配置数据源"
                logger.info("[Stream] No active datasource — workflow will handle gracefully")
            else:
                datasource_id = active_agent_ds.datasource_id
                select_tables = active_agent_ds.select_tables
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
                        logger.info(
                            f"[Stream] Built semantic model prompt for "
                            f"{len(select_tables)} tables ({len(semantic_model_prompt)} chars)"
                        )

            # 4. 获取多轮对话上下文
            multi_turn_context = get_multi_turn_manager().get_context_for_prompt(thread_id)
            if multi_turn_context:
                logger.info(f"[Stream] Multi-turn context loaded: {len(multi_turn_context)} chars")

            # 5. 构建初始状态（含空语义模型的降级状态）
            graph_input = _build_initial_state(
                agent_id=agent_id,
                user_query=user_query,
                nl2sql_only=nl2sql_only,
                human_review=human_feedback,
                multi_turn_context=multi_turn_context,
                semantic_model_prompt=semantic_model_prompt,
            )

        # ===== astream 事件循环 =====
        # stream_mode="updates": 每个节点完成后产生 {node_name: state_update}
        # Controller 将其映射为 GraphNodeResponse SSE 消息投递给前端
        # ★ 只在 USER_VISIBLE_NODES 中的节点才推送 — 内部管线节点（RAG 回收等）不暴露

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
            """记录本次执行指标到数据库 (非致命)

            status: 流程终止状态 — success / error / paused / cancelled
            """
            # 同步 hf_final_status 到指标，确保 DB 中可区分暂停/完成
            if metrics_state.get("hf_final_status") is None:
                metrics_state["hf_final_status"] = status
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
                # LangGraph interrupt() 的封装格式：
                #   {"__interrupt__": (Interrupt(value),)} — tuple 包装
                #   {"__interrupt__": Interrupt(value)}   — 直接对象
                # 统一提取内部 value
                raw = event["__interrupt__"]
                if isinstance(raw, (list, tuple)) and len(raw) > 0:
                    raw = raw[0]
                interrupt_value = getattr(raw, "value", raw)

                # 根据 interrupt type 确定来源节点
                interrupt_type = (
                    interrupt_value.get("type", "") if isinstance(interrupt_value, dict) else ""
                )
                if interrupt_type == "intent_confirm":
                    source_node = "intent_recognition"
                    logger.info(f"[Stream] Intent confirm interrupt: {interrupt_value.get('message', '')}")
                else:
                    source_node = "human_feedback"
                    logger.info(f"[Stream] Human feedback interrupt: {interrupt_value}")

                # Send node output as SSE data
                if isinstance(interrupt_value, dict):
                    java_name = NODE_NAME_MAP.get(source_node, source_node)
                    text = json.dumps(interrupt_value, ensure_ascii=False)
                    yield _format_logged_sse_data(_build_graph_response(
                        agent_id, thread_id, java_name, text, TEXT_TYPE_JSON
                    ))

                # Send paused event so frontend knows this is a normal pause, not an error
                yield _format_logged_sse_event("paused", _build_graph_response(
                    agent_id, thread_id, NODE_NAME_MAP.get(source_node, ""), "", TEXT_TYPE_TEXT
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

                if node_name not in USER_VISIBLE_NODES:
                    m.finish("success")
                    m.log()
                    continue
                java_name = NODE_NAME_MAP.get(node_name, node_name)

                # ===== 读取节点的自描述 SSE 输出 =====
                # 每个 WorkflowNode.__call__() 调用 format_sse() 并将结果注入为
                # node_output["sse_output"] = {"text": ..., "textType": ...}
                # Controller 只读取此字段，不再窥探节点内部字段
                sse = node_output.get("sse_output")

                # Phase 7: 应用节点报告的指标增量
                # 每个节点在 SSEPayload.metrics_delta 中声明自己贡献的指标
                metrics_delta = node_output.get("_metrics_delta", {})
                for key, value in metrics_delta.items():
                    if value is not None:
                        metrics_state[key] = value

                # ★ 意图识别：非 data_analysis 意图 → 提前结束流程
                # TODO: intent 字段应通过 _metrics_delta 传递，避免 Controller 窥探节点内部
                if node_name == "intent_recognition":
                    intent = node_output.get("intent", "")
                    if intent != "data_analysis":
                        if sse:
                            # [旧代码] 只传 V2.0 字段
                            # yield _format_logged_sse_data(_build_graph_response(
                            #     agent_id, thread_id, java_name, sse["text"], sse["textType"]
                            # ))
                            yield _format_logged_sse_data(_build_graph_response(
                                agent_id, thread_id, java_name,
                                text=sse["text"],
                                text_type=sse["textType"],
                                agent_name=sse.get("agentName"),
                                tool_name=sse.get("toolName"),
                                tool_status=sse.get("toolStatus"),
                                tool_summary=sse.get("toolSummary"),
                            ))
                        m.finish("success")
                        m.log()
                        yield _format_logged_sse_event("complete", _build_graph_response(
                            agent_id, thread_id, "", "", TEXT_TYPE_TEXT, complete=True
                        ))
                        tracker.log_summary()
                        await _record_metrics("success")
                        get_multi_turn_manager().add_turn(thread_id, user_query, "[闲聊]")
                        return

                # ===== 通用 SSE 输出 — Controller 不窥探节点内部字段 =====
                # V3.0: 透传各节点 format_sse() 声明的 agentName/toolName/toolStatus/toolSummary
                # Phase 1 前端忽略这些字段, Phase 2 前端直接读取不再需要 NODE_TO_EXECUTION 硬编码
                if sse:
                    # [旧代码] 只传 V2.0 字段
                    # yield _format_logged_sse_data(_build_graph_response(
                    #     agent_id, thread_id, java_name, sse["text"], sse["textType"]
                    # ))
                    yield _format_logged_sse_data(_build_graph_response(
                        agent_id, thread_id, java_name,
                        text=sse["text"],
                        text_type=sse["textType"],
                        agent_name=sse.get("agentName"),
                        tool_name=sse.get("toolName"),
                        tool_status=sse.get("toolStatus"),
                        tool_summary=sse.get("toolSummary"),
                    ))

                # ===== 节点指标状态判定 (NodeMetricsTracker) =====
                # 大部分节点总是成功；少数节点可能失败
                # TODO: 后续迁移 — 错误信号应由节点通过 _metrics_delta 声明，
                #       而非 Controller 硬编码 node_name 窥探字段
                status = "success"
                if node_name == "sql_execute" and node_output.get("sql_error"):
                    status = "error"
                    m.error_type = "SqlExecuteError"
                    m.error_message = str(node_output.get("sql_error", ""))[:200]
                elif node_name == "semantic_consistency" and not node_output.get("semantic_consistency_result", False):
                    status = "error"
                    m.error_type = "SemanticConsistencyError"
                    m.error_message = "语义一致性校验未通过"
                elif node_name == "python_execute" and not node_output.get("python_is_success", False):
                    status = "error"
                    m.error_type = "PythonExecuteError"
                    m.error_message = str(node_output.get("python_error", ""))[:200]
                m.finish(status)
                m.log()

        # 发送完成事件 — 对齐 Java handleStreamComplete
        logger.info(f"[Stream] Complete, threadId={thread_id}")
        tracker.log_summary()
        await _record_metrics("success")
        yield _format_logged_sse_event("complete", _build_graph_response(
            agent_id, thread_id, "", "", TEXT_TYPE_TEXT, complete=True
        ))
        # 本轮对话写入多轮上下文，下次请求可获取历史
        get_multi_turn_manager().add_turn(thread_id, user_query, "[分析完成]")

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
        yield _format_logged_sse_event("error", _build_graph_response(
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
    logger.info(
        "[Stream] Start POST, "
        f"agentId={query_request.agent_id}, query={query_request.query}, "
        f"threadId={query_request.workflow_id}"
    )
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
    logger.info(f"[Stream] Start, agentId={agentId}, query={query}, threadId={threadId}")
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
