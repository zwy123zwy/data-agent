"""
端到端报告评测 — L4 层: LLM-as-Judge 报告质量评分

【在系统中的地位】
  评测最终生成的 HTML/Markdown 分析报告的质量。
  使用 LLM-as-Judge 模式: 让另一个 LLM 对报告打分。

【评分维度】
  1. 完整性 (Completeness)     — 是否回答了用户的所有问题
  2. 准确性 (Accuracy)         — 数据引用是否正确，有无幻觉
  3. 可读性 (Readability)      — 结构是否清晰，格式是否规范
  4. 洞察深度 (Insight Depth)  — 是否有超出预期的分析
  5. 可视化质量 (Visual Quality)— 图表是否恰当、清晰

【模块连接】
  上游:
    - run_evaluation.py → 调用 evaluate_report_quality()

  依赖:
    - app/core/llm.py → llm_service.chat() — 用 LLM 评判报告

  Java 对应:
    ReportGeneratorNode.java 的质量评测部分
"""
import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import logging

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

logger = logging.getLogger(__name__)


@dataclass
class ReportQualityResult:
    """单条报告的评测结果"""
    test_id: int
    completeness: float = 0       # 完整性 0-10
    accuracy: float = 0           # 准确性 0-10
    readability: float = 0        # 可读性 0-10
    insight_depth: float = 0      # 洞察深度 0-10
    visual_quality: float = 0     # 可视化质量 0-10
    overall_score: float = 0      # 综合评分 0-100
    judge_comment: str = ""       # 评判理由


@dataclass
class ReportEvalReport:
    """报告评测汇总"""
    total: int
    avg_completeness: float = 0
    avg_accuracy: float = 0
    avg_readability: float = 0
    avg_insight: float = 0
    avg_visual: float = 0
    avg_overall: float = 0
    details: List[ReportQualityResult] = field(default_factory=list)


# LLM-as-Judge System Prompt
REPORT_JUDGE_PROMPT = """你是一个数据分析报告质量评审专家。请对以下报告进行评分。

评分维度 (每个维度 0-10 分):

1. **完整性 (Completeness)**: 报告是否完整回答了用户的问题？是否遗漏了关键信息？
   - 10: 完全回答了所有问题，无遗漏
   - 5: 回答了部分问题，有重要遗漏
   - 0: 完全没有回答问题

2. **准确性 (Accuracy)**: 报告中的数据引用是否准确？是否有明显的数据错误或幻觉？
   - 10: 所有数据引用准确无误
   - 5: 有部分数据不准确
   - 0: 大量数据错误

3. **可读性 (Readability)**: 报告结构是否清晰？格式是否规范？是否易于理解？
   - 10: 结构完美，层次分明，一目了然
   - 5: 基本可读，但组织不够清晰
   - 0: 杂乱无章，难以理解

4. **洞察深度 (Insight Depth)**: 报告是否提供了有价值的分析洞见？是否有深层次的发现？
   - 10: 有深刻洞见，超出预期的分析
   - 5: 有基本分析，但停留在表面
   - 0: 仅有数据罗列，无分析

5. **可视化质量 (Visual Quality)**: 图表是否恰当、清晰、美观？
   - 10: 图表选择恰当，呈现精美
   - 5: 有图表但不够优化
   - 0: 无图表或图表完全不当

请严格按照以下 JSON 格式返回评分结果，不要包含其他内容:
{
  "completeness": <0-10>,
  "accuracy": <0-10>,
  "readability": <0-10>,
  "insight_depth": <0-10>,
  "visual_quality": <0-10>,
  "overall_score": <0-100>,
  "comment": "<简要评判理由>"
}"""


async def evaluate_report_quality(
    report_content: str,
    user_question: str = "",
    test_id: int = 0,
) -> ReportQualityResult:
    """LLM-as-Judge 报告质量评估

    Args:
        report_content: 报告内容 (HTML/Markdown)
        user_question: 原始用户问题 (用于检查完整性)
        test_id: 用例 ID

    Returns:
        ReportQualityResult
    """
    from app.core.llm import llm_service
    from app.core.text_utils import clean_code_block

    user_prompt = f"原始用户问题: {user_question}\n\n报告内容:\n{report_content[:8000]}"

    try:
        raw = await llm_service.chat(REPORT_JUDGE_PROMPT, user_prompt, temperature=0.0)
        result_json = clean_code_block(raw, lang="json")

        scores = json.loads(result_json)

        return ReportQualityResult(
            test_id=test_id,
            completeness=float(scores.get("completeness", 0)),
            accuracy=float(scores.get("accuracy", 0)),
            readability=float(scores.get("readability", 0)),
            insight_depth=float(scores.get("insight_depth", 0)),
            visual_quality=float(scores.get("visual_quality", 0)),
            overall_score=float(scores.get("overall_score", 0)),
            judge_comment=scores.get("comment", ""),
        )
    except Exception as e:
        logger.error(f"[ReportJudge] Evaluation failed: {e}")
        return ReportQualityResult(
            test_id=test_id,
            judge_comment=f"Evaluation error: {e}",
        )


def compute_report_metrics_heuristic(report_content: str) -> Dict[str, float]:
    """启发式报告评分 (不依赖 LLM，用于快速验证)

    检查项:
      - 是否有标题层级 (h1/h2/h3 或 #/##/###)
      - 是否包含数据表格
      - 是否包含图表引用
      - 报告长度是否合理
      - 是否有结论/总结段落
    """
    score = 0.0
    details = []

    # 长度检查 (至少 200 字符)
    if len(report_content) >= 200:
        score += 2
        details.append("length_ok")
    elif len(report_content) >= 50:
        score += 1
        details.append("length_minimal")

    # 标题层级检查
    import re
    if re.search(r'(<h[1-3]>|^#{1,3}\s)', report_content, re.MULTILINE | re.IGNORECASE):
        score += 2
        details.append("has_headings")

    # 数据表格检查
    if re.search(r'(<table|<tr|<td|^\|.*\|)', report_content, re.MULTILINE | re.IGNORECASE):
        score += 2
        details.append("has_table")

    # 图表引用检查
    if re.search(r'(chart|plot|graph|图表|<img|echarts|\.png|\.svg)', report_content, re.IGNORECASE):
        score += 2
        details.append("has_chart_ref")

    # 结论段落检查
    if re.search(r'(结论|总结|建议|conclusion|summary|insight)', report_content, re.IGNORECASE):
        score += 2
        details.append("has_conclusion")

    return {
        "heuristic_score": min(score, 10.0),
        "checks": details,
    }
