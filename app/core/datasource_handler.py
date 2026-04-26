"""
数据库类型处理器基类和实现
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


class DatasourceTypeHandler(ABC):
    """数据库类型处理器接口"""

    @abstractmethod
    def type_name(self) -> str:
        """数据库类型名称"""
        pass

    @abstractmethod
    def build_connection_url(self, datasource) -> str:
        """构建连接 URL"""
        pass

    @abstractmethod
    async def get_tables(self, conn: AsyncConnection, schema: str) -> List[Dict[str, Any]]:
        """获取所有表"""
        pass

    @abstractmethod
    async def get_columns(self, conn: AsyncConnection, schema: str, table: str) -> List[Dict[str, Any]]:
        """获取表的所有字段"""
        pass

    async def get_foreign_keys(self, conn: AsyncConnection, schema: str, table: str) -> List[Dict[str, Any]]:
        """获取表的外键（可选实现）"""
        return []


class MysqlTypeHandler(DatasourceTypeHandler):
    """MySQL 类型处理器"""

    def type_name(self) -> str:
        return "mysql"

    def build_connection_url(self, datasource) -> str:
        """构建 MySQL 连接 URL"""
        return (
            f"mysql+aiomysql://{datasource.username}:{datasource.password}"
            f"@{datasource.host}:{datasource.port}/{datasource.database}"
            f"?charset=utf8mb4"
        )

    async def get_tables(self, conn: AsyncConnection, schema: str) -> List[Dict[str, Any]]:
        """获取所有表"""
        sql = """
        SELECT TABLE_NAME as name, TABLE_COMMENT as comment
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = :schema
        AND TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
        LIMIT 2000
        """
        result = await conn.execute(text(sql), {"schema": schema})
        tables = []
        for row in result:
            tables.append({
                "name": row[0],
                "comment": row[1] or ""
            })
        return tables

    async def get_columns(self, conn: AsyncConnection, schema: str, table: str) -> List[Dict[str, Any]]:
        """获取表的所有字段"""
        sql = """
        SELECT
            COLUMN_NAME as name,
            DATA_TYPE as type,
            COLUMN_COMMENT as comment,
            IF(COLUMN_KEY='PRI', TRUE, FALSE) as is_primary_key,
            IF(IS_NULLABLE='NO', FALSE, TRUE) as nullable,
            COLUMN_DEFAULT as default_value
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = :schema
        AND TABLE_NAME = :table
        ORDER BY ORDINAL_POSITION
        """
        result = await conn.execute(text(sql), {"schema": schema, "table": table})
        columns = []
        for row in result:
            columns.append({
                "name": row[0],
                "type": row[1],
                "comment": row[2] or "",
                "is_primary_key": bool(row[3]),
                "nullable": bool(row[4]),
                "default_value": row[5]
            })
        return columns

    async def get_foreign_keys(self, conn: AsyncConnection, schema: str, table: str) -> List[Dict[str, Any]]:
        """获取表的外键"""
        sql = """
        SELECT
            CONSTRAINT_NAME as name,
            COLUMN_NAME as column_name,
            REFERENCED_TABLE_NAME as referenced_table,
            REFERENCED_COLUMN_NAME as referenced_column
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = :schema
        AND TABLE_NAME = :table
        AND REFERENCED_TABLE_NAME IS NOT NULL
        """
        result = await conn.execute(text(sql), {"schema": schema, "table": table})
        foreign_keys = []
        for row in result:
            foreign_keys.append({
                "name": row[0],
                "column_name": row[1],
                "referenced_table": row[2],
                "referenced_column": row[3]
            })
        return foreign_keys


class SqliteTypeHandler(DatasourceTypeHandler):
    """SQLite 类型处理器"""

    def type_name(self) -> str:
        return "sqlite"

    def build_connection_url(self, datasource) -> str:
        """构建 SQLite 连接 URL"""
        return datasource.connection_url or f"sqlite+aiosqlite:///{datasource.database}"

    async def get_tables(self, conn: AsyncConnection, schema: str) -> List[Dict[str, Any]]:
        """获取所有表"""
        sql = """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
        AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
        result = await conn.execute(text(sql))
        tables = []
        for row in result:
            tables.append({
                "name": row[0],
                "comment": ""
            })
        return tables

    async def get_columns(self, conn: AsyncConnection, schema: str, table: str) -> List[Dict[str, Any]]:
        """获取表的所有字段"""
        sql = f"PRAGMA table_info({table})"
        result = await conn.execute(text(sql))
        columns = []
        for row in result:
            # SQLite PRAGMA table_info 返回: cid, name, type, notnull, dflt_value, pk
            columns.append({
                "name": row[1],
                "type": row[2],
                "comment": "",
                "is_primary_key": bool(row[5]),
                "nullable": not bool(row[3]),
                "default_value": row[4]
            })
        return columns


class PostgresqlTypeHandler(DatasourceTypeHandler):
    """PostgreSQL 类型处理器"""

    def type_name(self) -> str:
        return "postgresql"

    def build_connection_url(self, datasource) -> str:
        """构建 PostgreSQL 连接 URL"""
        return (
            f"postgresql+asyncpg://{datasource.username}:{datasource.password}"
            f"@{datasource.host}:{datasource.port}/{datasource.database}"
        )

    async def get_tables(self, conn: AsyncConnection, schema: str) -> List[Dict[str, Any]]:
        """获取所有表"""
        sql = """
        SELECT
            tb.table_name as name,
            COALESCE(d.description, '') as comment
        FROM information_schema.tables tb
        LEFT JOIN pg_catalog.pg_description d
            ON d.objoid = (tb.table_schema||'.'||tb.table_name)::regclass
        WHERE tb.table_schema = :schema
        AND tb.table_type = 'BASE TABLE'
        ORDER BY tb.table_name
        LIMIT 2000
        """
        result = await conn.execute(text(sql), {"schema": schema})
        tables = []
        for row in result:
            tables.append({
                "name": row[0],
                "comment": row[1] or ""
            })
        return tables

    async def get_columns(self, conn: AsyncConnection, schema: str, table: str) -> List[Dict[str, Any]]:
        """获取表的所有字段"""
        sql = """
        SELECT
            c.column_name as name,
            c.data_type as type,
            COALESCE(pgd.description, '') as comment,
            CASE WHEN pk.column_name IS NOT NULL THEN TRUE ELSE FALSE END as is_primary_key,
            CASE WHEN c.is_nullable = 'YES' THEN TRUE ELSE FALSE END as nullable,
            c.column_default as default_value
        FROM information_schema.columns c
        LEFT JOIN pg_catalog.pg_description pgd
            ON pgd.objoid = (c.table_schema||'.'||c.table_name)::regclass
            AND pgd.objsubid = c.ordinal_position
        LEFT JOIN (
            SELECT ku.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage ku
                ON tc.constraint_name = ku.constraint_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
            AND tc.table_schema = :schema
            AND tc.table_name = :table
        ) pk ON pk.column_name = c.column_name
        WHERE c.table_schema = :schema
        AND c.table_name = :table
        ORDER BY c.ordinal_position
        """
        result = await conn.execute(text(sql), {"schema": schema, "table": table})
        columns = []
        for row in result:
            columns.append({
                "name": row[0],
                "type": row[1],
                "comment": row[2] or "",
                "is_primary_key": bool(row[3]),
                "nullable": bool(row[4]),
                "default_value": row[5]
            })
        return columns


# 类型处理器注册表
_handlers: Dict[str, DatasourceTypeHandler] = {
    "mysql": MysqlTypeHandler(),
    "sqlite": SqliteTypeHandler(),
    "postgresql": PostgresqlTypeHandler(),
}


def get_handler(db_type: str) -> Optional[DatasourceTypeHandler]:
    """获取数据库类型处理器"""
    return _handlers.get(db_type.lower())


def register_handler(handler: DatasourceTypeHandler):
    """注册新的数据库类型处理器"""
    _handlers[handler.type_name().lower()] = handler
