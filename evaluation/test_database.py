"""
SQLite 测试数据库 — 用于评测 SQL 执行 (EX/VES)

【在系统中的地位】
  为评测系统提供独立的、可复现的 SQLite 数据库环境。
  不依赖外部 MySQL，评测完全自包含。

【模块连接】
  上游:
    - run_evaluation.py → 通过 TestDatabase 执行 gold_sql 和 gen_sql
    - metrics/sql_metrics.py → compute_execution_accuracy 需要 db executor

  下游:
    - sqlite3 (Python 标准库) → 实际的 SQLite 数据库文件

  数据来源:
    - datasets/business_demo/schema.sql  → DDL (自动转换为 SQLite 方言)
    - datasets/business_demo/seed_data.sql → INSERT (自动适配 SQLite)
"""
import sqlite3
import os
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class TestDatabase:
    """SQLite 测试数据库管理器

    为每条 test_case 的 gold_sql 和 generated_sql 提供执行环境。
    数据库文件存储在 evaluation/databases/ 目录下。
    """

    def __init__(self, dataset_name: str):
        self.dataset_name = dataset_name
        dataset_dir = Path(__file__).resolve().parent / "datasets" / dataset_name
        db_dir = Path(__file__).resolve().parent / "databases"
        db_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = db_dir / f"{dataset_name}.sqlite"
        self.schema_path = dataset_dir / "schema.sql"
        self.seed_path = dataset_dir / "seed_data.sql"

        self._initialized = False

    def _ensure_initialized(self):
        """延迟初始化：首次使用时创建数据库"""
        if self._initialized:
            return

        # 如果数据库已存在，先删除重建 (保证数据一致性)
        if self.db_path.exists():
            self.db_path.unlink()

        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA foreign_keys = ON")

        try:
            # 1. 执行 schema (MySQL DDL → SQLite DDL)
            if self.schema_path.exists():
                schema_sql = self.schema_path.read_text(encoding="utf-8")
                sqlite_schema = self._convert_mysql_ddl_to_sqlite(schema_sql)
                conn.executescript(sqlite_schema)

            # 2. 插入种子数据
            if self.seed_path.exists():
                seed_sql = self.seed_path.read_text(encoding="utf-8")
                sqlite_seed = self._convert_mysql_insert_to_sqlite(seed_sql)
                conn.executescript(sqlite_seed)

            conn.commit()
            self._initialized = True
            logger.info(f"[TestDB] Initialized SQLite database: {self.db_path}")
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Failed to initialize test database: {e}")
        finally:
            conn.close()

    # ========================================================================
    # DDL 转换: MySQL → SQLite
    # ========================================================================

    def _convert_mysql_ddl_to_sqlite(self, sql: str) -> str:
        """将 MySQL DDL 转换为 SQLite DDL

        差异:
          - AUTO_INCREMENT → AUTOINCREMENT
          - COMMENT '...' → 移除
          - DECIMAL(p,s) → REAL
          - DATETIME → TEXT
          - INT → INTEGER
          - ENGINE/CHARSET → 移除
          - FOREIGN KEY → 保留 (SQLite 通过 PRAGMA foreign_keys = ON 支持)
        """
        # 移除 MySQL 特有的 COMMENT
        sql = re.sub(r"\s+COMMENT\s+'[^']*'", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r'\s+COMMENT\s+"[^"]*"', "", sql, flags=re.IGNORECASE)

        # 移除 ENGINE=xxx CHARSET=xxx 等
        sql = re.sub(r'\s+ENGINE\s*=\s*\w+', "", sql, flags=re.IGNORECASE)
        sql = re.sub(r'\s+DEFAULT\s+CHARSET\s*=\s*\w+', "", sql, flags=re.IGNORECASE)
        sql = re.sub(r'\s+COLLATE\s*=\s*\w+', "", sql, flags=re.IGNORECASE)

        # 类型转换
        sql = re.sub(r'\bAUTO_INCREMENT\b', 'AUTOINCREMENT', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bDECIMAL\s*\(\s*\d+\s*,\s*\d+\s*\)', 'REAL', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bDATETIME\b', 'TEXT', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bINT\b(?!EGER)', 'INTEGER', sql, flags=re.IGNORECASE)

        # 移除 ON UPDATE CURRENT_TIMESTAMP (SQLite 不支持)
        sql = re.sub(
            r'\bON\s+UPDATE\s+CURRENT_TIMESTAMP\b',
            '',
            sql,
            flags=re.IGNORECASE
        )

        # 移除 UNIQUE 后面的索引定义语法 (保留 UNIQUE 关键字本身)
        # SQLite 支持 UNIQUE，但语法略有不同

        return sql

    # ========================================================================
    # INSERT 转换
    # ========================================================================

    def _convert_mysql_insert_to_sqlite(self, sql: str) -> str:
        """将 MySQL INSERT 转换为 SQLite 兼容格式

        主要处理:
          - 日期时间字符串保持原样 (SQLite TEXT 类型)
          - 转义字符适配
        """
        # MySQL DDL 中的 ON UPDATE CURRENT_TIMESTAMP 已在 DDL 转换中移除
        # INSERT 语句通常直接兼容
        return sql

    # ========================================================================
    # SQL 方言转换: MySQL → SQLite (运行时转换 generated SQL)
    # ========================================================================

    @staticmethod
    def _find_matching_paren(text: str, open_pos: int) -> int:
        """找到与 open_pos 处的 '(' 匹配的 ')' 位置

        例: text="func(a, b)", open_pos=4 → 返回 10 (b后面的))
        """
        depth = 0
        for i in range(open_pos, len(text)):
            if text[i] == '(':
                depth += 1
            elif text[i] == ')':
                depth -= 1
                if depth == 0:
                    return i
        return -1

    @classmethod
    def _convert_function(cls, sql: str, func_name: str, converter) -> str:
        """转换 SQL 函数调用 — 正确处理嵌套括号

        找到所有 func_name(...) 调用，提取参数（处理括号深度），
        对每个匹配调用 converter(match_start, match_end, args_str)。

        Args:
            sql: 原始 SQL
            func_name: 函数名 (如 "DATEDIFF")
            converter: callable(start_pos, end_pos, args_str) → replacement_str
        """
        pattern = re.compile(r'\b' + re.escape(func_name) + r'\s*\(', re.IGNORECASE)
        result = list(sql)
        # 从后往前替换，避免位置偏移
        replacements = []

        for m in pattern.finditer(sql):
            start = m.start()
            paren_open = m.end() - 1  # position of '('
            paren_close = cls._find_matching_paren(sql, paren_open)
            if paren_close == -1:
                continue
            args = sql[paren_open + 1:paren_close]
            repl = converter(args)
            replacements.append((start, paren_close + 1, repl))

        # 从后往前替换
        for start, end, repl in reversed(replacements):
            sql = sql[:start] + repl + sql[end:]

        return sql

    def convert_mysql_to_sqlite(self, sql: str) -> str:
        """运行时将 MySQL 方言 SQL 转换为 SQLite 方言"""
        sql = sql.strip().rstrip(";")

        # ── NOW() → datetime('now') (先转换，后续 DATEDIFF 等会匹配 datetime('now')) ──
        sql = re.sub(r'\bNOW\s*\(\s*\)', "datetime('now')", sql, flags=re.IGNORECASE)

        # ── DATE_FORMAT(date, fmt) ──
        def convert_date_format(args: str) -> str:
            parts = args.split(',', 1)
            if len(parts) == 2:
                date_expr = parts[0].strip()
                fmt = parts[1].strip().strip("'\"")
                return f"strftime('{fmt}', {date_expr})"
            return args

        sql = self._convert_function(sql, "DATE_FORMAT", convert_date_format)

        # ── DATE_ADD(date, INTERVAL N DAY) ──
        def convert_date_add(args: str) -> str:
            parts = args.split(',', 1)
            if len(parts) == 2:
                date_expr = parts[0].strip()
                m = re.search(r'INTERVAL\s+(\d+)\s+DAY', parts[1], re.IGNORECASE)
                if m:
                    return f"datetime({date_expr}, '+{m.group(1)} days')"
            return args

        sql = self._convert_function(sql, "DATE_ADD", convert_date_add)

        # ── DATE_SUB(expr, INTERVAL N DAY) ──
        def convert_date_sub(args: str) -> str:
            parts = args.split(',', 1)
            if len(parts) == 2:
                date_expr = parts[0].strip()
                m = re.search(r'INTERVAL\s+(\d+)\s+DAY', parts[1], re.IGNORECASE)
                if m:
                    return f"datetime({date_expr}, '-{m.group(1)} days')"
            return args

        sql = self._convert_function(sql, "DATE_SUB", convert_date_sub)

        # ── DATEDIFF(expr1, expr2) ──
        def convert_datediff(args: str) -> str:
            parts = args.split(',', 1)
            if len(parts) == 2:
                d1, d2 = parts[0].strip(), parts[1].strip()
                return f"CAST(julianday({d1}) - julianday({d2}) AS INTEGER)"
            return args

        sql = self._convert_function(sql, "DATEDIFF", convert_datediff)

        return sql

    # ========================================================================
    # SQL 执行接口
    # ========================================================================

    def execute_sql(self, sql: str) -> Tuple[List[Dict[str, Any]], float]:
        """执行 SQL 并返回 (结果集, 执行时间_ms)

        Args:
            sql: 原始 SQL (MySQL 方言，内部自动转换为 SQLite)

        Returns:
            (result_rows, execution_time_ms)
            result_rows: List[Dict] — 每行是一个 {列名: 值} 字典
        """
        self._ensure_initialized()

        sqlite_sql = self.convert_mysql_to_sqlite(sql)

        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row  # 让结果可以通过列名访问

        try:
            start = time.perf_counter()
            cursor = conn.execute(sqlite_sql)
            rows = cursor.fetchall()
            elapsed_ms = (time.perf_counter() - start) * 1000

            # 转换为 List[Dict]
            result = [dict(row) for row in rows]
            return result, elapsed_ms
        except Exception as e:
            raise RuntimeError(f"SQL execution failed: {e}\nSQL: {sqlite_sql[:200]}")
        finally:
            conn.close()

    def execute_sql_safe(self, sql: str) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str], float]:
        """安全执行 SQL — 不抛异常

        Returns:
            (result_rows_or_None, error_message_or_None, execution_time_ms)
        """
        try:
            rows, elapsed = self.execute_sql(sql)
            return rows, None, elapsed
        except Exception as e:
            return None, str(e), 0

    # ========================================================================
    # 数据库管理
    # ========================================================================

    def reset(self):
        """重置数据库（删除重建）"""
        if self.db_path.exists():
            self.db_path.unlink()
        self._initialized = False
        self._ensure_initialized()

    def close(self):
        """清理数据库文件"""
        if self.db_path.exists():
            self.db_path.unlink()
            logger.info(f"[TestDB] Removed: {self.db_path}")

    def table_names(self) -> List[str]:
        """获取所有表名"""
        self._ensure_initialized()
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def row_count(self, table: str) -> int:
        """获取表的行数"""
        self._ensure_initialized()
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
            return cursor.fetchone()[0]
        finally:
            conn.close()

    def stats(self) -> Dict[str, int]:
        """获取所有表的行数统计"""
        self._ensure_initialized()
        stats = {}
        for table in self.table_names():
            stats[table] = self.row_count(table)
        return stats
