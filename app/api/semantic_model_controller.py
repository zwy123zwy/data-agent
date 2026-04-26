"""
SemanticModel API
语义模型管理接口
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from ..core.database import get_db
from ..services.semantic_model_service import SemanticModelService
from ..services.agent_service import AgentService
from ..services.datasource_service import DatasourceService
from ..schemas.semantic_model import (
    SemanticModelCreate,
    SemanticModelUpdate,
    SemanticModelResponse,
    SemanticModelSearchRequest
)

router = APIRouter(prefix="/api/agents/{agent_id}/semantic-models", tags=["SemanticModel"])


@router.post("", response_model=SemanticModelResponse, status_code=201)
async def create_semantic_model(
    agent_id: int,
    model_data: SemanticModelCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建语义模型"""
    # 检查 Agent 是否存在
    agent = await AgentService.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")

    # 检查数据源是否存在
    datasource = await DatasourceService.get_datasource(db, model_data.datasource_id)
    if not datasource:
        raise HTTPException(status_code=404, detail="数据源不存在")

    semantic_model = await SemanticModelService.create_semantic_model(db, agent_id, model_data)
    return semantic_model


@router.get("", response_model=dict)
async def list_semantic_models(
    agent_id: int,
    datasource_id: int = Query(None, description="数据源ID过滤"),
    table_name: str = Query(None, description="表名过滤"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db)
):
    """列出语义模型"""
    # 检查 Agent 是否存在
    agent = await AgentService.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")

    skip = (page - 1) * size
    models, total = await SemanticModelService.list_semantic_models(
        db, agent_id, datasource_id, table_name, skip, size
    )

    return {
        "items": [SemanticModelResponse.model_validate(m) for m in models],
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size
    }


@router.get("/{model_id}", response_model=SemanticModelResponse)
async def get_semantic_model(
    agent_id: int,
    model_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取语义模型详情"""
    semantic_model = await SemanticModelService.get_semantic_model(db, model_id)
    if not semantic_model or semantic_model.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="语义模型不存在")

    return semantic_model


@router.put("/{model_id}", response_model=SemanticModelResponse)
async def update_semantic_model(
    agent_id: int,
    model_id: int,
    model_data: SemanticModelUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新语义模型"""
    # 检查语义模型是否存在且属于该 Agent
    existing = await SemanticModelService.get_semantic_model(db, model_id)
    if not existing or existing.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="语义模型不存在")

    semantic_model = await SemanticModelService.update_semantic_model(db, model_id, model_data)
    return semantic_model


@router.delete("/{model_id}", status_code=204)
async def delete_semantic_model(
    agent_id: int,
    model_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除语义模型"""
    # 检查语义模型是否存在且属于该 Agent
    existing = await SemanticModelService.get_semantic_model(db, model_id)
    if not existing or existing.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="语义模型不存在")

    await SemanticModelService.delete_semantic_model(db, model_id)
    return None


@router.post("/search", response_model=List[SemanticModelResponse])
async def search_semantic_models(
    agent_id: int,
    search_request: SemanticModelSearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """搜索语义模型"""
    # 检查 Agent 是否存在
    agent = await AgentService.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")

    results = await SemanticModelService.search_semantic_models(db, agent_id, search_request)
    return results
