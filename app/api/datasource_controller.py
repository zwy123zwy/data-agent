from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from ..core.database import get_db
from ..schemas.datasource import (
    DatasourceCreate, DatasourceUpdate, DatasourceResponse,
    DatasourceListResponse, DatasourceTestResponse,
)
from ..services.datasource_service import DatasourceService
from ..services.schema_service import SchemaService

router = APIRouter(prefix="/api/datasource", tags=["Datasource管理"])


@router.post("", response_model=DatasourceResponse, status_code=201, summary="创建数据源")
async def create_datasource(datasource_data: DatasourceCreate, db: AsyncSession = Depends(get_db)):
    """创建一个新的数据源"""
    datasource = await DatasourceService.create_datasource(db, datasource_data)
    return datasource


@router.get("", response_model=DatasourceListResponse, summary="列出所有数据源")
async def list_datasources(
    type: Optional[str] = Query(None, description="类型过滤: mysql/postgresql/sqlite"),
    skip: int = Query(0, ge=0, description="分页偏移"),
    limit: int = Query(100, ge=1, le=1000, description="每页数量"),
    db: AsyncSession = Depends(get_db),
):
    """列出所有数据源，支持分页和类型过滤"""
    datasources, total = await DatasourceService.list_datasources(db, type, skip, limit)
    return DatasourceListResponse(total=total, items=datasources)


@router.get("/types", summary="获取支持的数据库类型")
async def list_datasource_types():
    """返回支持的数据库类型列表"""
    return [
        {"value": "mysql", "label": "MySQL"},
        {"value": "postgresql", "label": "PostgreSQL"},
        {"value": "sqlite", "label": "SQLite"},
    ]


@router.get("/{datasource_id}", response_model=DatasourceResponse, summary="获取数据源详情")
async def get_datasource(datasource_id: int, db: AsyncSession = Depends(get_db)):
    """根据 ID 获取数据源详情"""
    datasource = await DatasourceService.get_datasource(db, datasource_id)
    if not datasource:
        raise HTTPException(status_code=404, detail="Datasource not found")
    return datasource


@router.put("/{datasource_id}", response_model=DatasourceResponse, summary="更新数据源")
async def update_datasource(datasource_id: int, datasource_data: DatasourceUpdate, db: AsyncSession = Depends(get_db)):
    """更新数据源信息"""
    datasource = await DatasourceService.update_datasource(db, datasource_id, datasource_data)
    if not datasource:
        raise HTTPException(status_code=404, detail="Datasource not found")
    return datasource


@router.delete("/{datasource_id}", status_code=204, summary="删除数据源")
async def delete_datasource(datasource_id: int, db: AsyncSession = Depends(get_db)):
    """删除数据源"""
    success = await DatasourceService.delete_datasource(db, datasource_id)
    if not success:
        raise HTTPException(status_code=404, detail="Datasource not found")
    return None


@router.post("/{datasource_id}/test", response_model=DatasourceTestResponse, summary="测试数据源连接")
async def test_datasource(datasource_id: int, db: AsyncSession = Depends(get_db)):
    """测试数据源连接是否正常"""
    success, message = await DatasourceService.test_connection(db, datasource_id)
    test_status = "success" if success else "failed"
    return DatasourceTestResponse(success=success, message=message, test_status=test_status)


@router.get("/{datasource_id}/tables", summary="获取数据源的表列表")
async def list_tables(datasource_id: int, db: AsyncSession = Depends(get_db)):
    """获取指定数据源的所有表"""
    datasource = await DatasourceService.get_datasource(db, datasource_id)
    if not datasource:
        raise HTTPException(status_code=404, detail="Datasource not found")
    schema = await SchemaService.get_database_schema(datasource)
    return [{"name": table["name"], "comment": table.get("comment", "")} for table in schema["tables"]]


@router.get("/{datasource_id}/tables/{table_name}/columns", summary="获取表的字段列表")
async def list_columns(datasource_id: int, table_name: str, db: AsyncSession = Depends(get_db)):
    """获取指定表的所有字段"""
    datasource = await DatasourceService.get_datasource(db, datasource_id)
    if not datasource:
        raise HTTPException(status_code=404, detail="Datasource not found")
    schema = await SchemaService.get_database_schema(datasource, [table_name])
    if not schema["tables"]:
        raise HTTPException(status_code=404, detail="Table not found")
    return schema["tables"][0].get("columns", [])
