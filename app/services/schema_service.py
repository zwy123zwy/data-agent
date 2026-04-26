"""
数据库 Schema 服务
用于获取数据库表结构、字段信息等元数据
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
