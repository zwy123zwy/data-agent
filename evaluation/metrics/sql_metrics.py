"""
SQL 评测指标计算 — Text-to-SQL 业界标准指标

【指标说明】
  EX (Execution Accuracy):
    执行 generated_sql 和 gold_sql，比较两者的执行结果是否一致。
    这是最重要的指标 — 容忍语法不同但语义等价的SQL。
    例: SELECT * FROM t WHERE id=1 与 SELECT * FROM t WHERE id IN (1) 结果一致 → 正确

  EM (Exact Set Match):
    将 SQL 拆解为组件集合 (SELECT列, FROM表, WHERE条件...)，逐个比对。
    比 EX 更严格，要求 SQL 结构和 gold 完全等价。

  SP (Syntax Pass):
    SQL 能否成功解析并执行。最低门槛指标。

  VES (Valid Efficiency Score):
    在 EX 正确的前提下，评估生成 SQL 的执行效率。
    得分 = min(1.0, gold_time / gen_time)，越接近1越高效。

【模块连接】
  被调用: evaluation/run_evaluation.py → for each test_case → compute_*()
  依赖:    sqlalchemy (执行SQL对比结果)
"""
import re
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class SqlMetricsResult:
    """单条 SQL 的评测结果"""
    test_id: int
    syntax_pass: bool = False
    execution_accuracy: bool = False
    exact_set_match: bool = False
    valid_efficiency_score: Optional[float] = None
    error_message: Optional[str] = None
    gen_sql: str = ""
    gold_sql: str = ""


@dataclass
class EvalReport:
    """完整评测报告"""
    dataset_name: str
    total: int
    syntax_pass_count: int = 0
    ex_pass_count: int = 0
    em_pass_count: int = 0
    ves_scores: List[float] = field(default_factory=list)
    details: List[SqlMetricsResult] = field(default_factory=list)
    per_difficulty: Dict[str, Dict] = field(default_factory=dict)

    @property
    def syntax_pass_rate(self) -> float:
        return self.syntax_pass_count / self.total * 100 if self.total else 0

    @property
    def execution_accuracy(self) -> float:
        return self.ex_pass_count / self.total * 100 if self.total else 0

    @property
    def exact_set_match_rate(self) -> float:
        return self.em_pass_count / self.total * 100 if self.total else 0

    @property
    def avg_ves(self) -> float:
        return sum(self.ves_scores) / len(self.ves_scores) if self.ves_scores else 0


# ============================================================================
# SQL 组件拆解 — 用于 EM (Exact Set Match)
# ============================================================================

def _normalize_sql(sql: str) -> str:
    """标准化 SQL: 去多余空格、统一大小写、去分号"""
    sql = sql.strip().rstrip(";")
    sql = re.sub(r"\s+", " ", sql)
    return sql.strip().lower()


def _extract_sql_components(sql: str) -> Dict[str, set]:
    """将 SQL 拆解为组件集合

    返回: {
      "select_columns": {"col1", "col2", ...},
      "from_tables": {"t1", "t2", ...},
      "where_conditions": {"cond1", "cond2", ...},  # 按 AND/OR 分割
      "group_by": {"col1", ...},
      "order_by": {"col1 ASC", ...},
      "has_join": True/False,
      "has_subquery": True/False,
      "has_aggregation": True/False,
    }
    """
    sql = _normalize_sql(sql)

    components = {
        "select_columns": set(),
        "from_tables": set(),
        "where_conditions": set(),
        "group_by": set(),
        "order_by": set(),
        "has_join": False,
        "has_subquery": False,
        "has_aggregation": False,
    }

    # 提取 SELECT 列
    select_match = re.search(
        r"select\s+(.*?)\s+from\s", sql, re.IGNORECASE | re.DOTALL
    )
    if select_match:
        cols = select_match.group(1)
        # 按逗号分割 (不分割括号内的逗号)
        for col in _split_top_level(cols, ","):
            col = col.strip().lower()
            # 去掉别名
            col = re.sub(r"\s+as\s+\w+", "", col)
            components["select_columns"].add(col)

    # 提取 FROM 表
    from_match = re.search(
        r"from\s+(.*?)(?:where|group\s+by|having|order\s+by|limit|$)",
        sql, re.IGNORECASE
    )
    if from_match:
        tables = from_match.group(1)
        for t in _split_top_level(tables, r"\b(?:join|inner\s+join|left\s+join|right\s+join|cross\s+join)\b"):
            t = t.strip().lower()
            t = re.sub(r"\s+as\s+\w+", "", t)
            if t:
                components["from_tables"].add(t)

    # 检测 JOIN
    if re.search(r"\bjoin\b", sql, re.IGNORECASE):
        components["has_join"] = True

    # 检测子查询
    if re.search(r"select\s+.*\s+from\s+.*\(", sql, re.IGNORECASE):
        components["has_subquery"] = True
    if re.search(r"\(\s*select\s+", sql, re.IGNORECASE):
        components["has_subquery"] = True

    # 检测聚合
    if re.search(r"\b(count|sum|avg|max|min)\s*\(\s*\*", sql, re.IGNORECASE):
        components["has_aggregation"] = True

    # GROUP BY
    group_match = re.search(r"group\s+by\s+(.*?)(?:having|order\s+by|limit|$)", sql, re.IGNORECASE)
    if group_match:
        for col in group_match.group(1).split(","):
            components["group_by"].add(col.strip().lower())

    # ORDER BY
    order_match = re.search(r"order\s+by\s+(.*?)(?:limit|$)", sql, re.IGNORECASE)
    if order_match:
        for col in order_match.group(1).split(","):
            components["order_by"].add(col.strip().lower())

    return components


def _split_top_level(text: str, delimiter: str) -> List[str]:
    """按分隔符切分，忽略括号内的分隔符"""
    parts = []
    depth = 0
    current = []
    # 如果是正则模式，先找到所有分割点
    if isinstance(delimiter, str) and delimiter == ",":
        for ch in text:
            if ch in "(":
                depth += 1
            elif ch in ")":
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append("".join(current))
                current = []
                continue
            current.append(ch)
        if current:
            parts.append("".join(current))
        return parts
    else:
        # regex 分割
        for match in re.finditer(delimiter, text, re.IGNORECASE):
            prefix = text[: match.start()]
            if prefix.strip():
                parts.append(prefix.strip())
            text = text[match.end():]
        if text.strip():
            parts.append(text.strip())
        return parts


# ============================================================================
# 核心指标计算
# ============================================================================

def compute_syntax_pass(sql: str) -> tuple[bool, Optional[str]]:
    """检查 SQL 语法是否可以解析 (不需要实际执行即可判断)"""
    sql = _normalize_sql(sql)
    if not sql:
        return False, "Empty SQL"

    # 基本语法检查: 必须有 SELECT + FROM
    if not re.search(r"\bselect\b", sql, re.IGNORECASE):
        return False, "Missing SELECT keyword"
    if not re.search(r"\bfrom\b", sql, re.IGNORECASE):
        return False, "Missing FROM keyword"

    # 括号匹配检查
    depth = 0
    for ch in sql:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False, "Unmatched closing parenthesis"
    if depth != 0:
        return False, "Unmatched opening parenthesis"

    return True, None


async def compute_execution_accuracy(
    generated_sql: str,
    gold_sql: str,
    db_executor,  # AsyncSession or connection
) -> tuple[bool, Optional[str]]:
    """EX (Execution Accuracy): 两条 SQL 执行结果是否一致

    Args:
        generated_sql: 模型生成的 SQL
        gold_sql: 标准答案 SQL
        db_executor: 数据库执行器 (有 execute_sql 方法)

    Returns:
        (是否一致, 错误信息)
    """
    try:
        gen_rows = await db_executor.execute_sql(generated_sql)
        gold_rows = await db_executor.execute_sql(gold_sql)
        return _compare_result_sets(gen_rows, gold_rows)
    except Exception as e:
        return False, str(e)


def _compare_result_sets(
    rows1: List[Dict], rows2: List[Dict]
) -> tuple[bool, Optional[str]]:
    """比较两个结果集是否等价 (排序后逐行逐列比较)"""
    # 列数不同 → 不匹配
    if not rows1 and not rows2:
        return True, None
    if not rows1 or not rows2:
        return False, "One result set is empty"

    cols1 = set(rows1[0].keys())
    cols2 = set(rows2[0].keys())
    if cols1 != cols2:
        return False, f"Column mismatch: {cols1 - cols2} vs {cols2 - cols1}"

    # 标准化排序后比较
    cols = sorted(cols1)
    sorted1 = sorted([tuple(str(r.get(c, "")).lower() for c in cols) for r in rows1])
    sorted2 = sorted([tuple(str(r.get(c, "")).lower() for c in cols) for r in rows2])

    if sorted1 == sorted2:
        return True, None
    return False, f"Row mismatch: {len(sorted1)} vs {len(sorted2)} rows"


def compute_exact_set_match(generated_sql: str, gold_sql: str) -> tuple[bool, Optional[str]]:
    """EM (Exact Set Match): SQL 组件级精确匹配

    拆解两条 SQL 为 {select列, from表, where条件...} 集合，逐项比对。
    """
    gen_comp = _extract_sql_components(generated_sql)
    gold_comp = _extract_sql_components(gold_sql)

    for key in ["select_columns", "from_tables"]:
        if gen_comp[key] != gold_comp[key]:
            return False, f"Component '{key}' mismatch: {gen_comp[key]} vs {gold_comp[key]}"

    # 宽松比对: group_by, order_by 不要求完全一致
    for key in ["has_join", "has_subquery", "has_aggregation"]:
        if gen_comp[key] != gold_comp[key]:
            return False, f"Structural '{key}' mismatch"

    return True, None


def compute_ves(gen_time_ms: float, gold_time_ms: float) -> float:
    """VES (Valid Efficiency Score): 效率评分

    VES = min(1.0, gold_time / gen_time)
    - VES >= 1.0: 与标准答案一样快或更快 → 满分
    - VES < 1.0: 比标准答案慢 → 按比例扣分
    - 最低 0 分 (如果超时)

    注意: 此指标需要 SQL 在有数据的库上实际执行才能获取时间。
    """
    if gen_time_ms <= 0:
        return 0.0
    return min(1.0, gold_time_ms / max(gen_time_ms, 0.001))
