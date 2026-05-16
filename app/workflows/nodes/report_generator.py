"""
报告生成节点 — 对齐 Java ReportGeneratorNode

Harness 角色: 工作流的终端节点。汇总所有执行步骤的结果，
调用 LLM 生成 Markdown 分析报告 + ECharts 图表推荐 + HTML 渲染。

I/O 契约:
  requires: user_query, query_plan, sql_result_list_memory, python_analysis, python_output
  provides: report, html_report, markdown_report, display_style
"""
from typing import Dict, Any
from ..state import WorkflowState, get_canonical_query
from ..node_base import WorkflowNode, SSEPayload
from ...core.llm import llm_service
from ...core.config import settings
from ...core.text_utils import clean_code_block
from ...core.database import get_db
from ...services.prompt_config_service import PromptConfigService
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

# 默认报告系统提示词 — 对齐 Java report-generator-plain.txt
DEFAULT_REPORT_SYSTEM_PROMPT = """你是一个数据分析报告生成专家。
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
  "echarts_option": { ... }
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


async def _load_report_prompt(agent_id: int) -> str:
    """加载报告自定义 Prompt — 对齐 Java getOptimizationConfigs("report-generator", agentId)"""
    try:
        async for db in get_db():
            configs = await PromptConfigService.get_active_all_by_type(
                db, "report-generator", agent_id=agent_id
            )
            if configs:
                optimizations = "\n\n".join(c.system_prompt for c in configs if c.system_prompt)
                if optimizations:
                    return DEFAULT_REPORT_SYSTEM_PROMPT + "\n\n## 自定义优化规则\n" + optimizations
    except Exception:
        pass
    return DEFAULT_REPORT_SYSTEM_PROMPT


def _build_user_requirements_and_plan(user_query: str, plan: dict) -> str:
    """构建用户需求与执行计划描述 — 对齐 Java buildUserRequirementsAndPlan"""
    parts = [
        "## 用户原始需求",
        user_query,
        "",
        "## 执行计划概述",
        f"**思考过程**: {plan.get('thought_process', '无')}",
        "",
        "## 详细执行步骤",
    ]
    steps = plan.get("execution_plan", [])
    for i, step in enumerate(steps):
        parts.append(f"### 步骤 {i + 1}: 步骤编号 {step.get('step', i + 1)}")
        parts.append(f"**工具**: {step.get('tool_to_use', 'Unknown')}")
        tp = step.get("tool_parameters") or {}
        if tp.get("instruction"):
            parts.append(f"**参数描述**: {tp['instruction']}")
        parts.append("")
    return "\n".join(parts)


def _build_analysis_steps_and_data(plan: dict, sql_memory: list,
                                   python_analysis: str, python_output: str) -> str:
    """构建分析步骤与数据结果 — 对齐 Java buildAnalysisStepsAndData"""
    parts = ["## 数据执行结果"]
    if not sql_memory and not python_analysis:
        parts.append("暂无执行结果数据")
        return "\n".join(parts)

    steps = plan.get("execution_plan", [])
    for i, step in enumerate(steps):
        step_id = str(i + 1)
        step_key = f"step_{step_id}"

        # 查找对应的 SQL 结果
        sql_info = None
        for entry in sql_memory:
            if str(entry.get("step")) == step_id:
                sql_info = entry
                break

        if not sql_info and not python_analysis:
            continue

        parts.append(f"### {step_key}")
        parts.append(f"**步骤编号**: {step.get('step', i + 1)}")
        parts.append(f"**使用工具**: {step.get('tool_to_use', 'Unknown')}")
        tp = step.get("tool_parameters") or {}
        if tp.get("instruction"):
            parts.append(f"**参数描述**: {tp['instruction']}")
        if tp.get("sql_query"):
            parts.append(f"**执行SQL**: \n```sql\n{tp['sql_query']}\n```")

        if sql_info:
            parts.append(
                f"**执行结果**: \n```json\n"
                f"{json.dumps(sql_info.get('result', ''), ensure_ascii=False)[:2000]}\n```"
            )

    if python_analysis:
        parts.append(f"**Python 分析结果**: {python_analysis}")
    if python_output:
        parts.append(f"**Python 输出**: \n```\n{python_output[:2000]}\n```")

    return "\n".join(parts)


async def _recommend_chart(sql_result: list) -> Dict[str, Any] | None:
    """推荐 ECharts 图表配置 — 对齐 Java data-view-analyze"""
    if not sql_result or len(sql_result) == 0:
        return None
    if not settings.enable_sql_result_chart:
        return None
    try:
        sample = sql_result[:5]
        columns = list(sql_result[0].keys()) if sql_result else []
        prompt = (
            f"数据字段: {columns}\n"
            f"总记录数: {len(sql_result)}\n"
            f"样本数据:\n{json.dumps(sample, ensure_ascii=False, indent=2)}\n\n"
            f"请推荐最合适的 ECharts 图表配置。"
        )
        text = await llm_service.chat(CHART_RECOMMEND_SYSTEM_PROMPT, prompt, temperature=0.0)
        return json.loads(clean_code_block(text, lang="json"))
    except Exception as e:
        logger.warning(f"[ReportGenerator] Chart recommendation failed: {e}")
        return None


class ReportGeneratorNode(WorkflowNode):
    """报告生成 — 对齐 Java ReportGeneratorNode.apply()

    终端节点，汇总所有步骤结果生成最终报告:
    1. 加载 per-agent 自定义报告 Prompt
    2. 构建结构化提示词 (用户需求 + 执行计划 + 数据结果 + Python 分析)
    3. LLM 生成 Markdown 报告
    4. 推荐 ECharts 图表配置
    5. 生成 HTML 报告（含 ECharts 渲染）
    """

    name = "report_generator"
    description = "汇总所有步骤结果，生成 Markdown 报告 + ECharts 图表 + HTML 渲染"
    requires = [
        "user_query", "query_plan", "sql_result_list_memory",
        "python_analysis", "python_output", "python_charts",
    ]
    provides = ["report", "html_report", "markdown_report", "display_style"]
    applicable_data_sources = ["*"]

    async def execute(self, state: WorkflowState) -> Dict[str, Any]:
        logger.info("[ReportGenerator] Generating report")

        user_query = get_canonical_query(state)
        agent_id = state.get("agent_id", 0)
        sql_memory = state.get("sql_result_list_memory") or []
        python_analysis = state.get("python_analysis", "")
        python_output = state.get("python_output", "")
        python_charts = state.get("python_charts", [])

        plan = state.get("query_plan")
        if isinstance(plan, str):
            try:
                plan = json.loads(plan)
            except json.JSONDecodeError:
                plan = {}

        try:
            # 对齐 Java: 从 DB 加载自定义报告 Prompt
            report_system_prompt = await _load_report_prompt(agent_id)

            # 构建结构化提示词
            user_requirements = _build_user_requirements_and_plan(user_query, plan)
            analysis_data = _build_analysis_steps_and_data(
                plan, sql_memory, python_analysis, python_output
            )

            # 获取 summary_and_recommendations
            summary_and_recommendations = ""
            steps = plan.get("execution_plan", [])
            for step in steps:
                tp = step.get("tool_parameters") or {}
                if tp.get("summary_and_recommendations"):
                    summary_and_recommendations = tp["summary_and_recommendations"]
                    break

            full_user_prompt = (
                f"{user_requirements}\n\n"
                f"{analysis_data}\n\n"
                f"## 报告大纲\n{summary_and_recommendations or '根据分析结果生成报告'}\n\n"
                f"请生成完整的 Markdown 分析报告。"
            )

            # LLM 生成报告
            report_md = await llm_service.chat(
                report_system_prompt, full_user_prompt, temperature=0.3
            )
            report_md = report_md.strip()
            logger.info(f"[ReportGenerator] Generated report: {len(report_md)} chars")

            # 推荐 ECharts 图表配置
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

    def format_sse(self, output: Dict[str, Any]) -> SSEPayload | None:
        html_report = output.get("html_report", "")
        report = output.get("report", "")
        markdown_report = output.get("markdown_report", "")
        if html_report:
            return SSEPayload(
                text=html_report,
                text_type="HTML",
                metrics_delta={"report_generated": True},
            )
        elif markdown_report:
            return SSEPayload(
                text=markdown_report,
                text_type="MARK_DOWN",
                metrics_delta={"report_generated": True},
            )
        elif report:
            return SSEPayload(
                text=report,
                text_type="MARK_DOWN",
                metrics_delta={"report_generated": True},
            )
        return None


# LangGraph 兼容实例
report_generator_node = ReportGeneratorNode()
