"""
模型配置管理 API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from ..core.database import get_db
from ..core.model_registry import get_model_registry, ModelRegistry
from ..schemas.model_config import (
    ModelConfigCreate,
    ModelConfigUpdate,
    ModelConfigResponse,
    ModelTestRequest
)

router = APIRouter()


@router.post("/models", response_model=ModelConfigResponse, summary="创建模型配置")
async def create_model(
    config: ModelConfigCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建模型配置"""
    registry = get_model_registry(db)
    model = await registry.register_model(config)
    return model


@router.get("/models", response_model=List[ModelConfigResponse], summary="列出模型配置")
async def list_models(
    type: Optional[str] = None,
    enabled: Optional[bool] = None,
    db: AsyncSession = Depends(get_db)
):
    """列出模型配置"""
    registry = get_model_registry(db)
    models = await registry.list_models(type=type, enabled=enabled)
    return models


@router.get("/models/{model_id}", response_model=ModelConfigResponse, summary="获取模型详情")
async def get_model(
    model_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取模型详情"""
    registry = get_model_registry(db)
    model = await registry.get_model_by_id(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.put("/models/{model_id}", response_model=ModelConfigResponse, summary="更新模型配置")
async def update_model(
    model_id: int,
    update_data: ModelConfigUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新模型配置"""
    registry = get_model_registry(db)
    model = await registry.update_model(model_id, update_data)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.delete("/models/{model_id}", summary="删除模型配置")
async def delete_model(
    model_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除模型配置"""
    registry = get_model_registry(db)
    success = await registry.delete_model(model_id)
    if not success:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"message": "Model deleted successfully"}


@router.post("/models/{model_id}/set-default", response_model=ModelConfigResponse, summary="设置默认模型")
async def set_default_model(
    model_id: int,
    db: AsyncSession = Depends(get_db)
):
    """设置默认模型"""
    registry = get_model_registry(db)
    model = await registry.set_default_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.post("/models/{model_id}/test", summary="测试模型")
async def test_model(
    model_id: int,
    request: ModelTestRequest,
    db: AsyncSession = Depends(get_db)
):
    """测试模型"""
    registry = get_model_registry(db)
    result = await registry.test_model(model_id, request.prompt)
    return result
