from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..schemas.agent_datasource import (
    AgentDatasourceCreate,
    AgentDatasourceResponse,
    AgentDatasourceWithDetails,
    AgentDatasourceListResponse
)
from ..schemas.datasource import DatasourceResponse
from ..services.agent_datasource_service import AgentDatasourceService

router = APIRouter(prefix="/api/agent", tags=["Agent-Datasource关联"])


@router.post(
    "/{agent_id}/datasources/{datasource_id}",
    response_model=AgentDatasourceResponse,
    status_code=201,
    summary="绑定数据源到Agent"
)
async def bind_datasource(
    agent_id: int,
    datasource_id: int,
    bind_data: AgentDatasourceCreate = AgentDatasourceCreate(),
    db: AsyncSession = Depends(get_db)
):
    """
    绑定数据源到 Agent

    - **agent_id**: Agent ID
    - **datasource_id**: Datasource ID
    - **is_active**: 是否激活（默认 true）

    如果设置为激活，会自动将该 Agent 的其他数据源设为非激活
    """
    try:
        agent_datasource = await AgentDatasourceService.bind_datasource(
            db, agent_id, datasource_id, bind_data.is_active
        )
        return agent_datasource
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/{agent_id}/datasources/{datasource_id}",
    status_code=204,
    summary="解绑数据源"
)
async def unbind_datasource(
    agent_id: int,
    datasource_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    解绑 Agent 的数据源

    - **agent_id**: Agent ID
    - **datasource_id**: Datasource ID
    """
    success = await AgentDatasourceService.unbind_datasource(db, agent_id, datasource_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent-Datasource binding not found")
    return None


@router.get(
    "/{agent_id}/datasources",
    response_model=AgentDatasourceListResponse,
    summary="列出Agent的所有数据源"
)
async def list_agent_datasources(
    agent_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    列出 Agent 的所有数据源

    - **agent_id**: Agent ID

    返回数据源列表，包含数据源详情和激活状态
    """
    try:
        items, total = await AgentDatasourceService.list_agent_datasources(db, agent_id)

        # 构建响应
        response_items = []
        for agent_datasource, datasource in items:
            item = AgentDatasourceWithDetails(
                id=agent_datasource.id,
                agent_id=agent_datasource.agent_id,
                datasource_id=agent_datasource.datasource_id,
                is_active=agent_datasource.is_active,
                created_at=agent_datasource.created_at,
                datasource={
                    "id": datasource.id,
                    "name": datasource.name,
                    "type": datasource.type,
                    "database": datasource.database,
                    "test_status": datasource.test_status
                }
            )
            response_items.append(item)

        return AgentDatasourceListResponse(total=total, items=response_items)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/{agent_id}/datasources/active",
    response_model=DatasourceResponse,
    summary="获取Agent的激活数据源"
)
async def get_active_datasource(
    agent_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    获取 Agent 当前激活的数据源

    - **agent_id**: Agent ID

    返回激活的数据源详情，如果没有激活的数据源则返回 404
    """
    datasource = await AgentDatasourceService.get_active_datasource(db, agent_id)
    if not datasource:
        raise HTTPException(status_code=404, detail="No active datasource found for this Agent")
    return datasource


@router.post(
    "/{agent_id}/datasources/{datasource_id}/activate",
    response_model=AgentDatasourceResponse,
    summary="激活数据源"
)
async def activate_datasource(
    agent_id: int,
    datasource_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    激活 Agent 的指定数据源

    - **agent_id**: Agent ID
    - **datasource_id**: Datasource ID

    会自动将该 Agent 的其他数据源设为非激活
    """
    try:
        agent_datasource = await AgentDatasourceService.activate_datasource(
            db, agent_id, datasource_id
        )
        return agent_datasource
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
