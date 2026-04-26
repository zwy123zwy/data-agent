from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from ..core.database import get_db
from ..schemas.agent import AgentCreate, AgentUpdate, AgentResponse, AgentListResponse
from ..services.agent_service import AgentService

router = APIRouter(prefix="/api/agents", tags=["Agent管理"])


@router.post("", response_model=AgentResponse, status_code=201, summary="创建Agent")
async def create_agent(
    agent_data: AgentCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    创建一个新的 Agent

    - **name**: Agent名称（必填，最大100字符）
    - **description**: Agent描述（可选）
    """
    agent = await AgentService.create_agent(db, agent_data)
    return agent


@router.get("", response_model=AgentListResponse, summary="列出所有Agent")
async def list_agents(
    status: Optional[str] = Query(None, description="状态过滤: draft/published/offline"),
    skip: int = Query(0, ge=0, description="分页偏移"),
    limit: int = Query(100, ge=1, le=1000, description="每页数量"),
    db: AsyncSession = Depends(get_db)
):
    """
    列出所有 Agent，支持分页和状态过滤

    - **status**: 可选，过滤状态（draft/published/offline）
    - **skip**: 分页偏移，默认0
    - **limit**: 每页数量，默认100，最大1000
    """
    agents, total = await AgentService.list_agents(db, status, skip, limit)
    return AgentListResponse(total=total, items=agents)


@router.get("/{agent_id}", response_model=AgentResponse, summary="获取Agent详情")
async def get_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    根据 ID 获取 Agent 详情

    - **agent_id**: Agent ID
    """
    agent = await AgentService.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/{agent_id}", response_model=AgentResponse, summary="更新Agent")
async def update_agent(
    agent_id: int,
    agent_data: AgentUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    更新 Agent 信息

    - **agent_id**: Agent ID
    - **name**: Agent名称（可选）
    - **description**: Agent描述（可选）
    - **status**: 状态（可选，draft/published/offline）
    - **avatar**: 头像URL（可选）
    - **tags**: 标签（可选）
    """
    agent = await AgentService.update_agent(db, agent_id, agent_data)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.delete("/{agent_id}", status_code=204, summary="删除Agent")
async def delete_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    删除 Agent

    - **agent_id**: Agent ID
    """
    success = await AgentService.delete_agent(db, agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")
    return None


@router.post("/{agent_id}/publish", response_model=AgentResponse, summary="发布Agent")
async def publish_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    发布 Agent（状态改为 published）

    - **agent_id**: Agent ID
    """
    agent = await AgentService.publish_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/{agent_id}/offline", response_model=AgentResponse, summary="下线Agent")
async def offline_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    下线 Agent（状态改为 offline）

    - **agent_id**: Agent ID
    """
    agent = await AgentService.offline_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent
