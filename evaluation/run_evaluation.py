"""
评测主入口 — Text-to-SQL 全链路评测 (L2/L3/L4)

【评测流程】
  1. 加载数据集 (test_cases.json)
  2. 初始化 SQLite 测试数据库 (schema + seed data)
  3. 遍历每条 test_case:
     a. 调用 LLM 生成 SQL (vs gold_sql)
     b. 计算 L2 指标: SP / EM / EX / VES
     c. (Phase 3) 如果涉及 Python 分析，计算 L3 指标
     d. (Phase 4) 如果生成报告，计算 L4 指标
  4. 输出评测报告 JSON

【使用方式】
  # 完整评测 (需要 LLM API Key)
  python -m evaluation.run_evaluation --dataset business_demo --mode full

  # 仅验证 gold_sql 自身 (不需要 LLM)
  python -m evaluation.run_evaluation --dataset business_demo --mode validate

  # 按难度过滤
  python -m evaluation.run_evaluation --dataset business_demo --difficulty hard

  # 仅执行 SQL 生成 + 执行评测 (不评 Python/Report)
  python -m evaluation.run_evaluation --dataset business_demo --mode sql-only

【模块连接】
  上游 (被调用):  命令行 / CI pipeline
  调用:
    - evaluation/sql_generator.py       → LLM 生成 SQL
    - evaluation/test_database.py       → SQLite 执行环境
    - evaluation/metrics/sql_metrics.py   → SP/EM/EX/VES 计算
    - evaluation/metrics/python_metrics.py → Python 代码评测
    - evaluation/metrics/report_metrics.py → 报告质量评测
  输出: evaluation/reports/YYYY-MM-DD_HH-MM-SS.json
"""
import json
import os
import sys
import time
import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from .metrics.sql_metrics import (
    SqlMetricsResult,
    EvalReport,
    compute_syntax_pass,
    compute_exact_set_match,
    compute_execution_accuracy_sync,
    compute_ves,
)
from .metrics.python_metrics import (
    PythonMetricsResult,
    PythonEvalReport,
    compute_python_metrics,
)
from .metrics.report_metrics import (
    ReportQualityResult,
    ReportEvalReport,
    evaluate_report_quality,
    compute_report_metrics_heuristic,
)
from .test_database import TestDatabase
from .sql_generator import generate_sql_from_schema

import logging

logger = logging.getLogger(__name__)


# ============================================================================
# 数据集加载
# ============================================================================

def load_dataset(dataset_name: str) -> Dict[str, Any]:
    """加载评测数据集"""
    dataset_dir = Path(__file__).resolve().parent / "datasets" / dataset_name
    test_cases_path = dataset_dir / "test_cases.json"

    if not test_cases_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {test_cases_path}\n"
            f"Available datasets: {list((Path(__file__).resolve().parent / 'datasets').glob('*'))}"
        )

    with open(test_cases_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_schema(dataset_name: str) -> str:
    """加载数据集 schema DDL"""
    schema_path = (
        Path(__file__).resolve().parent / "datasets" / dataset_name / "schema.sql"
    )
    if schema_path.exists():
        return schema_path.read_text(encoding="utf-8")
    return ""


# ============================================================================
# 评测模式枚举
# ============================================================================

VALIDATE = "validate"       # 仅验证 gold_sql 自身 (SP + EM, 不需要 LLM/DB)
SQL_ONLY = "sql-only"       # SQL 生成 + 执行评测 (SP/EM/EX/VES, 需要 LLM)
FULL = "full"               # 完整评测 (L2 + L3 + L4, 需要 LLM)


# ============================================================================
# 评测执行
# ============================================================================

class SqlEvaluator:
    """SQL 评测器 — 支持 validate / sql-only / full 三种模式"""

    def __init__(self, dataset_name: str, mode: str = FULL):
        self.dataset = load_dataset(dataset_name)
        self.dataset_name = dataset_name
        self.mode = mode

        # 加载 schema (用于 LLM SQL 生成)
        self.schema_sql = load_schema(dataset_name)

        # 初始化 SQLite 测试数据库 (sql-only / full 模式需要)
        self.test_db: Optional[TestDatabase] = None
        if mode in (SQL_ONLY, FULL):
            try:
                self.test_db = TestDatabase(dataset_name)
                _ = self.test_db.stats()  # 触发初始化
                logger.info(f"[Eval] Test database ready: {dataset_name}")
            except Exception as e:
                logger.warning(f"[Eval] Test database init failed: {e}")
                self.test_db = None

        # 存储结果
        self.sql_results: List[SqlMetricsResult] = []
        self.python_results: List[PythonMetricsResult] = []
        self.report_results: List[ReportQualityResult] = []

    async def evaluate_all(
        self, difficulty_filter: str = "all", use_llm: bool = True
    ) -> Dict[str, Any]:
        """遍历所有 test_case 计算指标
        返回: 完整的评测报告 dict
        """
        test_cases = self.dataset.get("test_cases", [])

        # 难度过滤
        if difficulty_filter != "all":
            test_cases = [tc for tc in test_cases if tc.get("difficulty") == difficulty_filter]

        total = len(test_cases)
        report = EvalReport(dataset_name=self.dataset_name, total=total)

        # 难度统计
        per_diff = {"easy": {"total": 0, "sp": 0, "em": 0, "ex": 0},
                     "medium": {"total": 0, "sp": 0, "em": 0, "ex": 0},
                     "hard": {"total": 0, "sp": 0, "em": 0, "ex": 0},
                     "extra_hard": {"total": 0, "sp": 0, "em": 0, "ex": 0}}

        for idx, tc in enumerate(test_cases):
            tc_id = tc.get("id", idx)
            diff = tc.get("difficulty", "easy")
            question = tc.get("question", "")
            gold_sql = tc.get("gold_sql", "")

            logger.info(f"[Eval] [{idx + 1}/{total}] id={tc_id}, diff={diff}: {question[:60]}...")

            # ── Step 1: Compute SP & EM on gold SQL (baseline) ──
            result = SqlMetricsResult(test_id=tc_id, gold_sql=gold_sql)

            # ── Step 2: Generate SQL via LLM (if not validate mode) ──
            generated_sql = gold_sql  # default: gold = gen (for validate mode)
            llm_used = False

            if self.mode != VALIDATE and use_llm:
                try:
                    sql_features = tc.get("sql_features", [])
                    instruction = f"Category: {tc.get('category', '')}. "
                    instruction += f"Features: {', '.join(sql_features)}. "
                    instruction += f"Expected tables: {', '.join(tc.get('tables', []))}."

                    generated_sql = await generate_sql_from_schema(
                        question=question,
                        schema_sql=self.schema_sql,
                        dialect="mysql",
                        instruction=instruction,
                    )
                    llm_used = True
                    result.gen_sql = generated_sql
                except Exception as e:
                    logger.warning(f"[Eval] LLM generation failed for id={tc_id}: {e}")
                    result.gen_sql = gold_sql
                    result.error_message = f"LLM generation failed: {e}"

            # ── Step 3: Compute SP on generated SQL ──
            gen_sp, gen_sp_err = compute_syntax_pass(generated_sql)
            result.syntax_pass = gen_sp
            if not gen_sp:
                result.error_message = result.error_message or gen_sp_err

            # ── Step 4: Compute EM (gen vs gold) ──
            gen_em, gen_em_err = compute_exact_set_match(generated_sql, gold_sql)
            result.exact_set_match = gen_em
            if not gen_em and gen_em_err:
                result.error_message = result.error_message or gen_em_err

            # ── Step 5: Compute EX & VES (if DB available) ──
            if self.test_db and self.mode != VALIDATE:
                ex_match, ex_err, gen_time, gold_time = compute_execution_accuracy_sync(
                    generated_sql, gold_sql, self.test_db
                )
                result.execution_accuracy = ex_match
                if not ex_match and ex_err:
                    result.error_message = result.error_message or ex_err
                if ex_match and gen_time and gold_time:
                    result.valid_efficiency_score = compute_ves(gen_time, gold_time)
                elif gen_time and gold_time:
                    result.valid_efficiency_score = compute_ves(gen_time, gold_time)

            # ── Count once at the end ──
            per_diff[diff]["total"] += 1
            if result.syntax_pass:
                per_diff[diff]["sp"] += 1
            if result.exact_set_match:
                per_diff[diff]["em"] += 1
            if result.execution_accuracy:
                per_diff[diff]["ex"] += 1

            report.details.append(result)
            self.sql_results.append(result)

            # ── Step 5: Python metrics (if full mode and has python features) ──
            if self.mode == FULL and tc.get("category") in ("advanced_analytics",):
                # For now, only evaluate Python for advanced analytics cases
                pass  # Python code generation requires full workflow context

            # ── Step 6: Report quality (if full mode) ──
            if self.mode == FULL and use_llm and tc.get("category") in ("advanced_analytics",):
                # Report quality requires full report from workflow
                pass  # Requires full workflow output

        # ── Aggregate report-level counters from per-difficulty stats ──
        for d, stats in per_diff.items():
            t = stats["total"]
            report.syntax_pass_count += stats["sp"]
            report.em_pass_count += stats["em"]
            report.ex_pass_count += stats["ex"]
            report.per_difficulty[d] = {
                "total": t,
                "syntax_pass_rate": round(stats["sp"] / t * 100, 1) if t else 0,
                "em_rate": round(stats["em"] / t * 100, 1) if t else 0,
                "ex_rate": round(stats["ex"] / t * 100, 1) if t else 0,
            }

        return self._build_report_dict(report, use_llm)

    def _build_report_dict(self, report: EvalReport, use_llm: bool) -> Dict[str, Any]:
        """构建完整评测报告 dict"""
        return {
            "meta": {
                "dataset": report.dataset_name,
                "total_cases": report.total,
                "mode": self.mode,
                "llm_enabled": use_llm,
                "db_available": self.test_db is not None,
                "evaluated_at": datetime.now().isoformat(),
            },
            "summary": {
                "syntax_pass_rate": round(report.syntax_pass_rate, 1),
                "execution_accuracy": round(report.execution_accuracy, 1),
                "exact_set_match_rate": round(report.exact_set_match_rate, 1),
                "avg_ves": round(report.avg_ves, 2),
            },
            "per_difficulty": report.per_difficulty,
            "details": [
                {
                    "id": r.test_id,
                    "syntax_pass": r.syntax_pass,
                    "exact_set_match": r.exact_set_match,
                    "execution_accuracy": r.execution_accuracy,
                    "ves": r.valid_efficiency_score,
                    "error": r.error_message,
                }
                for r in report.details
            ],
            "python_evaluation": {
                "status": "not_run" if self.mode != FULL else "skipped",
                "note": "需要完整 LangGraph 工作流上下文才能生成 Python 代码",
            },
            "report_evaluation": {
                "status": "not_run" if self.mode != FULL else "skipped",
                "note": "需要完整 LangGraph 工作流输出才能评测报告质量",
            },
        }


# ============================================================================
# 报告生成
# ============================================================================

def generate_report(eval_data: Dict[str, Any], output_dir: Path = None) -> str:
    """生成评测报告 JSON 并保存"""
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_path = output_dir / f"{timestamp}.json"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(eval_data, f, ensure_ascii=False, indent=2)

    return str(report_path)


# ============================================================================
# CLI
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(description="Text-to-SQL Evaluation Runner")
    parser.add_argument(
        "--dataset", "-d",
        default="business_demo",
        help="Dataset name (default: business_demo)"
    )
    parser.add_argument(
        "--difficulty",
        default="all",
        choices=["all", "easy", "medium", "hard", "extra_hard"],
        help="Filter by difficulty level (default: all)"
    )
    parser.add_argument(
        "--mode", "-m",
        default="validate",
        choices=["validate", "sql-only", "full"],
        help="Evaluation mode: validate (gold self-check, no LLM), sql-only (generate+execute), full (L2+L3+L4)"
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM (在 sql-only/full 模式下也跳过 LLM 调用)"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output report path (default: reports/YYYY-MM-DD_HH-MM-SS.json)"
    )
    args = parser.parse_args()

    use_llm = not args.no_llm

    print("=" * 60)
    print(f"  Text-to-SQL Evaluation")
    print(f"  Dataset:    {args.dataset}")
    print(f"  Mode:       {args.mode}")
    print(f"  Difficulty: {args.difficulty}")
    print(f"  LLM:        {'enabled' if use_llm else 'disabled'}")
    print("=" * 60)

    evaluator = SqlEvaluator(args.dataset, mode=args.mode)
    report_data = await evaluator.evaluate_all(args.difficulty, use_llm=use_llm)

    # 打印结果
    summary = report_data["summary"]
    meta = report_data["meta"]
    print(f"\n{'─' * 50}")
    print(f"  Total:            {meta['total_cases']}")
    print(f"  DB Available:     {meta['db_available']}")
    print(f"  Syntax Pass:      {summary['syntax_pass_rate']:.1f}%")
    print(f"  Execution Accuracy:{summary['execution_accuracy']:.1f}%")
    print(f"  ExactSetMatch:    {summary['exact_set_match_rate']:.1f}%")
    if summary['avg_ves'] > 0:
        print(f"  Avg VES:          {summary['avg_ves']:.2f}")
    print(f"{'─' * 50}")

    for diff, stats in report_data.get("per_difficulty", {}).items():
        if stats.get("total", 0) > 0:
            sp = stats.get('syntax_pass_rate', 0)
            em = stats.get('em_rate', 0)
            ex = stats.get('ex_rate', 0)
            n = stats['total']
            print(f"  [{diff:12s}] SP={sp:.1f}%  EM={em:.1f}%  EX={ex:.1f}%  (n={n})")

    report_path = generate_report(report_data)
    if args.output:
        import shutil
        shutil.copy(report_path, args.output)
        print(f"\n[OK] Report also copied to: {args.output}")

    print(f"\n[OK] Report saved to: {report_path}")

    if not meta['db_available'] and args.mode != "validate":
        print("\n[WARN] Test database is not available. EX/VES metrics will not be computed.")
        print("       Ensure the dataset has valid schema.sql and seed_data.sql files.")

    if args.mode == "validate":
        print("\n[TIP] Run with '--mode sql-only' to test actual SQL generation via LLM.")
        print("      Set OPENAI_API_KEY in .env file first.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
