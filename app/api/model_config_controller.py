"""
模型配置管理 API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from ..core.database import get_db
from ..core.model_registry import get_model_registry
from ..schemas.model_config import (
    ModelConfigCreate, ModelConfigUpdate, ModelConfigResponse, ModelTestRequest,
)

router = APIRouter(prefix="/api/model-config", tags=["模型配置"])


@router.post("", response_model=ModelConfigResponse, status_code=201, summary="创建模型配置")
async def create_model(config: ModelConfigCreate, db: AsyncSession = Depends(get_db)):
    """创建模型配置"""
    registry = get_model_registry(db)
    model = await registry.register_model(config)
    return model


@router.get("", response_model=List[ModelConfigResponse], summary="列出模型配置")
async def list_models(
    type: Optional[str] = None,
    enabled: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):
    """列出模型配置"""
    registry = get_model_registry(db)
    models = await registry.list_models(type=type, enabled=enabled)
    return models


@router.get("/check-ready", summary="检查模型就绪状态")
async def check_ready(db: AsyncSession = Depends(get_db)):
    """检查是否有可用的默认模型"""
    registry = get_model_registry(db)
    chat = await registry.get_default_model("chat")
    embedding = await registry.get_default_model("embedding")
    return {
        "ready": bool(chat),
        "chatReady": bool(chat),
        "embeddingReady": bool(embedding),
    }


@router.get("/{model_id}", response_model=ModelConfigResponse, summary="获取模型详情")
async def get_model(model_id: int, db: AsyncSession = Depends(get_db)):
    """获取模型详情"""
    registry = get_model_registry(db)
    model = await registry.get_model_by_id(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.put("/{model_id}", response_model=ModelConfigResponse, summary="更新模型配置")
async def update_model(model_id: int, update_data: ModelConfigUpdate, db: AsyncSession = Depends(get_db)):
    """更新模型配置"""
    registry = get_model_registry(db)
    model = await registry.update_model(model_id, update_data)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.delete("/{model_id}", summary="删除模型配置")
async def delete_model(model_id: int, db: AsyncSession = Depends(get_db)):
    """删除模型配置"""
    registry = get_model_registry(db)
    success = await registry.delete_model(model_id)
    if not success:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"message": "Model deleted successfully"}


@router.post("/{model_id}/set-default", response_model=ModelConfigResponse, summary="设置默认模型")
async def set_default_model(model_id: int, db: AsyncSession = Depends(get_db)):
    """设置默认模型"""
    registry = get_model_registry(db)
    model = await registry.set_default_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.post("/{model_id}/test", summary="测试模型")
async def test_model(model_id: int, request: ModelTestRequest, db: AsyncSession = Depends(get_db)):
    """测试模型"""
    registry = get_model_registry(db)
    result = await registry.test_model(model_id, request.prompt)
    return result
