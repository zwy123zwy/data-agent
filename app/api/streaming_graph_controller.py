"""
流式查询 API — 对齐 Java GraphController + GraphServiceImpl

【在系统中的地位】
  这是整个后端最重要的 API 文件。前端的所有数据分析请求都通过这里的
  SSE (Server-Sent Events) 端点进入，驱动 LangGraph 工作流执行。

【模块连接】
  上游 (前端 → 本文件):
    - 前端 Vue 应用 → GET /api/stream/search?agentId=&query=...
    - 前端 Vue 应用 → POST /api/query/stream (JSON body)

  本文件 → 中层:
    - compiled_workflow.astream()         → 异步遍历 LangGraph 工作流
    - AgentService.get_agent()            → 验证 Agent 是否存在
    - AgentDatasourceService.get_active_datasource() → 验证数据源

  本文件 → 下游 (前端):
    - SSE event stream → text/event-stream 格式
    - 事件类型: start, intent, knowledge, rewrite, schema, plan, sql, ...

  Java 对应:
    streaming_graph_controller.py ≈ GraphController.java + GraphServiceImpl.java (合一)

【SSE 事件流说明】
  前端通过 EventSource API 监听以下事件:

  event: start      → 开始处理
  event: intent     → 意图识别结果 (data_analysis / chitchat)
  event: knowledge  → 知识召回结果
  event: rewrite    → 查询改写结果
  event: schema     → Schema 召回完成
  event: table_relation → 表关系构建完成
  event: feasibility → 可行性评估结果
  event: plan       → 执行计划 (textType: JSON)
  event: plan_step  → 当前执行步骤
  event: sql        → 生成的 SQL (textType: SQL)
  event: semantic_check → 语义校验结果
  event: sql_result → SQL 执行结果 (textType: JSON)
  event: sql_error  → SQL 执行错误
  event: python_code → Python 代码 (textType: Python)
  event: python_execute → Python 执行结果
  event: python_analysis → Python 分析结论
  event: report     → 最终报告 (textType: Markdown)
  event: paused     → 暂停等待人工反馈
  event: done       → 处理完成
  event: error      → 错误信息

  每个事件包含 textType 字段 (SQL/JSON/HTML/Markdown/Python)，
  前端根据 textType 选择不同的渲染组件。
"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from langgraph.types import Command
from ..core.database import get_db
from ..schemas.query import QueryRequest
from ..workflows.graph import compiled_workflow
from ..workflows.state import WorkflowState
from ..services.agent_service import AgentService
from ..services.agent_datasource_service import AgentDatasourceService
from ..services.semantic_model_service import SemanticModelService
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["流式查询"])

# TextType 标记 — 对齐 Java TextType 枚举
TEXT_TYPE_SQL = "SQL"
TEXT_TYPE_JSON = "JSON"
TEXT_TYPE_HTML = "HTML"
TEXT_TYPE_MARKDOWN = "Markdown"
TEXT_TYPE_PYTHON = "Python"


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


async def _create_sse_event(event: str, data: dict, text_type: str = None) -> str:
    """创建 SSE 事件 — 对齐 Java SseEmitter / Flux"""
    payload = json.dumps(data, ensure_ascii=False)
    if text_type:
        return f"event: {event}\ndata: {payload}\ntextType: {text_type}\n\n"
    return f"event: {event}\ndata: {payload}\n\n"


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
    """流式执行工作流 — 对齐 Java GraphServiceImpl.streamQuery()

    Yields:
        SSE 格式的事件流，包含 Token 级流式输出
    """
    config = {"configurable": {"thread_id": thread_id}} if thread_id else None

    try:
        # 发送开始事件
        yield await _create_sse_event("start", {
            "message": "开始处理查询",
            "thread_id": thread_id,
        })

        # 检查 Agent
        agent = await AgentService.get_agent(db, agent_id)
        if not agent:
            yield await _create_sse_event("error", {"error": "Agent 不存在"})
            return

        # 检查数据源 — 获取激活的数据源及其 select_tables
        agent_ds_list = await AgentDatasourceService.list_agent_datasources(db, agent_id)
        active_agent_ds = next((item for item in agent_ds_list if item.is_active == 1), None)
        if not active_agent_ds:
            yield await _create_sse_event("error", {"error": "没有激活的数据源"})
            return
        datasource_id = active_agent_ds.datasource_id
        select_tables = active_agent_ds.select_tables

        # 构建语义模型 Prompt — 将业务术语映射注入到工作流
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
            # 使用 Command 恢复 interrupt
            graph_input = resume_cmd
        else:
            graph_input = initial_state

        # ===== 使用 astream_events 实现 Token 级流式 =====
        node_events = {
            "intent_recognition", "knowledge_recall", "query_rewrite",
            "schema_recall", "table_relation", "feasibility", "planner",
            "plan_executor", "sql_generate", "semantic_consistency",
            "sql_execute", "python_generate", "python_execute",
            "python_analyze", "report_generator", "human_feedback",
        }

        async for event in compiled_workflow.astream(graph_input, config, stream_mode="updates"):
            for node_name, node_output in event.items():
                if node_name not in node_events:
                    continue

                logger.info(f"[Stream] Node: {node_name}")

                # ===== 意图识别 =====
                if node_name == "intent_recognition":
                    intent = node_output.get("intent")
                    yield await _create_sse_event("intent", {"intent": intent})
                    if intent != "data_analysis":
                        yield await _create_sse_event("done", {"message": "闲聊模式，查询完成"})
                        return

                # ===== 知识召回 =====
                elif node_name == "knowledge_recall":
                    knowledge = node_output.get("recalled_knowledge", "")
                    if knowledge:
                        yield await _create_sse_event("knowledge", {
                            "knowledge": knowledge[:500],
                        })

                # ===== 查询改写 =====
                elif node_name == "query_rewrite":
                    rewritten = node_output.get("rewritten_query")
                    if rewritten:
                        yield await _create_sse_event("rewrite", {
                            "rewritten_query": rewritten,
                        })

                # ===== Schema 召回 =====
                elif node_name == "schema_recall":
                    yield await _create_sse_event("schema", {
                        "message": "Schema 召回完成",
                    })

                # ===== 表关系 =====
                elif node_name == "table_relation":
                    schema_info = node_output.get("schema_info")
                    if schema_info:
                        tables_count = len(schema_info.get("tables", []))
                        relations_count = len(schema_info.get("relations", []))
                        yield await _create_sse_event("table_relation", {
                            "tables": tables_count,
                            "relations": relations_count,
                            "message": f"发现 {tables_count} 个表, {relations_count} 个关系",
                        })

                # ===== 可行性评估 =====
                elif node_name == "feasibility":
                    result = node_output.get("feasibility_result", {})
                    yield await _create_sse_event("feasibility", {
                        "feasible": result.get("feasible", True),
                        "reason": result.get("reason", ""),
                    })

                # ===== Planner =====
                elif node_name == "planner":
                    plan = node_output.get("query_plan")
                    if plan:
                        plan_str = plan if isinstance(plan, str) else json.dumps(plan, ensure_ascii=False)
                        yield await _create_sse_event("plan", {
                            "plan": plan_str,
                        }, TEXT_TYPE_JSON)

                # ===== PlanExecutor 调度 =====
                elif node_name == "plan_executor":
                    next_node = node_output.get("plan_next_node", "")
                    current = node_output.get("plan_current_step", 1)
                    yield await _create_sse_event("plan_step", {
                        "next_node": next_node,
                        "current_step": current,
                    })

                # ===== SQL 生成 =====
                elif node_name == "sql_generate":
                    sql = node_output.get("generated_sql")
                    if sql:
                        yield await _create_sse_event("sql", {
                            "sql": sql,
                        }, TEXT_TYPE_SQL)

                # ===== 语义一致性校验 =====
                elif node_name == "semantic_consistency":
                    passed = node_output.get("semantic_consistency_result", True)
                    yield await _create_sse_event("semantic_check", {
                        "passed": passed,
                    })

                # ===== SQL 执行 =====
                elif node_name == "sql_execute":
                    error = node_output.get("sql_error")
                    result = node_output.get("sql_result")
                    if error:
                        yield await _create_sse_event("sql_error", {"error": error})
                    elif result is not None:
                        yield await _create_sse_event("sql_result", {
                            "count": len(result),
                            "columns": list(result[0].keys()) if result else [],
                            "sample": result[:5] if result else [],
                        }, TEXT_TYPE_JSON)

                # ===== Python 代码生成 =====
                elif node_name == "python_generate":
                    code = node_output.get("python_code")
                    if code:
                        yield await _create_sse_event("python_code", {
                            "code": code,
                        }, TEXT_TYPE_PYTHON)

                # ===== Python 执行 =====
                elif node_name == "python_execute":
                    is_success = node_output.get("python_is_success", False)
                    charts = node_output.get("python_charts", [])
                    yield await _create_sse_event("python_execute", {
                        "success": is_success,
                        "charts_count": len(charts),
                    })

                # ===== Python 分析 =====
                elif node_name == "python_analyze":
                    analysis = node_output.get("python_analysis", "")
                    if analysis:
                        yield await _create_sse_event("python_analysis", {
                            "analysis": analysis[:500],
                        })

                # ===== 报告生成 =====
                elif node_name == "report_generator":
                    report = node_output.get("report", "")
                    html_report = node_output.get("html_report", "")
                    display_style = node_output.get("display_style")
                    yield await _create_sse_event("report", {
                        "report": report,
                        "html_report": html_report,
                        "display_style": display_style,
                    }, TEXT_TYPE_MARKDOWN)

                # ===== Human Feedback (interrupt 会在此暂停) =====
                elif node_name == "human_feedback":
                    feedback_data = node_output
                    if isinstance(feedback_data, dict) and feedback_data.get("type") == "human_feedback":
                        yield await _create_sse_event("paused", {
                            "message": feedback_data.get("message", "等待人工反馈"),
                            "plan_description": feedback_data.get("plan_description", ""),
                            "current_step": feedback_data.get("current_step", 1),
                        })
                        # LangGraph interrupt 在此触发，流自然暂停
                        return

        # 发送完成事件
        yield await _create_sse_event("done", {"message": "查询完成"})

    except Exception as e:
        logger.error(f"[Stream] Error: {e}")
        yield await _create_sse_event("error", {"error": str(e)})


# ========== API 端点 ==========

@router.post("/query/stream")
async def stream_query(
    query_request: QueryRequest,
    db: AsyncSession = Depends(get_db),
):
    """流式查询接口（SSE）— 对齐 Java GraphController.streamSearch()

    事件类型:
    - start: 开始处理
    - intent: 意图识别结果
    - knowledge: 知识召回结果
    - rewrite: 查询改写结果
    - schema: Schema 召回完成
    - table_relation: 表关系构建完成
    - feasibility: 可行性评估结果
    - plan: 执行计划（JSON）
    - plan_step: 计划执行步骤
    - sql: SQL 生成（textType: SQL）
    - semantic_check: 语义校验结果
    - sql_result: SQL 执行结果（textType: JSON）
    - sql_error: SQL 执行错误
    - python_code: Python 代码生成（textType: Python）
    - python_execute: Python 执行结果
    - python_analysis: Python 分析结论
    - report: 最终报告（textType: Markdown）
    - paused: 暂停等待人工反馈
    - done: 处理完成
    - error: 错误信息
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
