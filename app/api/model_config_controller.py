# 模型配置相关接口
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from ..core.database import get_db
from ..schemas.common import ApiResponse
from ..core.model_registry import get_model_registry
from ..core.llm import llm_service
from ..schemas.model_config import (
    ModelConfigCreate,
    ModelConfigUpdate,
    ModelConfigResponse,
    ModelTestRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/model-config", tags=["模型配置"])


@router.get("/list", summary="列出模型配置")
async def list_models(
    type: Optional[str] = None,
    enabled: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):

    registry = get_model_registry(db)
    models = await registry.list_models(type=type, enabled=enabled)
    return ApiResponse.ok(data=models)


@router.post("/add", summary="新增模型配置")
async def create_model(config: ModelConfigCreate, db: AsyncSession = Depends(get_db)):
    
    registry = get_model_registry(db)
    try:
        model = await registry.register_model(config)
        return ApiResponse.ok(message="模型配置创建成功")
    except Exception as e:
        logger.error(f"Error creating model config: {e}")
        raise HTTPException(status_code=500, detail=f"创建模型配置失败: {str(e)}")


@router.put("/update", summary="更新模型配置")
async def update_model(update_data: ModelConfigUpdate, db: AsyncSession = Depends(get_db)):
    
    if not update_data.id:
        raise HTTPException(status_code=400, detail="更新需要提供 id 字段")
    registry = get_model_registry(db)
    model = await registry.update_model(update_data.id, update_data)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return ApiResponse.ok(message="模型配置更新成功")


@router.delete("/{model_id}", summary="删除模型配置")
async def delete_model(model_id: int, db: AsyncSession = Depends(get_db)):
    """删除模型配置"""
    registry = get_model_registry(db)
    success = await registry.delete_model(model_id)
    if not success:
        raise HTTPException(status_code=404, detail="Model not found")
    return ApiResponse.ok(message="模型配置删除成功")


@router.post("/activate/{model_id}", summary="激活/切换模型配置")
async def activate_model(model_id: int, db: AsyncSession = Depends(get_db)):
    
    registry = get_model_registry(db)
    model = await registry.set_default_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    llm_service.invalidate()
    return ApiResponse.ok(message="模型配置已激活")


@router.post("/test", summary="测试模型连接")
async def test_model(request: ModelTestRequest, db: AsyncSession = Depends(get_db)):

    registry = get_model_registry(db)
    result = await registry.test_model_with_config(
        provider=request.provider,
        api_key=request.api_key,
        base_url=request.base_url,
        model_name=request.model_name,
        model_type=request.model_type,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        prompt=request.prompt,
    )
    logger.info(f"[ModelTest] Result: {result}")
    if result.get("success"):
        return ApiResponse.ok(data=result.get("response", ""), message="连接测试成功")
    else:
        return ApiResponse.fail(message=result.get("error", "连接测试失败"))


@router.get("/check-ready", summary="检查模型就绪状态")
async def check_ready(db: AsyncSession = Depends(get_db)):
    registry = get_model_registry(db)
    chat = await registry.get_default_model("chat")
    embedding = await registry.get_default_model("embedding")
    return ApiResponse.ok(data={
        "ready": bool(chat),
        "chatModelReady": bool(chat),
        "embeddingModelReady": bool(embedding),
    })
