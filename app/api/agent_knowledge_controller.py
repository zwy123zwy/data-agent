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
    KnowledgeCreate,
    KnowledgeResponse,
    AgentKnowledgeQueryDTO,
    UpdateKnowledgeDTO,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent-knowledge", tags=["AgentKnowledge"])


def _to_vo(knowledge) -> dict:
    """构建 AgentKnowledgeVO 响应 — 对齐 Java AgentKnowledgeVO"""
    return {
        "id": knowledge.id,
        "agentId": knowledge.agent_id,
        "title": knowledge.title,
        "content": knowledge.content,
        "type": knowledge.type,
        "question": getattr(knowledge, "question", None),
        "isRecall": getattr(knowledge, "is_recall", 1),
        "embeddingId": getattr(knowledge, "embedding_id", None),
        "embeddingStatus": getattr(knowledge, "embedding_status", "PENDING"),
        "errorMsg": getattr(knowledge, "error_msg", None),
        "sourceFilename": getattr(knowledge, "source_filename", None),
        "filePath": getattr(knowledge, "file_path", None),
        "fileSize": getattr(knowledge, "file_size", None),
        "fileType": getattr(knowledge, "file_type", None),
        "splitterType": getattr(knowledge, "splitter_type", "token"),
        "enabled": getattr(knowledge, "enabled", True),
        "isDeleted": getattr(knowledge, "is_deleted", 0),
        "isResourceCleaned": getattr(knowledge, "is_resource_cleaned", 0),
        "createTime": knowledge.created_at.isoformat() if knowledge.created_at else None,
        "updateTime": knowledge.updated_at.isoformat() if knowledge.updated_at else None,
    }


@router.get("/{id}", summary="获取知识详情")
async def get_knowledge(id: int, db: AsyncSession = Depends(get_db)):
    """获取知识详情 — 对齐 Java GET /api/agent-knowledge/{id}"""
    try:
        knowledge = await KnowledgeService.get_knowledge(db, id)
        if not knowledge:
            return {"success": False, "message": "知识不存在"}
        return {"success": True, "message": "查询成功", "data": _to_vo(knowledge)}
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

        # 处理文件上传
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

            # 验证并存储文件
            error = FileStorageService.validate_image(file_type_val, file_size)
            if error:
                # 不是图片，保存为通用文件
                pass

            try:
                file_path = FileStorageService.store_file(file_bytes, source_filename, "knowledge")
                file_type = file_type_val
            except Exception as e:
                logger.error("文件存储失败: %s", e)

            # 尝试读取文本内容（用于向量化）
            try:
                file_content_text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                file_content_text = f"[二进制文件: {source_filename}]"

        # 确定最终内容
        final_content = content or ""
        if file_content_text and not final_content:
            final_content = file_content_text

        knowledge_data = KnowledgeCreate(
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
        return {"success": True, "message": "创建知识成功，后台向量存储开始更新，请耐心等待...", "data": _to_vo(knowledge)}
    except Exception as e:
        logger.error("创建知识失败: %s", e)
        return {"success": False, "message": f"创建知识失败：{e}"}


@router.put("/{id}", summary="更新知识")
async def update_knowledge(
    id: int,
    dto: UpdateKnowledgeDTO,
    db: AsyncSession = Depends(get_db),
):
    """更新知识 — 对齐 Java PUT /api/agent-knowledge/{id}"""
    # 检查知识是否存在
    existing = await KnowledgeService.get_knowledge(db, id)
    if not existing:
        return {"success": False, "message": "知识不存在"}

    knowledge = await KnowledgeService.update_knowledge(db, id, dto)
    if not knowledge:
        return {"success": False, "message": "更新失败"}
    return {"success": True, "message": "更新成功", "data": _to_vo(knowledge)}


@router.put("/recall/{id}", summary="切换召回状态")
async def update_recall_status(
    id: int,
    isRecall: bool = Query(..., description="是否召回"),
    db: AsyncSession = Depends(get_db),
):
    """切换召回状态 — 对齐 Java PUT /api/agent-knowledge/recall/{id}"""
    knowledge = await KnowledgeService.update_recall_status(db, id, isRecall)
    if not knowledge:
        return {"success": False, "message": "知识不存在"}
    return {"success": True, "message": "更新成功", "data": _to_vo(knowledge)}


@router.delete("/{id}", summary="删除知识")
async def delete_knowledge(id: int, db: AsyncSession = Depends(get_db)):
    """删除知识 — 对齐 Java DELETE /api/agent-knowledge/{id}"""
    ok = await KnowledgeService.delete_knowledge(db, id)
    if ok:
        return {"success": True, "message": "删除操作已接收，等待后台删除相关资源..."}
    return {"success": False, "message": "删除失败"}


@router.post("/query/page", summary="分页查询知识")
async def query_page(dto: AgentKnowledgeQueryDTO, db: AsyncSession = Depends(get_db)):
    """分页查询 — 对齐 Java POST /api/agent-knowledge/query/page"""
    try:
        items, total, page_num, page_size, total_pages = await KnowledgeService.query_page(db, dto)
        return {
            "success": True,
            "data": [_to_vo(item) for item in items],
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
    return {"success": True, "message": "重试向量化操作成功，如果是文件解析需要花费点时间，请耐心等待...", "data": _to_vo(knowledge)}
