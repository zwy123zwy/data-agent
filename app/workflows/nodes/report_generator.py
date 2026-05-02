"""
报告生成节点（Report Generator Node） — 对齐 Java ReportGeneratorNode
LLM 动态报告 + ECharts 图表配置推荐 + 步骤结果聚合
"""
from typing import Dict, Any
from ..state import WorkflowState, get_canonical_query
from ..core.llm import get_llm_client
from ..core.config import settings
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

REPORT_SYSTEM_PROMPT = """你是一个数据分析报告生成专家。
根据分析过程和结果，生成专业的数据分析报告。

报告要求:
1. 使用 Markdown 格式
2. 包含: 概述、分析过程、关键发现、数据洞察、建议
3. 语言简洁专业
4. 充分利用分析结果中的数据
5. 如包含图表，描述图表展示的内容

返回完整的 Markdown 报告。
"""

CHART_RECOMMEND_SYSTEM_PROMPT = """你是一个数据可视化专家。
根据 SQL 查询结果的字段和数据特征，推荐最合适的 ECharts 图表配置。

分析维度:
1. 数据字段类型（分类、数值、时间）
2. 数据量级和分布
3. 最适合展示的图表类型

返回 JSON 格式:
{
  "chart_type": "bar" | "line" | "pie" | "scatter",
  "title": "图表标题",
  "x_axis_field": "X轴字段名",
  "y_axis_field": "Y轴字段名",
  "echarts_option": {
    // 完整的 ECharts option 配置
  }
}
"""


def generate_html_report(report_md: str, chart_configs: list, state: WorkflowState) -> str:
    """生成 HTML 格式报告 — 基于 LLM 内容 + ECharts"""
    user_query = get_canonical_query(state)

    charts_html = ""
    if chart_configs:
        for i, cfg in enumerate(chart_configs):
            chart_id = f"chart_{i}"
            charts_html += f"""
            <div class="chart-container">
                <div id="{chart_id}" style="width:100%;height:400px;"></div>
            </div>
            <script>
                var chart_{i} = echarts.init(document.getElementById('{chart_id}'));
                chart_{i}.setOption({json.dumps(cfg.get('echarts_option', cfg), ensure_ascii=False)});
                window.addEventListener('resize', function() {{ chart_{i}.resize(); }});
            </script>
            """

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>数据分析报告</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{ color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; border-left: 4px solid #4CAF50; padding-left: 10px; }}
        h3 {{ color: #666; margin-top: 20px; }}
        .query {{ background-color: #f9f9f9; padding: 15px; border-radius: 4px; border-left: 4px solid #2196F3; }}
        .sql {{ background-color: #2d2d2d; color: #f8f8f2; padding: 15px; border-radius: 4px; overflow-x: auto; font-family: 'Courier New', monospace; font-size: 0.85em; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 0.9em; }}
        th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #e0e0e0; }}
        th {{ background-color: #4CAF50; color: white; font-weight: 600; }}
        tr:hover {{ background-color: #f5f5f5; }}
        .analysis {{ background-color: #e8f5e9; padding: 20px; border-radius: 4px; border-left: 4px solid #4CAF50; line-height: 1.8; }}
        .chart-container {{ margin: 25px 0; padding: 15px; background: #fafafa; border-radius: 8px; border: 1px solid #e0e0e0; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #888; font-size: 0.9em; text-align: center; }}
        .step-result {{ margin: 15px 0; padding: 15px; background: #fafafa; border-radius: 6px; border: 1px solid #e8e8e8; }}
        .badge {{ display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 0.8em; background: #4CAF50; color: white; }}
        pre {{ white-space: pre-wrap; word-wrap: break-word; }}
        blockquote {{ border-left: 4px solid #ddd; padding-left: 15px; color: #666; margin: 15px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>数据分析报告</h1>
        <div class="query">
            <strong>用户查询:</strong> {user_query}
        </div>
        {charts_html}
        <div class="analysis">
            {report_md}
        </div>
        <div class="footer">
            <p>报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Powered by Python Agent V2</p>
        </div>
    </div>
</body>
</html>
"""
    return html


async def _recommend_chart(sql_result: list) -> Dict[str, Any] | None:
    """推荐 ECharts 图表配置 — 对齐 Java data-view-analyze"""
    if not sql_result or len(sql_result) == 0:
        return None

    if not settings.enable_sql_result_chart:
        return None

    try:
        llm = get_llm_client()
        sample = sql_result[:5]
        columns = list(sql_result[0].keys()) if sql_result else []

        prompt = (
            f"数据字段: {columns}\n"
            f"总记录数: {len(sql_result)}\n"
            f"样本数据:\n{json.dumps(sample, ensure_ascii=False, indent=2)}\n\n"
            f"请推荐最合适的 ECharts 图表配置。"
        )

        response = await llm.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": CHART_RECOMMEND_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )

        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]
        return json.loads(text)

    except Exception as e:
        logger.warning(f"[ReportGenerator] Chart recommendation failed: {e}")
        return None


async def report_generator_node(state: WorkflowState) -> Dict[str, Any]:
    """报告生成节点 — 对齐 Java ReportGeneratorNode.apply()

    1. 聚合所有步骤结果
    2. LLM 动态生成 Markdown 报告
    3. 推荐 ECharts 图表配置
    4. 生成 HTML 报告（含 ECharts）
    """
    logger.info("[ReportGenerator] Generating report")

    user_query = get_canonical_query(state)
    sql_memory = state.get("sql_result_list_memory") or []
    step_results = state.get("sql_step_results") or {}
    python_analysis = state.get("python_analysis", "")
    python_output = state.get("python_output", "")
    python_charts = state.get("python_charts", [])
    thought = ""
    plan = state.get("query_plan")

    if isinstance(plan, str):
        try:
            plan = json.loads(plan)
        except json.JSONDecodeError:
            plan = {}
    if plan:
        thought = plan.get("thought_process", "")

    try:
        llm = get_llm_client()

        # 构建报告上下文
        context_parts = [
            f"用户查询: {user_query}",
            f"分析思路: {thought}",
        ]

        # 各 SQL 步骤结果
        for entry in sql_memory:
            step_num = entry.get("step", "?")
            sql = entry.get("sql", "")
            row_count = entry.get("row_count", 0)
            columns = entry.get("columns", [])
            context_parts.append(
                f"Step {step_num} - SQL: {sql}\n"
                f"Step {step_num} - 结果: {row_count} 行, 字段: {columns}"
            )

        # Python 分析
        if python_analysis:
            context_parts.append(f"Python 分析结论: {python_analysis}")
        if python_output:
            context_parts.append(f"Python 执行输出:\n{python_output}")

        context = "\n\n".join(context_parts)

        # LLM 动态生成报告
        response = await llm.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": REPORT_SYSTEM_PROMPT},
                {"role": "user", "content": f"分析上下文:\n{context}\n\n请生成完整的 Markdown 分析报告。"},
            ],
            temperature=0.3,
        )

        report_md = response.choices[0].message.content.strip()
        logger.info(f"[ReportGenerator] Generated report: {len(report_md)} chars")

        # 推荐 ECharts 图表配置 — 对齐 Java data-view-analyze
        chart_configs = []
        if settings.enable_sql_result_chart and sql_memory:
            for entry in sql_memory:
                result = entry.get("result")
                if result:
                    cfg = await _recommend_chart(result)
                    if cfg:
                        chart_configs.append(cfg)

        # 生成 HTML
        html_report = generate_html_report(report_md, chart_configs, state)

        return {
            "report": report_md,
            "html_report": html_report,
            "markdown_report": report_md,
            "display_style": chart_configs[0] if chart_configs else None,
        }

    except Exception as e:
        logger.error(f"[ReportGenerator] Error: {e}")
        fallback_md = f"""# 数据分析报告

## 查询
{user_query}

## 分析结果
{python_analysis or '无分析结果'}

## 备注
报告生成过程中出现错误: {str(e)}
"""
        return {
            "report": fallback_md,
            "html_report": generate_html_report(fallback_md, [], state),
            "markdown_report": fallback_md,
            "error": str(e),
        }
