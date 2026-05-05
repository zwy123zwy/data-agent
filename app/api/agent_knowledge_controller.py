"""
AgentKnowledge API — 对齐 Java AgentKnowledgeController (7 个端点)
路由前缀: /api/agent-knowledge
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from ..core.database import get_db
from ..services.knowledge_service import KnowledgeService
from ..services.agent_service import AgentService
from ..services.file_storage_service import FileStorageService
from ..schemas.knowledge import (
    KnowledgeCreateRequest,
    KnowledgeResponse,
    KnowledgeQueryRequest,
    KnowledgeUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent-knowledge", tags=["AgentKnowledge"])


@router.get("/{id}", summary="获取知识详情")
async def get_knowledge(id: int, db: AsyncSession = Depends(get_db)):
    """获取知识详情 — 对齐 Java GET /api/agent-knowledge/{id}"""
    try:
        knowledge = await KnowledgeService.get_knowledge(db, id)
        if not knowledge:
            return {"success": False, "message": "知识不存在"}
        return {"success": True, "message": "查询成功", "data": KnowledgeResponse.model_validate(knowledge).model_dump(by_alias=True)}
    except Exception as e:
        logger.error("查询知识详情失败：%s", e)
        return {"success": False, "message": f"查询知识详情失败：{e}"}


@router.post("/create", summary="创建知识（支持文件上传）")
async def create_knowledge(
    agentId: str = Form(...),
    title: str = Form(...),
    type: str = Form(...),
    question: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    splitterType: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """创建知识 — 对齐 Java POST /api/agent-knowledge/create (multipart/form-data)"""
    try:
        agent = await AgentService.get_agent(db, int(agentId))
        if not agent:
            return {"success": False, "message": "Agent 不存在"}

        source_filename = None
        file_path = None
        file_size = None
        file_type = None
        file_content_text = None

        if file:
            file_bytes = await file.read()
            file_size = len(file_bytes)
            source_filename = file.filename or "unknown"
            file_type_val = file.content_type or "application/octet-stream"

            error = FileStorageService.validate_image(file_type_val, file_size)
            if error:
                pass

            try:
                file_path = FileStorageService.store_file(file_bytes, source_filename, "knowledge")
                file_type = file_type_val
            except Exception as e:
                logger.error("文件存储失败: %s", e)

            try:
                file_content_text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                file_content_text = f"[二进制文件: {source_filename}]"

        final_content = content or ""
        if file_content_text and not final_content:
            final_content = file_content_text

        knowledge_data = KnowledgeCreateRequest(
            title=title,
            content=final_content,
            type=type,
            question=question,
            source_filename=source_filename,
            file_path=file_path,
            file_size=file_size,
            file_type=file_type,
            splitter_type=splitterType or "token",
        )

        knowledge = await KnowledgeService.create_knowledge(db, int(agentId), knowledge_data)
        return {"success": True, "message": "创建知识成功，后台向量存储开始更新，请耐心等待...", "data": KnowledgeResponse.model_validate(knowledge).model_dump(by_alias=True)}
    except Exception as e:
        logger.error("创建知识失败: %s", e)
        return {"success": False, "message": f"创建知识失败：{e}"}


@router.put("/{id}", summary="更新知识")
async def update_knowledge(
    id: int,
    dto: KnowledgeUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新知识 — 对齐 Java PUT /api/agent-knowledge/{id}"""
    existing = await KnowledgeService.get_knowledge(db, id)
    if not existing:
        return {"success": False, "message": "知识不存在"}

    knowledge = await KnowledgeService.update_knowledge(db, id, dto)
    if not knowledge:
        return {"success": False, "message": "更新失败"}
    return {"success": True, "message": "更新成功", "data": KnowledgeResponse.model_validate(knowledge).model_dump(by_alias=True)}


@router.put("/recall/{id}", summary="切换召回状态")
async def update_recall_status(
    id: int,
    isRecall: int = Query(..., description="是否召回: 1=是, 0=否"),
    db: AsyncSession = Depends(get_db),
):
    """切换召回状态 — 对齐 Java PUT /api/agent-knowledge/recall/{id}"""
    knowledge = await KnowledgeService.update_recall_status(db, id, isRecall)
    if not knowledge:
        return {"success": False, "message": "知识不存在"}
    return {"success": True, "message": "更新成功", "data": KnowledgeResponse.model_validate(knowledge).model_dump(by_alias=True)}


@router.delete("/{id}", summary="删除知识")
async def delete_knowledge(id: int, db: AsyncSession = Depends(get_db)):
    """删除知识 — 对齐 Java DELETE /api/agent-knowledge/{id}"""
    ok = await KnowledgeService.delete_knowledge(db, id)
    if ok:
        return {"success": True, "message": "删除操作已接收，等待后台删除相关资源..."}
    return {"success": False, "message": "删除失败"}


@router.post("/query/page", summary="分页查询知识")
async def query_page(dto: KnowledgeQueryRequest, db: AsyncSession = Depends(get_db)):
    """分页查询 — 对齐 Java POST /api/agent-knowledge/query/page"""
    try:
        items, total, page_num, page_size, total_pages = await KnowledgeService.query_page(db, dto)
        return {
            "success": True,
            "data": [KnowledgeResponse.model_validate(item).model_dump(by_alias=True) for item in items],
            "total": total,
            "pageNum": page_num,
            "pageSize": page_size,
            "totalPages": total_pages,
        }
    except Exception as e:
        logger.error("分页查询知识列表失败：%s", e)
        return {"success": False, "message": f"分页查询失败：{e}", "data": [], "total": 0}


@router.post("/retry-embedding/{id}", summary="重试向量化")
async def retry_embedding(id: int, db: AsyncSession = Depends(get_db)):
    """重试向量化 — 对齐 Java POST /api/agent-knowledge/retry-embedding/{id}"""
    knowledge = await KnowledgeService.retry_embedding(db, id)
    if not knowledge:
        return {"success": False, "message": "知识不存在"}
    return {"success": True, "message": "重试向量化操作成功，如果是文件解析需要花费点时间，请耐心等待...", "data": KnowledgeResponse.model_validate(knowledge).model_dump(by_alias=True)}
