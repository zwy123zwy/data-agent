"""
模型配置管理 API — 对齐 Java ModelConfigController
Java 路由风格: /list, /add, /update, /activate/{id}, /test, /check-ready
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from ..core.database import get_db
from ..core.model_registry import get_model_registry
from ..schemas.model_config import (
    ModelConfigCreate,
    ModelConfigUpdate,
    ModelConfigResponse,
    ModelTestRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/model-config", tags=["模型配置"])


@router.get("/list", response_model=List[ModelConfigResponse], summary="列出模型配置")
async def list_models(
    type: Optional[str] = None,
    enabled: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):
    """列出模型配置 — 对齐 Java GET /api/model-config/list"""
    registry = get_model_registry(db)
    models = await registry.list_models(type=type, enabled=enabled)
    return models


@router.post("/add", summary="新增模型配置")
async def create_model(config: ModelConfigCreate, db: AsyncSession = Depends(get_db)):
    """新增模型配置 — 对齐 Java POST /api/model-config/add"""
    registry = get_model_registry(db)
    # 自动生成 name (如果未提供)
    if not config.name:
        config.name = f"{config.provider}-{config.model_id}"
    try:
        model = await registry.register_model(config)
        return {"success": True, "message": "模型配置创建成功", "data": None}
    except Exception as e:
        logger.error(f"Error creating model config: {e}")
        raise HTTPException(status_code=500, detail=f"创建模型配置失败: {str(e)}")


@router.put("/update", summary="更新模型配置")
async def update_model(update_data: ModelConfigUpdate, db: AsyncSession = Depends(get_db)):
    """更新模型配置 — 对齐 Java PUT /api/model-config/update (id 从 Body)"""
    if not update_data.id:
        raise HTTPException(status_code=400, detail="更新需要提供 id 字段")
    registry = get_model_registry(db)
    model = await registry.update_model(update_data.id, update_data)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"success": True, "message": "模型配置更新成功", "data": None}


@router.delete("/{model_id}", summary="删除模型配置")
async def delete_model(model_id: int, db: AsyncSession = Depends(get_db)):
    """删除模型配置 — 对齐 Java DELETE /api/model-config/{id}"""
    registry = get_model_registry(db)
    success = await registry.delete_model(model_id)
    if not success:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"success": True, "message": "模型配置删除成功", "data": None}


@router.post("/activate/{model_id}", summary="激活/切换模型配置")
async def activate_model(model_id: int, db: AsyncSession = Depends(get_db)):
    """激活模型配置 — 对齐 Java POST /api/model-config/activate/{id}"""
    registry = get_model_registry(db)
    model = await registry.set_default_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"success": True, "message": "模型配置已激活", "data": None}


@router.post("/test", summary="测试模型连接")
async def test_model(request: ModelTestRequest, db: AsyncSession = Depends(get_db)):
    """测试模型连接 — 对齐 Java POST /api/model-config/test (config 从 Body, 无需预存)"""
    registry = get_model_registry(db)
    result = await registry.test_model_with_config(
        provider=request.provider,
        api_key=request.api_key,
        api_base=request.api_base,
        model_id=request.model_id,
        model_type=request.type,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        prompt=request.prompt,
    )
    if result.get("success"):
        return {"success": True, "message": "连接测试成功", "data": result.get("response", "")}
    else:
        return {"success": False, "message": result.get("error", "连接测试失败"), "data": None}


@router.get("/check-ready", summary="检查模型就绪状态")
async def check_ready(db: AsyncSession = Depends(get_db)):
    """检查是否有可用的默认模型 — 对齐 Java GET /api/model-config/check-ready"""
    registry = get_model_registry(db)
    chat = await registry.get_default_model("chat")
    embedding = await registry.get_default_model("embedding")
    return {
        "ready": bool(chat),
        "chatModelReady": bool(chat),
        "embeddingModelReady": bool(embedding),
    }


# ============ 兼容旧路由 (Phase 1 迁移期) ============

@router.get("", response_model=List[ModelConfigResponse], summary="[兼容] 列出模型配置")
async def list_models_compat(
    type: Optional[str] = None,
    enabled: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):
    """[兼容旧路由] GET /api/model-config — 等同于 /list"""
    registry = get_model_registry(db)
    models = await registry.list_models(type=type, enabled=enabled)
    return models


@router.post("", summary="[兼容] 创建模型配置")
async def create_model_compat(config: ModelConfigCreate, db: AsyncSession = Depends(get_db)):
    """[兼容旧路由] POST /api/model-config — 等同于 /add"""
    registry = get_model_registry(db)
    if not config.name:
        config.name = f"{config.provider}-{config.model_id}"
    try:
        model = await registry.register_model(config)
        return {"success": True, "message": "模型配置创建成功", "data": None}
    except Exception as e:
        logger.error(f"Error creating model config: {e}")
        raise HTTPException(status_code=500, detail=f"创建模型配置失败: {str(e)}")
