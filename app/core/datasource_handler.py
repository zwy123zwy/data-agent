"""
数据库类型处理器 — 策略模式适配不同数据库

对齐 Java DatasourceTypeHandler + DBConnectionPool + BizDataSourceTypeEnum

【在系统中的地位】
  不同数据库 (MySQL/PostgreSQL/SQLite/Oracle/SQLServer/Dameng/Hive/ClickHouse)
  的连接测试、URL 构建、Schema 查询语法各不相同。
  本文件使用策略模式，每种数据库一个 Handler，统一接口隐藏差异。

【模块连接】
  上游 (谁调用 Handler):
    - services/datasource_service.py → test_connection() 通过 handler.ping()
    - services/schema_service.py     → 通过 get_handler(type) 获取对应处理器
      - build_connection_url() → 构建 SQLAlchemy 连接 URL
      - get_tables()           → 查询 information_schema 获取表列表
      - get_columns()          → 查询 information_schema 获取字段信息

【扩展新数据库】
  1. 继承 DatasourceTypeHandler
  2. 实现 type_name(), build_connection_url(), get_tables(), get_columns(), ping()
  3. 调用 register_handler() 注册
  4. 前端 datasource/types 列表自动包含新类型
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine


class DatasourceTypeHandler(ABC):
    """数据库类型处理器接口 — 对齐 Java DatasourceTypeHandler + DBConnectionPool"""

    # ═══════════════════════════════════════════════════════════════
    # 元信息
    # ═══════════════════════════════════════════════════════════════

    @abstractmethod
    def type_name(self) -> str:
        """数据库类型名称 (如 mysql, postgresql) — 对齐 Java typeName()"""
        pass

    def dialect_type(self) -> str:
        """SQL 方言类型 — 对齐 Java dialectType()，用于 SQL 生成"""
        return self.type_name()

    def supports(self, db_type: str) -> bool:
        """是否支持该类型 — 对齐 Java supports()"""
        return self.type_name().lower() == db_type.lower()

    # ═══════════════════════════════════════════════════════════════
    # 连接 URL
    # ═══════════════════════════════════════════════════════════════

    def has_required_connection_fields(self, datasource) -> bool:
        """是否具备构建 URL 的必要字段"""
        return (
            datasource.host is not None
            and datasource.port is not None
            and datasource.database_name is not None
        )

    @abstractmethod
    def build_connection_url(self, datasource) -> str:
        """构建连接 URL — 对齐 Java buildConnectionUrl()"""
        pass

    def resolve_connection_url(self, datasource) -> str:
        """解析连接 URL (优先用已有 connection_url) — 对齐 Java resolveConnectionUrl()"""
        if datasource.connection_url:
            return datasource.connection_url
        return self.build_connection_url(datasource)

    def normalize_test_url(self, datasource, url: str) -> str:
        """测试连接前标准化 URL (如追加参数) — 对齐 Java normalizeTestUrl()"""
        return url

    # ═══════════════════════════════════════════════════════════════
    # Schema 提取
    # ═══════════════════════════════════════════════════════════════

    def extract_schema_name(self, datasource) -> str:
        """提取 Schema 名 — 对齐 Java extractSchemaName()"""
        return datasource.database_name

    # ═══════════════════════════════════════════════════════════════
    # 连接配置
    # ═══════════════════════════════════════════════════════════════

    def to_db_config(self, datasource) -> dict:
        """转换 Datasource → DB 配置字典 — 对齐 Java toDbConfig()"""
        return {
            "url": self.resolve_connection_url(datasource),
            "username": datasource.username or "",
            "password": datasource.password or "",
            "type": self.type_name(),
            "dialect": self.dialect_type(),
            "schema": self.extract_schema_name(datasource),
        }

    # ═══════════════════════════════════════════════════════════════
    # 连接测试 (ping)
    # ═══════════════════════════════════════════════════════════════

    async def ping(self, datasource) -> tuple[bool, str]:
        """测试数据库连接 — 对齐 Java DBConnectionPool.ping()

        Returns:
            (success: bool, message: str)
        """
        url = self.resolve_connection_url(datasource)
        url = self.normalize_test_url(datasource, url)

        try:
            engine = create_async_engine(url, echo=False)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            return True, f"{self.type_name().upper()} connection successful"
        except Exception as e:
            # 尝试清理引擎
            try:
                await engine.dispose()
            except Exception:
                pass
            return False, f"Connection failed: {str(e)}"

    # ═══════════════════════════════════════════════════════════════
    # Schema 查询 (各 DB 语法不同)
    # ═══════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════
# MySQL
# ═══════════════════════════════════════════════════════════════════

class MysqlTypeHandler(DatasourceTypeHandler):

    def type_name(self) -> str:
        return "mysql"

    def dialect_type(self) -> str:
        return "mysql"

    def build_connection_url(self, datasource) -> str:
        if not self.has_required_connection_fields(datasource):
            return datasource.connection_url or ""
        return (
            f"mysql+aiomysql://{datasource.username}:{datasource.password}"
            f"@{datasource.host}:{datasource.port}/{datasource.database_name}"
            f"?charset=utf8mb4"
        )

    def normalize_test_url(self, datasource, url: str) -> str:
        """MySQL 测试 URL 标准化 — 追加必要参数"""
        updated = url
        lower = updated.lower()
        if "connect_timeout" not in lower:
            updated = updated + ("&" if "?" in updated else "?") + "connect_timeout=5"
        return updated

    async def get_tables(self, conn: AsyncConnection, schema: str) -> List[Dict[str, Any]]:
        sql = """
        SELECT TABLE_NAME as name, TABLE_COMMENT as comment
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = :schema
        AND TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
        LIMIT 2000
        """
        result = await conn.execute(text(sql), {"schema": schema})
        return [{"name": row[0], "comment": row[1] or ""} for row in result]

    async def get_columns(self, conn: AsyncConnection, schema: str, table: str) -> List[Dict[str, Any]]:
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
        return [
            {"name": r[0], "type": r[1], "comment": r[2] or "",
             "is_primary_key": bool(r[3]), "nullable": bool(r[4]), "default_value": r[5]}
            for r in result
        ]

    async def get_foreign_keys(self, conn: AsyncConnection, schema: str, table: str) -> List[Dict[str, Any]]:
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
        return [
            {"name": r[0], "column_name": r[1], "referenced_table": r[2], "referenced_column": r[3]}
            for r in result
        ]


# ═══════════════════════════════════════════════════════════════════
# PostgreSQL
# ═══════════════════════════════════════════════════════════════════

class PostgresqlTypeHandler(DatasourceTypeHandler):

    def type_name(self) -> str:
        return "postgresql"

    def dialect_type(self) -> str:
        return "postgresql"

    def build_connection_url(self, datasource) -> str:
        if not self.has_required_connection_fields(datasource):
            return datasource.connection_url or ""
        # 支持 "database|schema" 格式
        db_name = datasource.database_name
        if db_name and "|" in db_name:
            db_name = db_name.split("|")[0]
        return (
            f"postgresql+asyncpg://{datasource.username}:{datasource.password}"
            f"@{datasource.host}:{datasource.port}/{db_name}"
        )

    def extract_schema_name(self, datasource) -> str:
        db_name = datasource.database_name
        if db_name and "|" in db_name:
            parts = db_name.split("|")
            return parts[1] if len(parts) > 1 else parts[0]
        return db_name

    async def ping(self, datasource) -> tuple[bool, str]:
        """PostgreSQL ping — 对齐 Java: 额外检查 schema 是否存在"""
        url = self.resolve_connection_url(datasource)
        url = self.normalize_test_url(datasource, url)
        try:
            engine = create_async_engine(url, echo=False)
            async with engine.connect() as conn:
                # 检查 schema 是否存在
                schema = self.extract_schema_name(datasource)
                if schema:
                    result = await conn.execute(
                        text("SELECT count(*) FROM information_schema.schemata WHERE schema_name = :schema"),
                        {"schema": schema},
                    )
                    count = result.scalar()
                    if count == 0:
                        await engine.dispose()
                        return False, f"Schema '{schema}' does not exist"
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            return True, "PostgreSQL connection successful"
        except Exception as e:
            try:
                await engine.dispose()
            except Exception:
                pass
            return False, f"Connection failed: {str(e)}"

    async def get_tables(self, conn: AsyncConnection, schema: str) -> List[Dict[str, Any]]:
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
        return [{"name": r[0], "comment": r[1] or ""} for r in result]

    async def get_columns(self, conn: AsyncConnection, schema: str, table: str) -> List[Dict[str, Any]]:
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
        return [
            {"name": r[0], "type": r[1], "comment": r[2] or "",
             "is_primary_key": bool(r[3]), "nullable": bool(r[4]), "default_value": r[5]}
            for r in result
        ]


# ═══════════════════════════════════════════════════════════════════
# SQLite
# ═══════════════════════════════════════════════════════════════════

class SqliteTypeHandler(DatasourceTypeHandler):

    def type_name(self) -> str:
        return "sqlite"

    def dialect_type(self) -> str:
        return "sqlite"

    def has_required_connection_fields(self, datasource) -> bool:
        return bool(datasource.connection_url or datasource.database_name)

    def build_connection_url(self, datasource) -> str:
        return datasource.connection_url or f"sqlite+aiosqlite:///{datasource.database_name}"

    async def get_tables(self, conn: AsyncConnection, schema: str) -> List[Dict[str, Any]]:
        sql = """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
        AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
        result = await conn.execute(text(sql))
        return [{"name": r[0], "comment": ""} for r in result]

    async def get_columns(self, conn: AsyncConnection, schema: str, table: str) -> List[Dict[str, Any]]:
        sql = f"PRAGMA table_info({table})"
        result = await conn.execute(text(sql))
        return [
            {"name": r[1], "type": r[2], "comment": "",
             "is_primary_key": bool(r[5]), "nullable": not bool(r[3]), "default_value": r[4]}
            for r in result
        ]


# ═══════════════════════════════════════════════════════════════════
# Oracle
# ═══════════════════════════════════════════════════════════════════

class OracleTypeHandler(DatasourceTypeHandler):

    def type_name(self) -> str:
        return "oracle"

    def dialect_type(self) -> str:
        return "oracle"

    def build_connection_url(self, datasource) -> str:
        if not self.has_required_connection_fields(datasource):
            return datasource.connection_url or ""
        return (
            f"oracle+oracledb://{datasource.username}:{datasource.password}"
            f"@{datasource.host}:{datasource.port}/?service_name={datasource.database_name}"
        )

    async def ping(self, datasource) -> tuple[bool, str]:
        url = self.resolve_connection_url(datasource)
        try:
            engine = create_async_engine(url, echo=False)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1 FROM DUAL"))
            await engine.dispose()
            return True, "Oracle connection successful"
        except Exception as e:
            try:
                await engine.dispose()
            except Exception:
                pass
            return False, f"Connection failed: {str(e)}"

    async def get_tables(self, conn: AsyncConnection, schema: str) -> List[Dict[str, Any]]:
        sql = """
        SELECT TABLE_NAME as name, COMMENTS as comment
        FROM ALL_TAB_COMMENTS
        WHERE OWNER = UPPER(:schema)
        AND TABLE_TYPE = 'TABLE'
        ORDER BY TABLE_NAME
        """
        result = await conn.execute(text(sql), {"schema": schema})
        return [{"name": r[0], "comment": r[1] or ""} for r in result]

    async def get_columns(self, conn: AsyncConnection, schema: str, table: str) -> List[Dict[str, Any]]:
        sql = """
        SELECT
            c.COLUMN_NAME as name,
            c.DATA_TYPE as type,
            COALESCE(cc.COMMENTS, '') as comment,
            CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END as is_primary_key,
            CASE WHEN c.NULLABLE = 'Y' THEN 1 ELSE 0 END as nullable,
            c.DATA_DEFAULT as default_value
        FROM ALL_TAB_COLUMNS c
        LEFT JOIN ALL_COL_COMMENTS cc
            ON cc.OWNER = c.OWNER AND cc.TABLE_NAME = c.TABLE_NAME AND cc.COLUMN_NAME = c.COLUMN_NAME
        LEFT JOIN (
            SELECT cols.COLUMN_NAME
            FROM ALL_CONSTRAINTS cons
            JOIN ALL_CONS_COLUMNS cols ON cons.CONSTRAINT_NAME = cols.CONSTRAINT_NAME
            WHERE cons.CONSTRAINT_TYPE = 'P'
            AND cons.OWNER = UPPER(:schema)
            AND cons.TABLE_NAME = UPPER(:table)
        ) pk ON pk.COLUMN_NAME = c.COLUMN_NAME
        WHERE c.OWNER = UPPER(:schema)
        AND c.TABLE_NAME = UPPER(:table)
        ORDER BY c.COLUMN_ID
        """
        result = await conn.execute(text(sql), {"schema": schema, "table": table})
        return [
            {"name": r[0], "type": r[1], "comment": r[2] or "",
             "is_primary_key": bool(r[3]), "nullable": bool(r[4]), "default_value": r[5]}
            for r in result
        ]


# ═══════════════════════════════════════════════════════════════════
# SQL Server
# ═══════════════════════════════════════════════════════════════════

class SqlServerTypeHandler(DatasourceTypeHandler):

    def type_name(self) -> str:
        return "mssql"

    def dialect_type(self) -> str:
        return "mssql"

    def build_connection_url(self, datasource) -> str:
        if not self.has_required_connection_fields(datasource):
            return datasource.connection_url or ""
        return (
            f"mssql+aioodbc://{datasource.username}:{datasource.password}"
            f"@{datasource.host}:{datasource.port}/{datasource.database_name}"
            f"?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
        )

    async def ping(self, datasource) -> tuple[bool, str]:
        url = self.resolve_connection_url(datasource)
        try:
            engine = create_async_engine(url, echo=False)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            return True, "SQL Server connection successful"
        except Exception as e:
            try:
                await engine.dispose()
            except Exception:
                pass
            return False, f"Connection failed: {str(e)}"

    async def get_tables(self, conn: AsyncConnection, schema: str) -> List[Dict[str, Any]]:
        sql = """
        SELECT TABLE_NAME as name, ISNULL(CAST(ep.value AS NVARCHAR(MAX)), '') as comment
        FROM INFORMATION_SCHEMA.TABLES t
        LEFT JOIN sys.extended_properties ep
            ON ep.major_id = OBJECT_ID(t.TABLE_NAME)
            AND ep.minor_id = 0
            AND ep.name = 'MS_Description'
        WHERE TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
        """
        result = await conn.execute(text(sql))
        return [{"name": r[0], "comment": r[1] or ""} for r in result]

    async def get_columns(self, conn: AsyncConnection, schema: str, table: str) -> List[Dict[str, Any]]:
        sql = """
        SELECT
            c.COLUMN_NAME as name,
            c.DATA_TYPE as type,
            ISNULL(CAST(ep.value AS NVARCHAR(MAX)), '') as comment,
            CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END as is_primary_key,
            CASE WHEN c.IS_NULLABLE = 'YES' THEN 1 ELSE 0 END as nullable,
            c.COLUMN_DEFAULT as default_value
        FROM INFORMATION_SCHEMA.COLUMNS c
        LEFT JOIN sys.extended_properties ep
            ON ep.major_id = OBJECT_ID(c.TABLE_NAME)
            AND ep.minor_id = c.ORDINAL_POSITION
            AND ep.name = 'MS_Description'
        LEFT JOIN (
            SELECT ku.COLUMN_NAME
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
            WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
            AND tc.TABLE_NAME = :table
        ) pk ON pk.COLUMN_NAME = c.COLUMN_NAME
        WHERE c.TABLE_NAME = :table
        ORDER BY c.ORDINAL_POSITION
        """
        result = await conn.execute(text(sql), {"table": table})
        return [
            {"name": r[0], "type": r[1], "comment": r[2] or "",
             "is_primary_key": bool(r[3]), "nullable": bool(r[4]), "default_value": r[5]}
            for r in result
        ]


# ═══════════════════════════════════════════════════════════════════
# ClickHouse
# ═══════════════════════════════════════════════════════════════════

class ClickHouseTypeHandler(DatasourceTypeHandler):

    def type_name(self) -> str:
        return "clickhouse"

    def dialect_type(self) -> str:
        return "clickhouse"

    def build_connection_url(self, datasource) -> str:
        if not self.has_required_connection_fields(datasource):
            return datasource.connection_url or ""
        return (
            f"clickhouse+asynch://{datasource.username}:{datasource.password}"
            f"@{datasource.host}:{datasource.port}/{datasource.database_name}"
        )

    async def ping(self, datasource) -> tuple[bool, str]:
        url = self.resolve_connection_url(datasource)
        try:
            engine = create_async_engine(url, echo=False)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            return True, "ClickHouse connection successful"
        except Exception as e:
            try:
                await engine.dispose()
            except Exception:
                pass
            return False, f"Connection failed: {str(e)}"

    async def get_tables(self, conn: AsyncConnection, schema: str) -> List[Dict[str, Any]]:
        sql = """
        SELECT name, '' as comment
        FROM system.tables
        WHERE database = :schema
        ORDER BY name
        """
        result = await conn.execute(text(sql), {"schema": schema})
        return [{"name": r[0], "comment": r[1] or ""} for r in result]

    async def get_columns(self, conn: AsyncConnection, schema: str, table: str) -> List[Dict[str, Any]]:
        sql = """
        SELECT
            name,
            type,
            '' as comment,
            0 as is_primary_key,
            1 as nullable,
            '' as default_value
        FROM system.columns
        WHERE database = :schema
        AND table = :table
        ORDER BY position
        """
        result = await conn.execute(text(sql), {"schema": schema, "table": table})
        return [
            {"name": r[0], "type": r[1], "comment": r[2] or "",
             "is_primary_key": bool(r[3]), "nullable": bool(r[4]), "default_value": r[5]}
            for r in result
        ]


# ═══════════════════════════════════════════════════════════════════
# Dameng (达梦)
# ═══════════════════════════════════════════════════════════════════

class DamengTypeHandler(DatasourceTypeHandler):

    def type_name(self) -> str:
        return "dameng"

    def dialect_type(self) -> str:
        return "dameng"

    def build_connection_url(self, datasource) -> str:
        if not self.has_required_connection_fields(datasource):
            return datasource.connection_url or ""
        return (
            f"dm+dmPython://{datasource.username}:{datasource.password}"
            f"@{datasource.host}:{datasource.port}/{datasource.database_name}"
        )

    async def ping(self, datasource) -> tuple[bool, str]:
        url = self.resolve_connection_url(datasource)
        try:
            engine = create_async_engine(url, echo=False)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1 FROM DUAL"))
            await engine.dispose()
            return True, "Dameng connection successful"
        except Exception as e:
            try:
                await engine.dispose()
            except Exception:
                pass
            return False, f"Connection failed: {str(e)}"

    async def get_tables(self, conn: AsyncConnection, schema: str) -> List[Dict[str, Any]]:
        sql = """
        SELECT TABLE_NAME as name, COMMENTS as comment
        FROM ALL_TAB_COMMENTS
        WHERE OWNER = UPPER(:schema)
        AND TABLE_TYPE = 'TABLE'
        ORDER BY TABLE_NAME
        """
        result = await conn.execute(text(sql), {"schema": schema})
        return [{"name": r[0], "comment": r[1] or ""} for r in result]

    async def get_columns(self, conn: AsyncConnection, schema: str, table: str) -> List[Dict[str, Any]]:
        sql = """
        SELECT
            c.COLUMN_NAME as name,
            c.DATA_TYPE as type,
            COALESCE(cc.COMMENTS, '') as comment,
            CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END as is_primary_key,
            CASE WHEN c.NULLABLE = 'Y' THEN 1 ELSE 0 END as nullable,
            c.DATA_DEFAULT as default_value
        FROM ALL_TAB_COLUMNS c
        LEFT JOIN ALL_COL_COMMENTS cc
            ON cc.OWNER = c.OWNER AND cc.TABLE_NAME = c.TABLE_NAME AND cc.COLUMN_NAME = c.COLUMN_NAME
        LEFT JOIN (
            SELECT cols.COLUMN_NAME
            FROM ALL_CONSTRAINTS cons
            JOIN ALL_CONS_COLUMNS cols ON cons.CONSTRAINT_NAME = cols.CONSTRAINT_NAME
            WHERE cons.CONSTRAINT_TYPE = 'P'
            AND cons.OWNER = UPPER(:schema)
            AND cons.TABLE_NAME = UPPER(:table)
        ) pk ON pk.COLUMN_NAME = c.COLUMN_NAME
        WHERE c.OWNER = UPPER(:schema)
        AND c.TABLE_NAME = UPPER(:table)
        ORDER BY c.COLUMN_ID
        """
        result = await conn.execute(text(sql), {"schema": schema, "table": table})
        return [
            {"name": r[0], "type": r[1], "comment": r[2] or "",
             "is_primary_key": bool(r[3]), "nullable": bool(r[4]), "default_value": r[5]}
            for r in result
        ]


# ═══════════════════════════════════════════════════════════════════
# Hive
# ═══════════════════════════════════════════════════════════════════

class HiveTypeHandler(DatasourceTypeHandler):

    def type_name(self) -> str:
        return "hive"

    def dialect_type(self) -> str:
        return "hive"

    def build_connection_url(self, datasource) -> str:
        if not self.has_required_connection_fields(datasource):
            return datasource.connection_url or ""
        return (
            f"hive://{datasource.username}:{datasource.password}"
            f"@{datasource.host}:{datasource.port}/{datasource.database_name}"
        )

    async def ping(self, datasource) -> tuple[bool, str]:
        url = self.resolve_connection_url(datasource)
        try:
            engine = create_async_engine(url, echo=False)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            return True, "Hive connection successful"
        except Exception as e:
            try:
                await engine.dispose()
            except Exception:
                pass
            return False, f"Connection failed: {str(e)}"

    async def get_tables(self, conn: AsyncConnection, schema: str) -> List[Dict[str, Any]]:
        sql = """
        SHOW TABLES IN :schema
        """
        result = await conn.execute(text(f"SHOW TABLES IN {schema}"))
        return [{"name": r[0], "comment": ""} for r in result]

    async def get_columns(self, conn: AsyncConnection, schema: str, table: str) -> List[Dict[str, Any]]:
        sql = f"DESCRIBE {schema}.{table}"
        result = await conn.execute(text(sql))
        columns = []
        for r in result:
            columns.append({
                "name": r[0],
                "type": r[1],
                "comment": r[2] if len(r) > 2 and r[2] else "",
                "is_primary_key": False,
                "nullable": True,
                "default_value": None,
            })
        return columns


# ═══════════════════════════════════════════════════════════════════
# 类型处理器注册表 — 对齐 Java DatasourceTypeHandlerRegistry
# ═══════════════════════════════════════════════════════════════════

class DatasourceTypeHandlerRegistry:
    """数据源类型处理器注册表 — 对齐 Java DatasourceTypeHandlerRegistry"""

    def __init__(self):
        self._handlers: Dict[str, DatasourceTypeHandler] = {}

    def register(self, handler: DatasourceTypeHandler):
        """注册处理器 — 对齐 Java register()"""
        self._handlers[handler.type_name().lower()] = handler

    def is_registered(self, db_type: str) -> bool:
        """是否已注册 — 对齐 Java isRegistered()"""
        return db_type.lower() in self._handlers

    def get(self, db_type: str) -> Optional[DatasourceTypeHandler]:
        """获取处理器 (可能为空)"""
        return self._handlers.get(db_type.lower())

    def get_required(self, db_type: str) -> DatasourceTypeHandler:
        """获取处理器 (必须存在) — 对齐 Java getRequired()"""
        if not db_type:
            raise ValueError("Datasource type cannot be blank")
        handler = self._handlers.get(db_type.lower())
        if not handler:
            raise ValueError(f"Unsupported datasource type: {db_type}")
        return handler

    @property
    def supported_types(self) -> List[str]:
        """所有已注册的类型"""
        return list(self._handlers.keys())


# 全局注册表实例
_registry = DatasourceTypeHandlerRegistry()

# 注册所有内置处理器
_registry.register(MysqlTypeHandler())
_registry.register(PostgresqlTypeHandler())
_registry.register(SqliteTypeHandler())
_registry.register(OracleTypeHandler())
_registry.register(SqlServerTypeHandler())
_registry.register(ClickHouseTypeHandler())
_registry.register(DamengTypeHandler())
_registry.register(HiveTypeHandler())


def get_handler(db_type: str) -> Optional[DatasourceTypeHandler]:
    """获取数据库类型处理器"""
    return _registry.get(db_type)


def get_handler_registry() -> DatasourceTypeHandlerRegistry:
    """获取处理器注册表"""
    return _registry


def register_handler(handler: DatasourceTypeHandler):
    """注册新的数据库类型处理器"""
    _registry.register(handler)
