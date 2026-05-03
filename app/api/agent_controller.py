from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from ..core.database import get_db
from ..schemas.agent import AgentCreate, AgentUpdate, AgentResponse, AgentListResponse
from ..services.agent_service import AgentService

router = APIRouter(prefix="/api/agent", tags=["Agent管理"])


@router.post("", response_model=AgentResponse, status_code=201, summary="创建Agent")
async def create_agent(agent_data: AgentCreate, db: AsyncSession = Depends(get_db)):
    """创建一个新的 Agent"""
    agent = await AgentService.create_agent(db, agent_data)
    return agent


@router.get("/list", response_model=list[AgentResponse], summary="[前端] 列出所有Agent")
async def list_agents_frontend(
    status: Optional[str] = Query(None, description="状态过滤: draft/published/offline"),
    keyword: Optional[str] = Query(None, description="关键词搜索 (名称/描述)"),
    db: AsyncSession = Depends(get_db),
):
    """列出所有 Agent — 对齐 Java GET /api/agent/list?status=&keyword="""
    agents, total = await AgentService.list_agents(db, status=status, keyword=keyword)
    return agents


@router.get("", response_model=AgentListResponse, summary="列出所有Agent")
async def list_agents(
    status: Optional[str] = Query(None, description="状态过滤: draft/published/offline"),
    skip: int = Query(0, ge=0, description="分页偏移"),
    limit: int = Query(100, ge=1, le=1000, description="每页数量"),
    db: AsyncSession = Depends(get_db),
):
    """列出所有 Agent，支持分页和状态过滤"""
    agents, total = await AgentService.list_agents(db, status, skip, limit)
    return AgentListResponse(total=total, items=agents)


@router.get("/{agent_id}", response_model=AgentResponse, summary="获取Agent详情")
async def get_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    """根据 ID 获取 Agent 详情"""
    agent = await AgentService.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/{agent_id}", response_model=AgentResponse, summary="更新Agent")
async def update_agent(agent_id: int, agent_data: AgentUpdate, db: AsyncSession = Depends(get_db)):
    """更新 Agent 信息"""
    agent = await AgentService.update_agent(db, agent_id, agent_data)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.delete("/{agent_id}", status_code=204, summary="删除Agent")
async def delete_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    """删除 Agent"""
    success = await AgentService.delete_agent(db, agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")
    return None


@router.post("/{agent_id}/publish", response_model=AgentResponse, summary="发布Agent")
async def publish_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    """发布 Agent（状态改为 published）"""
    agent = await AgentService.publish_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/{agent_id}/offline", response_model=AgentResponse, summary="下线Agent")
async def offline_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    """下线 Agent（状态改为 offline）"""
    agent = await AgentService.offline_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


# ==================================================================
# API Key 管理 — 对齐 Java AgentController
# ==================================================================

@router.get("/{agent_id}/api-key", summary="获取API Key状态")
async def get_api_key(agent_id: int, db: AsyncSession = Depends(get_db)):
    """获取脱敏后的 API Key 状态 — 对齐 Java getApiKey"""
    agent = await AgentService.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    masked = AgentService._mask_api_key(agent.api_key)
    return {"success": True, "message": "获取 API Key 成功", "data": {
        "api_key": masked,
        "api_key_enabled": agent.api_key_enabled,
    }}


@router.post("/{agent_id}/api-key/generate", summary="生成API Key")
async def generate_api_key(agent_id: int, db: AsyncSession = Depends(get_db)):
    """生成 API Key — 对齐 Java generateApiKey"""
    agent = await AgentService.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent = await AgentService.generate_api_key(db, agent_id)
    return {"success": True, "message": "生成 API Key 成功", "data": {
        "api_key": agent.api_key,
        "api_key_enabled": agent.api_key_enabled,
    }}


@router.post("/{agent_id}/api-key/reset", summary="重置API Key")
async def reset_api_key(agent_id: int, db: AsyncSession = Depends(get_db)):
    """重置 API Key — 对齐 Java resetApiKey"""
    agent = await AgentService.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent = await AgentService.reset_api_key(db, agent_id)
    return {"success": True, "message": "重置 API Key 成功", "data": {
        "api_key": agent.api_key,
        "api_key_enabled": agent.api_key_enabled,
    }}


@router.delete("/{agent_id}/api-key", summary="删除API Key")
async def delete_api_key(agent_id: int, db: AsyncSession = Depends(get_db)):
    """删除 API Key — 对齐 Java deleteApiKey"""
    agent = await AgentService.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent = await AgentService.delete_api_key(db, agent_id)
    return {"success": True, "message": "删除 API Key 成功", "data": {
        "api_key": AgentService._mask_api_key(agent.api_key),
        "api_key_enabled": agent.api_key_enabled,
    }}


@router.post("/{agent_id}/api-key/enable", summary="启用/禁用API Key")
async def toggle_api_key(
    agent_id: int,
    enabled: bool = Query(..., description="true=启用, false=禁用"),
    db: AsyncSession = Depends(get_db),
):
    """启用/禁用 API Key — 对齐 Java toggleApiKey"""
    agent = await AgentService.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent = await AgentService.toggle_api_key(db, agent_id, enabled)
    masked = AgentService._mask_api_key(agent.api_key)
    return {"success": True, "message": "更新 API Key 状态成功", "data": {
        "api_key": masked,
        "api_key_enabled": agent.api_key_enabled,
    }}
