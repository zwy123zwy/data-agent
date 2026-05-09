"""
SQL 安全校验器 — 防止 SQL 注入和危险操作

只允许只读查询（SELECT / WITH / EXPLAIN / SHOW / DESCRIBE），
拦截所有 DDL、DML、DCL 和文件操作语句。

使用方式:
    from core.sql_validator import validate_sql_safety
    error = validate_sql_safety(sql)
    if error:
        raise ValueError(error)
"""
import re
import logging

logger = logging.getLogger(__name__)

# 多行注释和字符串字面量的移除模式（用于准确检测 SQL 类型）
_BLOCK_COMMENT = re.compile(r'/\*.*?\*/', re.DOTALL)
_LINE_COMMENT = re.compile(r'--[^\n]*')
_SINGLE_QUOTE_STRING = re.compile(r"'(?:[^'\\]|\\.)*'")
_DOUBLE_QUOTE_STRING = re.compile(r'"(?:[^"\\]|\\.)*"')

# 只允许的 SQL 语句类型（不区分大小写）
_ALLOWED_PREFIXES = (
    "SELECT",
    "WITH",
    "EXPLAIN",
    "DESCRIBE",
    "DESC",
    "SHOW",
)

# 危险关键字列表 — 一旦出现则立即拒绝
# 注意: 使用单词边界匹配，避免误判（比如 SELECT 中包含 "inserted" 不会触发）
_DANGEROUS_KEYWORDS = [
    # DDL — 数据结构变更
    "CREATE",
    "ALTER",
    "DROP",
    "TRUNCATE",
    "RENAME",
    # DML — 数据修改
    "INSERT",
    "UPDATE",
    "DELETE",
    "REPLACE",
    "MERGE",
    # DCL — 权限控制
    "GRANT",
    "REVOKE",
    "DENY",
    # 事务控制（只读事务不需要显式控制）
    "COMMIT",
    "ROLLBACK",
    # 危险文件操作
    "INTO OUTFILE",
    "INTO DUMPFILE",
    "LOAD_FILE",
    "LOAD DATA",
    # 其他危险操作
    "EXECUTE",
    "EXEC",
    "CALL",
    "SLEEP",
    "BENCHMARK",
    "WAITFOR",
]

# 危险关键字的正则 — 使用 \b 单词边界确保精确匹配
_DANGEROUS_PATTERNS = [
    re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE)
    for kw in _DANGEROUS_KEYWORDS
]


def _strip_strings_and_comments(sql: str) -> str:
    """移除 SQL 中的字符串字面量和注释，避免误判关键字"""
    s = _BLOCK_COMMENT.sub(" ", sql)
    s = _LINE_COMMENT.sub(" ", s)
    s = _SINGLE_QUOTE_STRING.sub("''", s)
    s = _DOUBLE_QUOTE_STRING.sub('""', s)
    return s


def validate_sql_safety(sql: str) -> str | None:
    """校验 SQL 语句安全性

    Args:
        sql: 待校验的 SQL 语句

    Returns:
        None 表示通过校验，否则返回错误信息字符串
    """
    if not sql or not sql.strip():
        return "SQL 语句为空"

    # 1. 移除注释和字符串，避免误判
    cleaned = _strip_strings_and_comments(sql).strip()

    if not cleaned:
        return "SQL 语句仅包含注释或字符串字面量"

    # 2. 检查是否以允许的关键字开头
    first_word = cleaned.split()[0].upper() if cleaned.split() else ""
    if first_word not in _ALLOWED_PREFIXES:
        return (
            f"不允许的 SQL 语句类型: {first_word}。"
            f"仅允许: {', '.join(_ALLOWED_PREFIXES)}"
        )

    # 3. 检查危险关键字
    for pattern, keyword in zip(_DANGEROUS_PATTERNS, _DANGEROUS_KEYWORDS):
        if pattern.search(cleaned):
            return f"SQL 语句包含危险关键字: {keyword}"

    # 4. 额外检查: 禁止分号后的第二条语句（防止 SQL 堆叠注入）
    # 移除字符串后，分号不应出现
    if ";" in cleaned:
        return "SQL 语句包含分号，不允许执行多条语句"

    logger.debug("[SQLValidator] SQL passed safety check: %s", sql[:80])
    return None
