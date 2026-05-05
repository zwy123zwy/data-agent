"""BusinessKnowledge API — 对齐 Java BusinessKnowledgeController (8 个端点)"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from ..core.database import get_db
from ..schemas.business_knowledge import (
    BusinessKnowledgeCreateRequest,
    BusinessKnowledgeUpdateRequest,
    BusinessKnowledgeResponse,
)
from ..services.business_knowledge_service import BusinessKnowledgeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/business-knowledge", tags=["业务知识"])


@router.get("", summary="列出业务知识")
async def list_knowledge(
    agentId: str = Query(..., alias="agentId", description="Agent ID"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    db: AsyncSession = Depends(get_db),
):
    """列出 Agent 的业务知识 — 对齐 Java GET /api/business-knowledge?agentId=&keyword="""
    result = await BusinessKnowledgeService.list_by_agent(
        db, int(agentId), keyword
    )
    return {
        "success": True,
        "message": "success list businessKnowledge",
        "data": [r.model_dump(by_alias=True) for r in result],
    }


@router.get("/{id}", summary="获取业务知识详情")
async def get_knowledge(id: int, db: AsyncSession = Depends(get_db)):
    """获取业务知识详情 — 对齐 Java GET /api/business-knowledge/{id}"""
    vo = await BusinessKnowledgeService.get_by_id(db, id)
    if not vo:
        return {"success": False, "message": "businessKnowledge not found"}
    return {"success": True, "message": "success get businessKnowledge", "data": vo.model_dump(by_alias=True)}


@router.post("", summary="创建业务知识")
async def create_knowledge(
    dto: BusinessKnowledgeCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """创建业务知识 — 对齐 Java POST /api/business-knowledge"""
    vo = await BusinessKnowledgeService.create(db, dto)
    return {"success": True, "message": "success create businessKnowledge", "data": vo.model_dump(by_alias=True)}


@router.put("/{id}", summary="更新业务知识")
async def update_knowledge(
    id: int,
    dto: BusinessKnowledgeUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新业务知识 — 对齐 Java PUT /api/business-knowledge/{id}"""
    vo = await BusinessKnowledgeService.update(db, id, dto)
    if not vo:
        return {"success": False, "message": "businessKnowledge not found"}
    return {"success": True, "message": "success update businessKnowledge", "data": vo.model_dump(by_alias=True)}


@router.delete("/{id}", summary="删除业务知识")
async def delete_knowledge(id: int, db: AsyncSession = Depends(get_db)):
    """删除业务知识 — 对齐 Java DELETE /api/business-knowledge/{id}"""
    ok = await BusinessKnowledgeService.delete(db, id)
    if not ok:
        return {"success": False, "message": "businessKnowledge not found"}
    return {"success": True, "message": "success delete businessKnowledge"}


@router.post("/recall/{id}", summary="切换召回状态")
async def recall_knowledge(
    id: int,
    isRecall: bool = Query(..., alias="isRecall", description="是否召回: true=是, false=否"),
    db: AsyncSession = Depends(get_db),
):
    """切换召回状态 — 对齐 Java POST /api/business-knowledge/recall/{id}?isRecall= (Boolean)"""
    ok = await BusinessKnowledgeService.set_recall(db, id, 1 if isRecall else 0)
    if not ok:
        return {"success": False, "message": "businessKnowledge not found"}
    return {"success": True, "message": "success update recall businessKnowledge"}


@router.post("/refresh-vector-store", summary="刷新向量存储")
async def refresh_vector_store(
    agentId: str = Query(..., alias="agentId", description="Agent ID"),
    db: AsyncSession = Depends(get_db),
):
    """刷新向量存储 — 对齐 Java POST /api/business-knowledge/refresh-vector-store?agentId="""
    await BusinessKnowledgeService.refresh_vector_store(db, int(agentId))
    return {"success": True, "message": "success refresh vector store"}


@router.post("/retry-embedding/{id}", summary="重试向量化")
async def retry_embedding(id: int, db: AsyncSession = Depends(get_db)):
    """重试向量化 — 对齐 Java POST /api/business-knowledge/retry-embedding/{id}"""
    ok = await BusinessKnowledgeService.retry_embedding(db, id)
    if not ok:
        return {"success": False, "message": "businessKnowledge not found"}
    return {"success": True, "message": "success retry embedding"}
