from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from ..core.database import get_db
from ..schemas.common import ApiResponse
from ..schemas.datasource import (
    DatasourceCreate, DatasourceUpdate, DatasourceResponse,
    DatasourceListResponse, DatasourceTestResponse,
)
from ..services.datasource_service import DatasourceService
from ..services.schema_service import SchemaService
from ..services.logical_relation_service import LogicalRelationService
from ..schemas.logical_relation import LogicalRelationCreate, LogicalRelationUpdate, LogicalRelationResponse

router = APIRouter(prefix="/api/datasource", tags=["Datasource管理"])


@router.post("", status_code=201, summary="创建数据源")
async def create_datasource(datasource_data: DatasourceCreate, db: AsyncSession = Depends(get_db)):
    """创建一个新的数据源"""
    datasource = await DatasourceService.create_datasource(db, datasource_data)
    return ApiResponse.ok(data=datasource)


@router.get("", summary="列出所有数据源")
async def list_datasources(
    type: Optional[str] = Query(None, description="类型过滤: mysql/postgresql/sqlite"),
    status: Optional[str] = Query(None, description="状态过滤: active/inactive/deleted"),
    skip: int = Query(0, ge=0, description="分页偏移"),
    limit: int = Query(100, ge=1, le=1000, description="每页数量"),
    db: AsyncSession = Depends(get_db),
):
    """列出所有数据源，支持分页和类型/状态过滤 — 对齐 Java 返回裸数组"""
    datasources, total = await DatasourceService.list_datasources(db, type, status, skip, limit)
    return ApiResponse.ok(data=datasources)


@router.get("/types", summary="获取支持的数据库类型")
async def list_datasource_types():
    """返回支持的数据库类型列表 — 对齐 Java DatasourceType {code, typeName, dialect, protocol, displayName}"""
    return ApiResponse.ok(data=[
        {"code": 1,  "typeName": "mysql",      "dialect": "MySQL",       "protocol": "mysql",      "displayName": "MySQL"},
        {"code": 2,  "typeName": "postgresql",  "dialect": "PostgreSQL",  "protocol": "postgresql", "displayName": "PostgreSQL"},
        {"code": 3,  "typeName": "sqlite",      "dialect": "SQLite",      "protocol": "sqlite",     "displayName": "SQLite"},
        {"code": 4,  "typeName": "h2",          "dialect": "H2",          "protocol": "h2",         "displayName": "H2"},
        {"code": 5,  "typeName": "dameng",      "dialect": "Dameng",      "protocol": "dameng",     "displayName": "达梦"},
        {"code": 6,  "typeName": "mssql",       "dialect": "SQL Server",  "protocol": "mssql",      "displayName": "SQL Server"},
        {"code": 7,  "typeName": "oracle",      "dialect": "Oracle",      "protocol": "oracle",     "displayName": "Oracle"},
        {"code": 8,  "typeName": "hive",         "dialect": "Hive",        "protocol": "hive",       "displayName": "Hive"},
        {"code": 9,  "typeName": "clickhouse",  "dialect": "ClickHouse",  "protocol": "clickhouse", "displayName": "ClickHouse"},
    ])


# ===== 逻辑外键 (Logical Relations) =====
# 对齐 Java DatasourceController 的 logicalRelations 部分

@router.get("/{datasource_id}/logical-relations", summary="获取数据源的逻辑外键列表")
async def list_logical_relations(datasource_id: int, db: AsyncSession = Depends(get_db)):
    """获取指定数据源的所有逻辑外键关系 — GET /api/datasource/{id}/logical-relations"""
    datasource = await DatasourceService.get_datasource(db, datasource_id)
    if not datasource:
        raise HTTPException(status_code=404, detail="Datasource not found")
    items = await LogicalRelationService.list_by_datasource(db, datasource_id)
    return ApiResponse.ok(data=[item.model_dump(by_alias=True) for item in items])


@router.post("/{datasource_id}/logical-relations", status_code=201, summary="创建逻辑外键")
async def create_logical_relation(datasource_id: int, dto: LogicalRelationCreate, db: AsyncSession = Depends(get_db)):
    """创建逻辑外键关系 — POST /api/datasource/{id}/logical-relations"""
    datasource = await DatasourceService.get_datasource(db, datasource_id)
    if not datasource:
        raise HTTPException(status_code=404, detail="Datasource not found")
    item = await LogicalRelationService.create(db, datasource_id, dto)
    return ApiResponse.ok(data=item.model_dump(by_alias=True), message="创建成功")


@router.put("/{datasource_id}/logical-relations/{relation_id}", summary="更新逻辑外键")
async def update_logical_relation(datasource_id: int, relation_id: int, dto: LogicalRelationUpdate, db: AsyncSession = Depends(get_db)):
    """更新逻辑外键关系 — PUT /api/datasource/{id}/logical-relations/{relationId}"""
    datasource = await DatasourceService.get_datasource(db, datasource_id)
    if not datasource:
        raise HTTPException(status_code=404, detail="Datasource not found")
    item = await LogicalRelationService.update(db, relation_id, dto)
    if not item:
        raise HTTPException(status_code=404, detail="Logical relation not found")
    return ApiResponse.ok(data=item.model_dump(by_alias=True), message="更新成功")


@router.delete("/{datasource_id}/logical-relations/{relation_id}", summary="删除逻辑外键")
async def delete_logical_relation(datasource_id: int, relation_id: int, db: AsyncSession = Depends(get_db)):
    """软删除逻辑外键关系 — DELETE /api/datasource/{id}/logical-relations/{relationId}"""
    datasource = await DatasourceService.get_datasource(db, datasource_id)
    if not datasource:
        raise HTTPException(status_code=404, detail="Datasource not found")
    deleted = await LogicalRelationService.delete(db, relation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Logical relation not found")
    return ApiResponse.ok(message="删除成功")


@router.put("/{datasource_id}/logical-relations", summary="批量保存逻辑外键")
async def batch_save_logical_relations(datasource_id: int, relations: list[LogicalRelationCreate], db: AsyncSession = Depends(get_db)):
    """批量替换数据源的所有逻辑外键 — PUT /api/datasource/{id}/logical-relations (batch)"""
    datasource = await DatasourceService.get_datasource(db, datasource_id)
    if not datasource:
        raise HTTPException(status_code=404, detail="Datasource not found")
    items = await LogicalRelationService.batch_save(db, datasource_id, relations)
    return ApiResponse.ok(data=[item.model_dump(by_alias=True) for item in items], message="批量保存成功")


@router.get("/{datasource_id}", summary="获取数据源详情")
async def get_datasource(datasource_id: int, db: AsyncSession = Depends(get_db)):
    """根据 ID 获取数据源详情"""
    datasource = await DatasourceService.get_datasource(db, datasource_id)
    if not datasource:
        raise HTTPException(status_code=404, detail="Datasource not found")
    return ApiResponse.ok(data=datasource)


@router.put("/{datasource_id}", summary="更新数据源")
async def update_datasource(datasource_id: int, datasource_data: DatasourceUpdate, db: AsyncSession = Depends(get_db)):
    """更新数据源信息"""
    datasource = await DatasourceService.update_datasource(db, datasource_id, datasource_data)
    if not datasource:
        raise HTTPException(status_code=404, detail="Datasource not found")
    return ApiResponse.ok(data=datasource)


@router.delete("/{datasource_id}", status_code=204, summary="删除数据源")
async def delete_datasource(datasource_id: int, db: AsyncSession = Depends(get_db)):
    """删除数据源"""
    success = await DatasourceService.delete_datasource(db, datasource_id)
    if not success:
        raise HTTPException(status_code=404, detail="Datasource not found")
    return None


@router.post("/{datasource_id}/test", summary="测试数据源连接")
async def test_datasource(datasource_id: int, db: AsyncSession = Depends(get_db)):
    """测试数据源连接是否正常 — 对齐 Java POST /api/datasource/{id}/test"""
    success, message = await DatasourceService.test_connection(db, datasource_id)
    return ApiResponse.ok(data=success, message=message)


@router.get("/{datasource_id}/tables", summary="获取数据源的表列表")
async def list_tables(datasource_id: int, db: AsyncSession = Depends(get_db)):
    """获取指定数据源的所有表"""
    datasource = await DatasourceService.get_datasource(db, datasource_id)
    if not datasource:
        raise HTTPException(status_code=404, detail="Datasource not found")
    schema = await SchemaService.get_database_schema(datasource)
    return ApiResponse.ok(data=[{"name": table["name"], "comment": table.get("comment", "")} for table in schema["tables"]])


@router.get("/{datasource_id}/tables/{table_name}/columns", summary="获取表的字段列表")
async def list_columns(datasource_id: int, table_name: str, db: AsyncSession = Depends(get_db)):
    """获取指定表的所有字段"""
    datasource = await DatasourceService.get_datasource(db, datasource_id)
    if not datasource:
        raise HTTPException(status_code=404, detail="Datasource not found")
    schema = await SchemaService.get_database_schema(datasource, [table_name])
    if not schema["tables"]:
        raise HTTPException(status_code=404, detail="Table not found")
    return ApiResponse.ok(data=schema["tables"][0].get("columns", []))
