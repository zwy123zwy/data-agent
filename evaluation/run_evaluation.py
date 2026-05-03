"""
评测主入口 — 对 Text-to-SQL 模型进行全链路评测

【评测流程】
  1. 加载数据集 (test_cases.json)
  2. 遍历每条 test_case，调用 LangGraph 工作流生成 SQL
  3. 计算 L2 指标: SyntaxPass / EX / EM
  4. (Phase 2) 计算 L3/L4 指标: Python 可执行率 / 报告质量
  5. 输出评测报告 JSON

【使用方式】
  python -m evaluation.run_evaluation --dataset business_demo --difficulty all

【模块连接】
  上游 (被调用): 命令行 / CI pipeline
  中层 (调用):   workflows.graph.compiled_workflow → 执行 Text-to-SQL 工作流
  下层 (依赖):   metrics.sql_metrics → 计算各项指标
  输出:           evaluation/reports/YYYY-MM-DD_HH-MM-SS.json
"""
import json
import os
import sys
import time
import argparse
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
)


# ============================================================================
# 数据集加载
# ============================================================================

def load_dataset(dataset_name: str) -> Dict[str, Any]:
    """加载评测数据集

    Returns:
        {"dataset_name": "...", "test_cases": [...], "total_cases": N}
    """
    dataset_dir = Path(__file__).resolve().parent / "datasets" / dataset_name
    test_cases_path = dataset_dir / "test_cases.json"

    if not test_cases_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {test_cases_path}\n"
            f"Available datasets: {list((Path(__file__).resolve().parent / 'datasets').glob('*'))}"
        )

    with open(test_cases_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data


# ============================================================================
# 评测执行
# ============================================================================

class SqlEvaluator:
    """SQL 评测器 — 不依赖数据库，在线计算 SyntaxPass + EM

    注意: 完整评测 (EX/VES) 需要实际数据库连接，当前版本先在
    SyntaxPass 和 EM 层面做离线评估。Phase 2 会在有 DB 连接后加入 EX 和 VES。
    """

    def __init__(self, dataset_name: str):
        self.dataset = load_dataset(dataset_name)
        self.dataset_name = dataset_name
        self.results: List[SqlMetricsResult] = []

    async def evaluate_all(self, difficulty_filter: str = "all") -> EvalReport:
        """遍历所有 test_case 计算指标"""
        test_cases = self.dataset.get("test_cases", [])

        if difficulty_filter != "all":
            test_cases = [
                tc for tc in test_cases
                if tc.get("difficulty") == difficulty_filter
            ]

        report = EvalReport(
            dataset_name=self.dataset_name,
            total=len(test_cases),
        )

        per_diff = {
            "easy": {"total": 0, "sp": 0, "em": 0},
            "medium": {"total": 0, "sp": 0, "em": 0},
            "hard": {"total": 0, "sp": 0, "em": 0},
            "extra_hard": {"total": 0, "sp": 0, "em": 0},
        }

        for tc in test_cases:
            result = self._evaluate_one(tc)
            self.results.append(result)
            report.details.append(result)

            if result.syntax_pass:
                report.syntax_pass_count += 1
                diff = tc.get("difficulty", "easy")
                per_diff[diff]["sp"] += 1

            if result.exact_set_match:
                report.em_pass_count += 1
                diff = tc.get("difficulty", "easy")
                per_diff[diff]["em"] += 1

            diff = tc.get("difficulty", "easy")
            per_diff[diff]["total"] += 1

        # 计算各难度指标
        for diff, stats in per_diff.items():
            t = stats["total"]
            report.per_difficulty[diff] = {
                "total": t,
                "syntax_pass_rate": round(stats["sp"] / t * 100, 1) if t else 0,
                "em_rate": round(stats["em"] / t * 100, 1) if t else 0,
            }

        return report

    def _evaluate_one(self, test_case: Dict) -> SqlMetricsResult:
        """对单条 test_case 计算指标"""
        gold_sql = test_case.get("gold_sql", "")

        result = SqlMetricsResult(
            test_id=test_case.get("id", 0),
            gold_sql=gold_sql,
        )

        # 注: 完整评测中，generated_sql 由 LangGraph 工作流生成
        # 当前阶段先验证 gold_sql 本身的正确性
        result.gen_sql = gold_sql  # Phase 2 替换为实际生成的 SQL

        sp, sp_err = compute_syntax_pass(gold_sql)
        result.syntax_pass = sp
        if not sp:
            result.error_message = sp_err

        # EM: gold vs gold → 应该是100% (验证 gold 自身一致性)
        em, em_err = compute_exact_set_match(gold_sql, gold_sql)
        result.exact_set_match = em

        return result


# ============================================================================
# 报告生成
# ============================================================================

def generate_report(eval_result: EvalReport, output_dir: Path = None) -> str:
    """生成评测报告 JSON 并保存"""
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_path = output_dir / f"{timestamp}.json"

    report_data = {
        "meta": {
            "dataset": eval_result.dataset_name,
            "total_cases": eval_result.total,
            "evaluated_at": datetime.now().isoformat(),
        },
        "summary": {
            "syntax_pass_rate": round(eval_result.syntax_pass_rate, 1),
            "execution_accuracy": round(eval_result.execution_accuracy, 1),
            "exact_set_match_rate": round(eval_result.exact_set_match_rate, 1),
            "avg_ves": round(eval_result.avg_ves, 2),
        },
        "per_difficulty": eval_result.per_difficulty,
        "details": [
            {
                "id": r.test_id,
                "syntax_pass": r.syntax_pass,
                "exact_set_match": r.exact_set_match,
                "execution_accuracy": r.execution_accuracy,
                "error": r.error_message,
            }
            for r in eval_result.details
        ],
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] Report saved to: {report_path}")
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
    args = parser.parse_args()

    print("=" * 60)
    print(f"  Text-to-SQL Evaluation")
    print(f"  Dataset:   {args.dataset}")
    print(f"  Difficulty: {args.difficulty}")
    print("=" * 60)

    evaluator = SqlEvaluator(args.dataset)
    report = await evaluator.evaluate_all(args.difficulty)

    print(f"\n{'─' * 40}")
    print(f"  Total:          {report.total}")
    print(f"  Syntax Pass:    {report.syntax_pass_rate:.1f}%  ({report.syntax_pass_count}/{report.total})")
    print(f"  ExactSetMatch:  {report.exact_set_match_rate:.1f}%  ({report.em_pass_count}/{report.total})")
    print(f"{'─' * 40}")

    for diff, stats in report.per_difficulty.items():
        if stats["total"] > 0:
            print(f"  [{diff:12s}] SP={stats['syntax_pass_rate']:.1f}%  EM={stats['em_rate']:.1f}%  (n={stats['total']})")

    generate_report(report)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
