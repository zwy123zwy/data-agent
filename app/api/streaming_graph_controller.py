"""
流式查询 API
使用 SSE (Server-Sent Events) 实现流式输出
"""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..schemas.query import QueryRequest
from ..workflows.graph import compiled_workflow
from ..workflows.state import WorkflowState
from ..services.agent_service import AgentService
from ..services.agent_datasource_service import AgentDatasourceService
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["流式查询"])


async def stream_workflow_execution(
    agent_id: int,
    user_query: str,
    db: AsyncSession
):
    """
    流式执行工作流

    Yields:
        SSE 格式的事件流
    """
    try:
        # 发送开始事件
        yield f"event: start\ndata: {json.dumps({'message': '开始处理查询'})}\n\n"

        # 检查 Agent 是否存在
        agent = await AgentService.get_agent(db, agent_id)
        if not agent:
            yield f"event: error\ndata: {json.dumps({'error': 'Agent 不存在'})}\n\n"
            return

        # 检查是否有激活的数据源
        active_datasource = await AgentDatasourceService.get_active_datasource(db, agent_id)
        if not active_datasource:
            yield f"event: error\ndata: {json.dumps({'error': '没有激活的数据源'})}\n\n"
            return

        # 构建初始状态
        initial_state: WorkflowState = {
            "agent_id": agent_id,
            "user_query": user_query,
            "sql_retry_count": 0
        }

        # 执行工作流（使用 astream 流式执行）
        async for event in compiled_workflow.astream(initial_state):
            # event 是一个字典，key 是节点名，value 是节点输出
            for node_name, node_output in event.items():
                logger.info(f"[Stream] Node: {node_name}")

                # 根据节点类型发送不同的事件
                if node_name == "intent_recognition":
                    intent = node_output.get("intent")
                    yield f"event: intent\ndata: {json.dumps({'intent': intent})}\n\n"

                elif node_name == "knowledge_recall":
                    knowledge = node_output.get("recalled_knowledge", "")
                    if knowledge:
                        yield f"event: knowledge\ndata: {json.dumps({'knowledge': knowledge})}\n\n"

                elif node_name == "query_rewrite":
                    rewritten = node_output.get("rewritten_query")
                    if rewritten:
                        yield f"event: rewrite\ndata: {json.dumps({'rewritten_query': rewritten})}\n\n"

                elif node_name == "schema_recall":
                    yield f"event: schema\ndata: {json.dumps({'message': 'Schema 召回完成'})}\n\n"

                elif node_name == "sql_generate":
                    sql = node_output.get("generated_sql")
                    if sql:
                        yield f"event: sql\ndata: {json.dumps({'sql': sql})}\n\n"

                elif node_name == "sql_execute":
                    result = node_output.get("sql_result")
                    error = node_output.get("sql_error")
                    if error:
                        yield f"event: sql_error\ndata: {json.dumps({'error': error})}\n\n"
                    elif result:
                        yield f"event: sql_result\ndata: {json.dumps({'result': result, 'count': len(result)})}\n\n"

                elif node_name == "simple_report":
                    report = node_output.get("report")
                    if report:
                        yield f"event: report\ndata: {json.dumps({'report': report})}\n\n"

        # 发送完成事件
        yield f"event: done\ndata: {json.dumps({'message': '查询完成'})}\n\n"

    except Exception as e:
        logger.error(f"[Stream] Error: {e}")
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"


@router.post("/query/stream")
async def stream_query(
    query_request: QueryRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    流式查询接口（SSE）

    返回 Server-Sent Events 流，实时推送工作流执行进度

    事件类型：
    - start: 开始处理
    - intent: 意图识别结果
    - knowledge: 知识召回结果
    - rewrite: 查询改写结果
    - schema: Schema 召回完成
    - sql: SQL 生成结果
    - sql_result: SQL 执行结果
    - sql_error: SQL 执行错误
    - report: 最终报告
    - done: 处理完成
    - error: 错误信息
    """
    return StreamingResponse(
        stream_workflow_execution(
            agent_id=query_request.agent_id,
            user_query=query_request.query,
            db=db
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用 Nginx 缓冲
        }
    )
