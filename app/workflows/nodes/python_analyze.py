"""
Python 分析节点（Python Analyze Node）
分析 Python 执行结果并生成文字描述
"""
from typing import Dict, Any
from ..state import AgentState
from ...core.llm import get_llm_client
from ...core.config import settings
import logging

logger = logging.getLogger(__name__)


async def python_analyze_node(state: AgentState) -> Dict[str, Any]:
    """
    Python 分析节点

    解读 Python 执行结果，生成分析结论

    Args:
        state: 工作流状态

    Returns:
        更新后的状态
    """
    python_output = state.get("python_output")
    python_charts = state.get("python_charts", [])
    python_data = state.get("python_data")
    user_query = state.get("rewritten_query") or state["user_query"]

    if not python_output and not python_data:
        logger.warning("[PythonAnalyze] No Python output to analyze")
        return {"python_analysis": "无分析结果"}

    logger.info("[PythonAnalyze] Analyzing Python execution results")

    try:
        llm = get_llm_client()

        # 构建提示
        prompt = f"""用户查询: {user_query}

Python 执行输出:
{python_output or python_data}

生成的图表: {', '.join(python_charts) if python_charts else '无'}

请根据上述执行结果，生成简洁的分析结论（2-3句话）。
重点说明：
1. 数据的主要特征
2. 关键发现
3. 对用户查询的回答

只返回分析文字，不要有标题或格式。
"""

        response = await llm.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )

        analysis = response.choices[0].message.content.strip()

        logger.info("[PythonAnalyze] Analysis generated")

        return {"python_analysis": analysis}

    except Exception as e:
        logger.error(f"[PythonAnalyze] Error: {e}")
        return {"python_analysis": f"分析失败: {str(e)}"}
