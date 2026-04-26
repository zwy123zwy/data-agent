"""
Knowledge API
知识库管理接口
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from ..core.database import get_db
from ..services.knowledge_service import KnowledgeService
from ..services.agent_service import AgentService
from ..schemas.knowledge import (
    KnowledgeCreate,
    KnowledgeUpdate,
    KnowledgeResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResult
)

router = APIRouter(prefix="/api/agents/{agent_id}/knowledge", tags=["Knowledge"])


@router.post("", response_model=KnowledgeResponse, status_code=201)
async def create_knowledge(
    agent_id: int,
    knowledge_data: KnowledgeCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建知识"""
    # 检查 Agent 是否存在
    agent = await AgentService.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")

    knowledge = await KnowledgeService.create_knowledge(db, agent_id, knowledge_data)
    return knowledge


@router.get("", response_model=dict)
async def list_knowledge(
    agent_id: int,
    type: str = Query(None, description="知识类型过滤"),
    enabled_only: bool = Query(False, description="仅显示启用的知识"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db)
):
    """列出知识"""
    # 检查 Agent 是否存在
    agent = await AgentService.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")

    skip = (page - 1) * size
    knowledge_list, total = await KnowledgeService.list_knowledge(
        db, agent_id, type, enabled_only, skip, size
    )

    return {
        "items": [KnowledgeResponse.model_validate(k) for k in knowledge_list],
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size
    }


@router.get("/{knowledge_id}", response_model=KnowledgeResponse)
async def get_knowledge(
    agent_id: int,
    knowledge_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取知识详情"""
    knowledge = await KnowledgeService.get_knowledge(db, knowledge_id)
    if not knowledge or knowledge.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="知识不存在")

    return knowledge


@router.put("/{knowledge_id}", response_model=KnowledgeResponse)
async def update_knowledge(
    agent_id: int,
    knowledge_id: int,
    knowledge_data: KnowledgeUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新知识"""
    # 检查知识是否存在且属于该 Agent
    existing = await KnowledgeService.get_knowledge(db, knowledge_id)
    if not existing or existing.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="知识不存在")

    knowledge = await KnowledgeService.update_knowledge(db, knowledge_id, knowledge_data)
    return knowledge


@router.delete("/{knowledge_id}", status_code=204)
async def delete_knowledge(
    agent_id: int,
    knowledge_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除知识"""
    # 检查知识是否存在且属于该 Agent
    existing = await KnowledgeService.get_knowledge(db, knowledge_id)
    if not existing or existing.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="知识不存在")

    await KnowledgeService.delete_knowledge(db, knowledge_id)
    return None


@router.post("/search", response_model=List[KnowledgeSearchResult])
async def search_knowledge(
    agent_id: int,
    search_request: KnowledgeSearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """向量检索知识"""
    # 检查 Agent 是否存在
    agent = await AgentService.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")

    results = await KnowledgeService.search_knowledge(db, agent_id, search_request)
    return results
