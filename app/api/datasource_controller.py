from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from ..core.database import get_db
from ..schemas.datasource import (
    DatasourceCreate,
    DatasourceUpdate,
    DatasourceResponse,
    DatasourceListResponse,
    DatasourceTestResponse
)
from ..services.datasource_service import DatasourceService

router = APIRouter(prefix="/api/datasources", tags=["Datasource管理"])


@router.post("", response_model=DatasourceResponse, status_code=201, summary="创建数据源")
async def create_datasource(
    datasource_data: DatasourceCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    创建一个新的数据源

    - **name**: 数据源名称（必填）
    - **type**: 数据库类型（必填，mysql/postgresql/sqlite）
    - **database**: 数据库名（必填）
    - **host**: 主机地址（MySQL/PostgreSQL 必填）
    - **port**: 端口号（MySQL/PostgreSQL 必填）
    - **username**: 用户名（MySQL/PostgreSQL 必填）
    - **password**: 密码（MySQL/PostgreSQL 必填）
    - **connection_url**: 连接字符串（SQLite 必填）
    """
    datasource = await DatasourceService.create_datasource(db, datasource_data)
    return datasource


@router.get("", response_model=DatasourceListResponse, summary="列出所有数据源")
async def list_datasources(
    type: Optional[str] = Query(None, description="类型过滤: mysql/postgresql/sqlite"),
    skip: int = Query(0, ge=0, description="分页偏移"),
    limit: int = Query(100, ge=1, le=1000, description="每页数量"),
    db: AsyncSession = Depends(get_db)
):
    """
    列出所有数据源，支持分页和类型过滤

    - **type**: 可选，过滤类型（mysql/postgresql/sqlite）
    - **skip**: 分页偏移，默认0
    - **limit**: 每页数量，默认100，最大1000
    """
    datasources, total = await DatasourceService.list_datasources(db, type, skip, limit)
    return DatasourceListResponse(total=total, items=datasources)


@router.get("/{datasource_id}", response_model=DatasourceResponse, summary="获取数据源详情")
async def get_datasource(
    datasource_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    根据 ID 获取数据源详情

    - **datasource_id**: 数据源 ID
    """
    datasource = await DatasourceService.get_datasource(db, datasource_id)
    if not datasource:
        raise HTTPException(status_code=404, detail="Datasource not found")
    return datasource


@router.put("/{datasource_id}", response_model=DatasourceResponse, summary="更新数据源")
async def update_datasource(
    datasource_id: int,
    datasource_data: DatasourceUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    更新数据源信息

    - **datasource_id**: 数据源 ID
    - **name**: 数据源名称（可选）
    - **host**: 主机地址（可选）
    - **port**: 端口号（可选）
    - **username**: 用户名（可选）
    - **password**: 密码（可选）
    - **connection_url**: 连接字符串（可选）
    """
    datasource = await DatasourceService.update_datasource(db, datasource_id, datasource_data)
    if not datasource:
        raise HTTPException(status_code=404, detail="Datasource not found")
    return datasource


@router.delete("/{datasource_id}", status_code=204, summary="删除数据源")
async def delete_datasource(
    datasource_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    删除数据源

    - **datasource_id**: 数据源 ID
    """
    success = await DatasourceService.delete_datasource(db, datasource_id)
    if not success:
        raise HTTPException(status_code=404, detail="Datasource not found")
    return None


@router.post("/{datasource_id}/test", response_model=DatasourceTestResponse, summary="测试数据源连接")
async def test_datasource(
    datasource_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    测试数据源连接是否正常

    - **datasource_id**: 数据源 ID

    返回测试结果和状态
    """
    success, message = await DatasourceService.test_connection(db, datasource_id)
    test_status = "success" if success else "failed"

    return DatasourceTestResponse(
        success=success,
        message=message,
        test_status=test_status
    )
