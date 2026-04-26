"""
Schema API
提供数据库结构查询接口
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..services.datasource_service import DatasourceService
from ..services.schema_service import SchemaService
from typing import Dict, Any, Optional, List

router = APIRouter(prefix="/api/schema", tags=["Schema"])


@router.get("/datasources/{datasource_id}")
async def get_datasource_schema(
    datasource_id: int,
    table_names: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    获取数据源的 Schema（结构化数据）

    Args:
        datasource_id: 数据源 ID
        table_names: 可选，逗号分隔的表名列表，如 "users,orders"

    Returns:
        数据库结构的 JSON 对象
    """
    # 获取数据源
    datasource = await DatasourceService.get_datasource(db, datasource_id)
    if not datasource:
        raise HTTPException(status_code=404, detail="数据源不存在")

    # 解析表名列表
    tables = None
    if table_names:
        tables = [t.strip() for t in table_names.split(",") if t.strip()]

    # 获取 Schema
    try:
        schema = await SchemaService.get_database_schema(datasource, tables)
        return schema
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 Schema 失败: {str(e)}")


@router.get("/datasources/{datasource_id}/ddl")
async def get_datasource_ddl(
    datasource_id: int,
    table_names: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """
    获取数据源的 DDL（文本格式，用于 LLM）

    Args:
        datasource_id: 数据源 ID
        table_names: 可选，逗号分隔的表名列表

    Returns:
        DDL 文本
    """
    # 获取数据源
    datasource = await DatasourceService.get_datasource(db, datasource_id)
    if not datasource:
        raise HTTPException(status_code=404, detail="数据源不存在")

    # 解析表名列表
    tables = None
    if table_names:
        tables = [t.strip() for t in table_names.split(",") if t.strip()]

    # 获取 DDL
    try:
        ddl = await SchemaService.get_database_ddl(datasource, tables)
        return {"ddl": ddl}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 DDL 失败: {str(e)}")


@router.get("/datasources/{datasource_id}/tables")
async def get_datasource_tables(
    datasource_id: int,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, List[Dict[str, str]]]:
    """
    获取数据源的所有表名

    Args:
        datasource_id: 数据源 ID

    Returns:
        表名列表
    """
    # 获取数据源
    datasource = await DatasourceService.get_datasource(db, datasource_id)
    if not datasource:
        raise HTTPException(status_code=404, detail="数据源不存在")

    # 获取表列表
    try:
        schema = await SchemaService.get_database_schema(datasource)
        tables = [
            {"name": table["name"], "comment": table.get("comment", "")}
            for table in schema["tables"]
        ]
        return {"tables": tables}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取表列表失败: {str(e)}")


@router.get("/datasources/{datasource_id}/tables/{table_name}")
async def get_table_schema(
    datasource_id: int,
    table_name: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    获取指定表的详细结构

    Args:
        datasource_id: 数据源 ID
        table_name: 表名

    Returns:
        表结构详情
    """
    # 获取数据源
    datasource = await DatasourceService.get_datasource(db, datasource_id)
    if not datasource:
        raise HTTPException(status_code=404, detail="数据源不存在")

    # 获取表结构
    try:
        schema = await SchemaService.get_database_schema(datasource, [table_name])

        if not schema["tables"]:
            raise HTTPException(status_code=404, detail=f"表 {table_name} 不存在")

        return schema["tables"][0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取表结构失败: {str(e)}")


@router.get("/datasources/{datasource_id}/tables/{table_name}/ddl")
async def get_table_ddl(
    datasource_id: int,
    table_name: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """
    获取指定表的 DDL（文本格式）

    Args:
        datasource_id: 数据源 ID
        table_name: 表名

    Returns:
        DDL 文本
    """
    # 获取数据源
    datasource = await DatasourceService.get_datasource(db, datasource_id)
    if not datasource:
        raise HTTPException(status_code=404, detail="数据源不存在")

    # 获取表 DDL
    try:
        ddl = await SchemaService.get_table_ddl(datasource, table_name)
        return {"ddl": ddl}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取表 DDL 失败: {str(e)}")
