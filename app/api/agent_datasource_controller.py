"""
AgentDatasource API — 对齐 Java AgentDatasourceController
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..schemas.agent_datasource import (
    AgentDatasourceCreate,
    AgentDatasourceResponse,
    ToggleDatasourceRequest,
    UpdateDatasourceTablesRequest,
)
from ..schemas.datasource import DatasourceResponse
from ..services.agent_datasource_service import AgentDatasourceService

router = APIRouter(prefix="/api/agent", tags=["Agent-Datasource关联"])

# ═══════════════════════════════════════════════════════════════
# 静态路径必须在路径参数之前注册，避免 FastAPI 路由冲突
# ═══════════════════════════════════════════════════════════════


@router.get("/{agent_id}/datasources", summary="列出Agent的所有数据源")
async def list_agent_datasources(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """列出 Agent 的所有数据源，返回 {success, message, data: [AgentDatasourceResponse]}
    对齐 Java GET /{agentId}/datasources
    """
    try:
        items = await AgentDatasourceService.list_agent_datasources(db, agent_id)
        return {
            "success": True,
            "message": "操作成功",
            "data": [item.model_dump(by_alias=True) for item in items],
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{agent_id}/datasources/active", summary="获取Agent的激活数据源")
async def get_active_datasource(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取 Agent 当前激活的数据源 — 对齐 Java GET /{agentId}/datasources/active
    返回 AgentDatasourceResponse (含 datasource + selectTables)，而非裸 Datasource。
    """
    items = await AgentDatasourceService.list_agent_datasources(db, agent_id)
    active = next((item for item in items if item.is_active == 1), None)  # type: ignore
    if not active:
        raise HTTPException(status_code=404, detail="No active datasource found for this Agent")
    return {
        "success": True,
        "message": "操作成功",
        "data": active.model_dump(by_alias=True),
    }


@router.put("/{agent_id}/datasources/toggle", summary="切换数据源启用/禁用")
async def toggle_datasource(
    agent_id: int,
    dto: ToggleDatasourceRequest,
    db: AsyncSession = Depends(get_db),
):
    """启用/禁用 Agent 的数据源 — 对齐 Java PUT /{agentId}/datasources/toggle"""
    try:
        agent_ds = await AgentDatasourceService.toggle_datasource(
            db, agent_id, dto.datasource_id, dto.is_active
        )
        resp = AgentDatasourceResponse(
            id=agent_ds.id,
            agent_id=agent_ds.agent_id,
            datasource_id=agent_ds.datasource_id,
            is_active=agent_ds.is_active,
            created_at=agent_ds.created_at,
            updated_at=getattr(agent_ds, "updated_at", None),
            select_tables=[],
        )
        msg = "数据源已启用" if dto.is_active else "数据源已禁用"
        return {"success": True, "message": msg, "data": resp.model_dump(by_alias=True)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{agent_id}/datasources/tables", summary="更新选中的数据表")
async def update_datasource_tables(
    agent_id: int,
    dto: UpdateDatasourceTablesRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新 Agent 数据源选中的表 — 对齐 Java POST /{agentId}/datasources/tables
    前端发送 tables: [{name, comment}]，提取 name 字段存储
    """
    try:
        table_names = dto.get_table_names()
        await AgentDatasourceService.update_datasource_tables(
            db, agent_id, dto.datasource_id, table_names
        )
        return {"success": True, "message": "更新成功", "data": None}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{agent_id}/datasources/init", summary="初始化Schema到向量存储")
async def init_schema(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
):
    """初始化 Agent 的数据库 Schema 到向量存储 — 对齐 Java POST /{agentId}/datasources/init"""
    try:
        result = await AgentDatasourceService.init_schema(db, agent_id)
        if result:
            return {"success": True, "message": "Schema初始化成功", "data": None}
        else:
            raise HTTPException(status_code=500, detail="Schema初始化失败")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger = __import__("logging").getLogger(__name__)
        logger.error(f"Failed to initialize schema for agent: {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Schema初始化失败：{e}")


@router.post("/{agent_id}/datasources/{datasource_id}", summary="绑定数据源到Agent")
async def bind_datasource(
    agent_id: int,
    datasource_id: int,
    bind_data: AgentDatasourceCreate = AgentDatasourceCreate(),
    db: AsyncSession = Depends(get_db),
):
    """绑定数据源到 Agent — 对齐 Java POST /{agentId}/datasources/{datasourceId}"""
    try:
        agent_ds = await AgentDatasourceService.bind_datasource(
            db, agent_id, datasource_id, bind_data.is_active
        )
        resp = AgentDatasourceResponse(
            id=agent_ds.id,
            agent_id=agent_ds.agent_id,
            datasource_id=agent_ds.datasource_id,
            is_active=agent_ds.is_active,
            created_at=agent_ds.created_at,
            updated_at=getattr(agent_ds, "updated_at", None),
            select_tables=[],
        ).model_dump(by_alias=True)
        return {"success": True, "message": "数据源添加成功", "data": resp}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{agent_id}/datasources/{datasource_id}", summary="解绑数据源")
async def unbind_datasource(
    agent_id: int,
    datasource_id: int,
    db: AsyncSession = Depends(get_db),
):
    """解绑 Agent 的数据源 — 对齐 Java DELETE /{agentId}/datasources/{datasourceId}"""
    success = await AgentDatasourceService.unbind_datasource(db, agent_id, datasource_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent-Datasource binding not found")
    return {"success": True, "message": "数据源已移除"}
