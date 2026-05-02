"""
模型配置管理 API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Any
from pydantic import BaseModel
from ..core.database import get_db
from ..core.model_registry import get_model_registry, ModelRegistry
from ..schemas.model_config import (
    ModelConfigCreate,
    ModelConfigUpdate,
    ModelConfigResponse,
    ModelTestRequest
)

router = APIRouter()
legacy_router = APIRouter(prefix="/api/model-config", tags=["模型配置-兼容路径"])


class ModelUpdateRequest(BaseModel):
    id: int
    data: ModelConfigUpdate


class ModelTestLegacyRequest(BaseModel):
    model_id: int
    prompt: str = "Hello, how are you?"


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


@legacy_router.get("/list", response_model=List[ModelConfigResponse], include_in_schema=False)
async def list_models_legacy(
    type: Optional[str] = None,
    enabled: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):
    return await list_models(type=type, enabled=enabled, db=db)


@legacy_router.post("/add", response_model=ModelConfigResponse, include_in_schema=False)
async def add_model_legacy(config: ModelConfigCreate, db: AsyncSession = Depends(get_db)):
    return await create_model(config=config, db=db)


@legacy_router.put("/update", response_model=ModelConfigResponse, include_in_schema=False)
async def update_model_legacy(payload: ModelUpdateRequest, db: AsyncSession = Depends(get_db)):
    return await update_model(model_id=payload.id, update_data=payload.data, db=db)


@legacy_router.delete("/{id}", include_in_schema=False)
async def delete_model_legacy(id: int, db: AsyncSession = Depends(get_db)):
    return await delete_model(model_id=id, db=db)


@legacy_router.post("/activate/{id}", response_model=ModelConfigResponse, include_in_schema=False)
async def activate_model_legacy(id: int, db: AsyncSession = Depends(get_db)):
    return await set_default_model(model_id=id, db=db)


@legacy_router.post("/test", include_in_schema=False)
async def test_model_legacy(payload: ModelTestLegacyRequest, db: AsyncSession = Depends(get_db)):
    req = ModelTestRequest(prompt=payload.prompt)
    return await test_model(model_id=payload.model_id, request=req, db=db)


@legacy_router.get("/check-ready", include_in_schema=False)
async def check_ready_legacy(db: AsyncSession = Depends(get_db)):
    registry = get_model_registry(db)
    chat = await registry.get_default_model("chat")
    embedding = await registry.get_default_model("embedding")
    return {"ready": bool(chat), "chatReady": bool(chat), "embeddingReady": bool(embedding)}
