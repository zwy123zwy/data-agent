"""
报告生成节点（Report Generator Node）
生成 HTML/Markdown 格式的完整报告
"""
from typing import Dict, Any
from ..state import AgentState
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_html_report(state: AgentState) -> str:
    """
    生成 HTML 格式报告

    Args:
        state: 工作流状态

    Returns:
        HTML 报告内容
    """
    user_query = state.get("rewritten_query") or state["user_query"]
    generated_sql = state.get("generated_sql", "")
    sql_result = state.get("sql_result", [])
    python_code = state.get("python_code")
    python_output = state.get("python_output")
    python_analysis = state.get("python_analysis")
    python_charts = state.get("python_charts", [])

    # HTML 模板
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>数据分析报告</title>
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
        h1 {{
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 30px;
            border-left: 4px solid #4CAF50;
            padding-left: 10px;
        }}
        .section {{
            margin: 20px 0;
        }}
        .query {{
            background-color: #f9f9f9;
            padding: 15px;
            border-radius: 4px;
            border-left: 4px solid #2196F3;
        }}
        .sql {{
            background-color: #f4f4f4;
            padding: 15px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            overflow-x: auto;
            border: 1px solid #ddd;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .analysis {{
            background-color: #e8f5e9;
            padding: 20px;
            border-radius: 4px;
            border-left: 4px solid #4CAF50;
            line-height: 1.6;
        }}
        .chart {{
            margin: 20px 0;
            text-align: center;
        }}
        .chart img {{
            max-width: 100%;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #888;
            font-size: 0.9em;
            text-align: center;
        }}
        .code {{
            background-color: #f4f4f4;
            padding: 15px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            overflow-x: auto;
            font-size: 0.9em;
            border: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 数据分析报告</h1>

        <div class="section">
            <h2>查询</h2>
            <div class="query">
                <strong>用户查询:</strong> {user_query}
            </div>
        </div>

        <div class="section">
            <h2>SQL 查询</h2>
            <div class="sql">
                <pre>{generated_sql}</pre>
            </div>
        </div>

        <div class="section">
            <h2>查询结果</h2>
            <p>共查询到 <strong>{len(sql_result)}</strong> 条记录</p>
"""

    # 添加数据表格（最多显示 10 条）
    if sql_result:
        html += """
            <table>
                <thead>
                    <tr>
"""
        # 表头
        for key in sql_result[0].keys():
            html += f"                        <th>{key}</th>\n"
        html += """                    </tr>
                </thead>
                <tbody>
"""
        # 数据行（最多 10 条）
        for row in sql_result[:10]:
            html += "                    <tr>\n"
            for value in row.values():
                html += f"                        <td>{value}</td>\n"
            html += "                    </tr>\n"

        if len(sql_result) > 10:
            html += f"""                    <tr>
                        <td colspan="{len(sql_result[0])}" style="text-align: center; color: #888;">
                            ... 还有 {len(sql_result) - 10} 条记录未显示
                        </td>
                    </tr>
"""
        html += """                </tbody>
            </table>
"""

    # 添加 Python 分析部分
    if python_code or python_analysis:
        html += """
        <div class="section">
            <h2>数据分析</h2>
"""
        if python_analysis:
            html += f"""
            <div class="analysis">
                {python_analysis}
            </div>
"""

        # 添加图表
        if python_charts:
            html += """
            <h3>可视化图表</h3>
"""
            for chart in python_charts:
                html += f"""
            <div class="chart">
                <img src="{chart}" alt="分析图表" />
                <p><em>{chart}</em></p>
            </div>
"""

        # 添加 Python 输出
        if python_output:
            html += f"""
            <h3>分析输出</h3>
            <div class="code">
                <pre>{python_output}</pre>
            </div>
"""

        html += """
        </div>
"""

    # 页脚
    html += f"""
        <div class="footer">
            <p>报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Powered by Python Agent V2</p>
        </div>
    </div>
</body>
</html>
"""

    return html


def generate_markdown_report(state: AgentState) -> str:
    """
    生成 Markdown 格式报告

    Args:
        state: 工作流状态

    Returns:
        Markdown 报告内容
    """
    user_query = state.get("rewritten_query") or state["user_query"]
    generated_sql = state.get("generated_sql", "")
    sql_result = state.get("sql_result", [])
    python_analysis = state.get("python_analysis")
    python_output = state.get("python_output")
    python_charts = state.get("python_charts", [])

    # Markdown 模板
    md = f"""# 📊 数据分析报告

## 查询

**用户查询**: {user_query}

## SQL 查询

```sql
{generated_sql}
```

## 查询结果

共查询到 **{len(sql_result)}** 条记录

"""

    # 添加数据表格（最多显示 10 条）
    if sql_result:
        # 表头
        md += "| " + " | ".join(sql_result[0].keys()) + " |\n"
        md += "| " + " | ".join(["---"] * len(sql_result[0])) + " |\n"

        # 数据行（最多 10 条）
        for row in sql_result[:10]:
            md += "| " + " | ".join(str(v) for v in row.values()) + " |\n"

        if len(sql_result) > 10:
            md += f"\n*... 还有 {len(sql_result) - 10} 条记录未显示*\n"

    # 添加分析部分
    if python_analysis:
        md += f"""
## 数据分析

{python_analysis}

"""

    # 添加图表
    if python_charts:
        md += "### 可视化图表\n\n"
        for chart in python_charts:
            md += f"![{chart}]({chart})\n\n"

    # 添加 Python 输出
    if python_output:
        md += f"""### 分析输出

```
{python_output}
```

"""

    # 页脚
    md += f"""---

*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*

*Powered by Python Agent V2*
"""

    return md


async def report_generator_node(state: AgentState) -> Dict[str, Any]:
    """
    报告生成节点

    生成完整的分析报告

    Args:
        state: 工作流状态

    Returns:
        更新后的状态
    """
    logger.info("[ReportGenerator] Generating report")

    try:
        # 生成 HTML 报告
        html_report = generate_html_report(state)

        # 生成 Markdown 报告
        markdown_report = generate_markdown_report(state)

        logger.info("[ReportGenerator] Report generated successfully")

        return {
            "report": markdown_report,  # 默认返回 Markdown
            "html_report": html_report,
            "markdown_report": markdown_report
        }

    except Exception as e:
        logger.error(f"[ReportGenerator] Error: {e}")
        return {
            "report": f"报告生成失败: {str(e)}",
            "error": str(e)
        }
