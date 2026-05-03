"""
数据库 Schema 服务 — 连接用户数据库读取元数据 (information_schema)

【在系统中的地位】
  本服务是整个 Text-to-SQL 管道的数据基础。它实际连接到用户配置的
  数据库 (MySQL/PostgreSQL/SQLite)，读取表结构、字段、外键等元数据，
  将其格式化为 LLM 能理解的 DDL 文本。

【模块连接】
  上游 (谁调用 SchemaService):
    - workflows/nodes/schema_recall.py → 工作流中调用，获取 DDL 给 SQL 生成
    - api/schema_controller.py        → 前端手动查看数据库 Schema

  被依赖:
    - core/datasource_handler.py → 数据库类型适配器 (MySQL/PostgreSQL/SQLite)
      get_handler(type) 返回对应 Handler，提供 get_tables/get_columns/get_foreign_keys

  数据流:
    Datasource (连接信息) → create_async_engine → connect → information_schema 查询
    → raw columns/tables → 格式化 → DDL 文本 → LLM prompt

  Java 对应:
    SchemaService ≈ SchemaRecallNode.java + SchemaService.java (合并)

【DDL 格式说明】
  生成的 DDL 不是 SQL 标准的 CREATE TABLE 语句，而是"描述性 DDL"——
  更适合 LLM 理解的表格形式:
    表名: users
    说明: 用户表
    字段:
      - id (INT) [主键] - 用户ID
      - name (VARCHAR) - 用户名
  这种格式 LLM 能高效解析，用于生成准确的 SQL。
"""
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncConnection
from ..core.datasource_handler import get_handler
from ..models.datasource import Datasource
import logging

logger = logging.getLogger(__name__)


class SchemaService:
    """Schema 服务"""

    @staticmethod
    async def get_database_schema(datasource: Datasource, table_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        获取数据库 Schema

        Args:
            datasource: 数据源对象
            table_names: 指定要获取的表名列表，如果为 None 则获取所有表

        Returns:
            包含数据库结构的字典
        """
        handler = get_handler(datasource.type)
        if not handler:
            raise ValueError(f"不支持的数据库类型: {datasource.type}")

        # 构建连接 URL
        connection_url = handler.build_connection_url(datasource)

        # 创建异步引擎
        engine = create_async_engine(connection_url, echo=False)

        try:
            async with engine.connect() as conn:
                # 获取所有表
                all_tables = await handler.get_tables(conn, datasource.database)

                # 如果指定了表名，则过滤
                if table_names:
                    all_tables = [t for t in all_tables if t["name"] in table_names]

                # 获取每个表的详细信息
                tables_with_details = []
                for table in all_tables:
                    table_name = table["name"]

                    # 获取字段信息
                    columns = await handler.get_columns(conn, datasource.database, table_name)

                    # 获取外键信息（如果支持）
                    foreign_keys = await handler.get_foreign_keys(conn, datasource.database, table_name)

                    tables_with_details.append({
                        "name": table_name,
                        "comment": table.get("comment", ""),
                        "columns": columns,
                        "foreign_keys": foreign_keys
                    })

                return {
                    "database": datasource.database,
                    "type": datasource.type,
                    "tables": tables_with_details
                }
        finally:
            await engine.dispose()

    @staticmethod
    async def get_table_ddl(datasource: Datasource, table_name: str) -> str:
        """
        生成表的 DDL 描述（用于 LLM）

        Args:
            datasource: 数据源对象
            table_name: 表名

        Returns:
            表的 DDL 描述文本
        """
        schema = await SchemaService.get_database_schema(datasource, [table_name])

        if not schema["tables"]:
            return f"表 {table_name} 不存在"

        table = schema["tables"][0]

        # 构建 DDL 描述
        ddl_lines = [
            f"表名: {table['name']}",
        ]

        if table.get("comment"):
            ddl_lines.append(f"说明: {table['comment']}")

        ddl_lines.append("\n字段:")

        for col in table["columns"]:
            col_desc = f"  - {col['name']} ({col['type']})"

            if col.get("is_primary_key"):
                col_desc += " [主键]"

            if not col.get("nullable"):
                col_desc += " [非空]"

            if col.get("comment"):
                col_desc += f" - {col['comment']}"

            ddl_lines.append(col_desc)

        # 添加外键信息
        if table.get("foreign_keys"):
            ddl_lines.append("\n外键:")
            for fk in table["foreign_keys"]:
                ddl_lines.append(
                    f"  - {fk['column_name']} -> {fk['referenced_table']}.{fk['referenced_column']}"
                )

        return "\n".join(ddl_lines)

    @staticmethod
    async def get_database_ddl(datasource: Datasource, table_names: Optional[List[str]] = None) -> str:
        """
        生成数据库的完整 DDL 描述（用于 LLM）

        Args:
            datasource: 数据源对象
            table_names: 指定要获取的表名列表，如果为 None 则获取所有表

        Returns:
            数据库的 DDL 描述文本
        """
        schema = await SchemaService.get_database_schema(datasource, table_names)

        ddl_lines = [
            f"数据库: {schema['database']}",
            f"类型: {schema['type']}",
            f"\n共 {len(schema['tables'])} 张表:\n"
        ]

        for table in schema["tables"]:
            ddl_lines.append("=" * 60)
            ddl_lines.append(f"表名: {table['name']}")

            if table.get("comment"):
                ddl_lines.append(f"说明: {table['comment']}")

            ddl_lines.append("\n字段:")

            for col in table["columns"]:
                col_desc = f"  - {col['name']} ({col['type']})"

                if col.get("is_primary_key"):
                    col_desc += " [主键]"

                if not col.get("nullable"):
                    col_desc += " [非空]"

                if col.get("comment"):
                    col_desc += f" - {col['comment']}"

                ddl_lines.append(col_desc)

            # 添加外键信息
            if table.get("foreign_keys"):
                ddl_lines.append("\n外键:")
                for fk in table["foreign_keys"]:
                    ddl_lines.append(
                        f"  - {fk['column_name']} -> {fk['referenced_table']}.{fk['referenced_column']}"
                    )

            ddl_lines.append("")

        return "\n".join(ddl_lines)
