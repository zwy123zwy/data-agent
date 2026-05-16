"""
PromptConfig API — 对齐 Java PromptConfigController (14 个端点)
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from ..core.database import get_db
from ..schemas.common import ApiResponse
from ..services.prompt_config_service import PromptConfigService
from ..schemas.prompt_config import (
    PromptConfigSaveRequest,
    PromptConfigUpdateRequest,
    PromptConfigResponse,
    PriorityUpdateRequest,
    DisplayOrderUpdateRequest,
    SUPPORTED_PROMPT_TYPES,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prompt-config", tags=["Prompt配置"])


# ================================================================
# POST 创建/更新
# ================================================================

@router.post("/save", summary="创建或更新配置")
async def save_config(
    dto: PromptConfigSaveRequest,
    db: AsyncSession = Depends(get_db),
):
    """创建或更新 Prompt 配置 — 对齐 Java POST /api/prompt-config/save"""
    cfg = await PromptConfigService.save_or_update(db, dto)
    return ApiResponse.ok(
        data=PromptConfigResponse.model_validate(cfg).model_dump(by_alias=True),
        message="优化配置保存成功",
    )


# ================================================================
# GET 静态路径 (必须在 /{config_id} 之前注册)
# ================================================================

@router.get("/list", summary="获取所有配置")
async def list_configs(db: AsyncSession = Depends(get_db)):
    """获取所有配置 — 对齐 Java GET /api/prompt-config/list"""
    configs = await PromptConfigService.get_all(db)
    return {
        "success": True,
        "data": [PromptConfigResponse.model_validate(c).model_dump(by_alias=True) for c in configs],
        "total": len(configs),
    }


@router.get("/list-by-type/{prompt_type}", summary="按类型查询配置")
async def list_by_type(
    prompt_type: str,
    agent_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """按类型+Agent查询 — 对齐 Java GET /api/prompt-config/list-by-type/{promptType}?agentId="""
    configs = await PromptConfigService.get_by_type(db, prompt_type, agent_id)
    return {
        "success": True,
        "data": [PromptConfigResponse.model_validate(c).model_dump(by_alias=True) for c in configs],
        "total": len(configs),
    }


@router.get("/active/{prompt_type}", summary="获取当前激活的配置")
async def get_active_config(
    prompt_type: str,
    agent_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """获取当前激活的配置 — 对齐 Java GET /api/prompt-config/active/{promptType}?agentId="""
    cfg = await PromptConfigService.get_active_by_type(db, prompt_type, agent_id)
    return {
        "success": True,
        "data": PromptConfigResponse.model_validate(cfg).model_dump(by_alias=True) if cfg else None,
        "hasCustomConfig": cfg is not None,
    }


@router.get("/active-all/{prompt_type}", summary="获取所有激活的配置")
async def get_active_configs(
    prompt_type: str,
    agent_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """获取所有激活的配置 — 对齐 Java GET /api/prompt-config/active-all/{promptType}?agentId="""
    configs = await PromptConfigService.get_active_all_by_type(db, prompt_type, agent_id)
    return {
        "success": True,
        "data": [PromptConfigResponse.model_validate(c).model_dump(by_alias=True) for c in configs],
        "total": len(configs),
        "hasOptimizationConfigs": len(configs) > 0,
    }


@router.get("/types", summary="获取支持的提示词类型")
async def get_types():
    """获取支持的提示词类型 — 对齐 Java GET /api/prompt-config/types"""
    return ApiResponse.ok(data=SUPPORTED_PROMPT_TYPES)


# ================================================================
# POST 批量操作 (静态路径)
# ================================================================

@router.post("/batch-enable", summary="批量启用")
async def batch_enable(ids: List[str] = Body(...), db: AsyncSession = Depends(get_db)):
    """批量启用 — 对齐 Java POST /api/prompt-config/batch-enable"""
    await PromptConfigService.batch_enable(db, ids)
    return ApiResponse.ok(message="批量启用配置成功")


@router.post("/batch-disable", summary="批量禁用")
async def batch_disable(ids: List[str] = Body(...), db: AsyncSession = Depends(get_db)):
    """批量禁用 — 对齐 Java POST /api/prompt-config/batch-disable"""
    await PromptConfigService.batch_disable(db, ids)
    return ApiResponse.ok(message="批量禁用配置成功")


# ================================================================
# 按 ID 查 (路径参数 — 必须在所有静态路径之后注册)
# ================================================================

@router.get("/{config_id}", summary="获取配置详情")
async def get_config(config_id: str, db: AsyncSession = Depends(get_db)):
    """获取配置详情 — 对齐 Java GET /api/prompt-config/{id}"""
    cfg = await PromptConfigService.get_by_id(db, config_id)
    if not cfg:
        return ApiResponse.fail(message="配置不存在")
    return ApiResponse.ok(data=PromptConfigResponse.model_validate(cfg).model_dump(by_alias=True))


# ================================================================
# 删除
# ================================================================

@router.delete("/{config_id}", summary="删除配置")
async def delete_config(config_id: str, db: AsyncSession = Depends(get_db)):
    """删除配置 — 对齐 Java DELETE /api/prompt-config/{id}"""
    ok = await PromptConfigService.delete_config(db, config_id)
    if not ok:
        return ApiResponse.fail(message="配置不存在或删除失败")
    return ApiResponse.ok(message="配置删除成功")


# ================================================================
# 启用/禁用 (子路径 — 静态部分 + 路径参数)
# ================================================================

@router.post("/{config_id}/enable", summary="启用配置")
async def enable_config(config_id: str, db: AsyncSession = Depends(get_db)):
    """启用配置 — 对齐 Java POST /api/prompt-config/{id}/enable"""
    ok = await PromptConfigService.enable_config(db, config_id)
    if not ok:
        return ApiResponse.fail(message="配置不存在或启用失败")
    return ApiResponse.ok(message="配置启用成功")


@router.post("/{config_id}/disable", summary="禁用配置")
async def disable_config(config_id: str, db: AsyncSession = Depends(get_db)):
    """禁用配置 — 对齐 Java POST /api/prompt-config/{id}/disable"""
    ok = await PromptConfigService.disable_config(db, config_id)
    if not ok:
        return ApiResponse.fail(message="配置不存在或禁用失败")
    return ApiResponse.ok(message="配置禁用成功")


# ================================================================
# 优先级 / 显示顺序
# ================================================================

@router.post("/{config_id}/priority", summary="更新优先级")
async def update_priority(
    config_id: str,
    body: PriorityUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新优先级 — 对齐 Java POST /api/prompt-config/{id}/priority"""
    ok = await PromptConfigService.update_priority(db, config_id, body.priority)
    if not ok:
        return ApiResponse.fail(message="更新优先级失败")
    return ApiResponse.ok(message="更新优先级成功")


@router.post("/{config_id}/display-order", summary="更新显示顺序")
async def update_display_order(
    config_id: str,
    body: DisplayOrderUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新显示顺序 — 对齐 Java POST /api/prompt-config/{id}/display-order"""
    ok = await PromptConfigService.update_display_order(db, config_id, body.display_order)
    if not ok:
        return ApiResponse.fail(message="更新显示顺序失败")
    return ApiResponse.ok(message="更新显示顺序成功")
