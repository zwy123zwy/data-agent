"""
计划生成节点（Planner Node）
将复杂查询分解为多个步骤
"""
from typing import Dict, Any
from ..state import AgentState
from ...core.llm import get_llm_client
from ...core.config import settings
import logging
import json

logger = logging.getLogger(__name__)


PLANNER_SYSTEM_PROMPT = """你是一个查询计划生成专家。
根据用户的复杂查询和数据库结构，将查询分解为多个可执行的步骤。

步骤类型：
1. sql_query - SQL 查询步骤
2. python_analysis - Python 数据分析步骤
3. report - 报告生成步骤

要求：
1. 每个步骤要有清晰的描述
2. 标明步骤之间的依赖关系
3. SQL 步骤要包含具体的 SQL 语句
4. Python 步骤要包含分析逻辑描述
5. 步骤要按逻辑顺序排列

返回 JSON 格式：
{
  "steps": [
    {
      "id": 1,
      "type": "sql_query",
      "description": "查询最近3个月每个地区的销售额",
      "sql": "SELECT region, MONTH(order_date) as month, SUM(amount) as sales FROM orders WHERE order_date >= DATE_SUB(NOW(), INTERVAL 3 MONTH) GROUP BY region, month",
      "depends_on": []
    },
    {
      "id": 2,
      "type": "python_analysis",
      "description": "计算每个地区的增长率",
      "code": "# 计算增长率的Python代码",
      "depends_on": [1]
    },
    {
      "id": 3,
      "type": "report",
      "description": "生成对比报告",
      "depends_on": [2]
    }
  ]
}
"""


async def planner_node(state: AgentState) -> Dict[str, Any]:
    """
    计划生成节点

    分析用户查询的复杂度，如果是复杂查询则生成多步骤计划

    Args:
        state: 工作流状态

    Returns:
        更新后的状态
    """
    user_query = state.get("rewritten_query") or state["user_query"]
    schema = state.get("schema", "")
    recalled_knowledge = state.get("recalled_knowledge", "")

    logger.info(f"[Planner] Analyzing query complexity: {user_query}")

    try:
        llm = get_llm_client()

        # 构建提示
        user_prompt = f"""数据库结构:
{schema}

{recalled_knowledge}

用户查询: {user_query}

请分析这个查询是否需要多步骤执行。如果是简单查询（单个SQL即可完成），返回：
{{"simple": true}}

如果是复杂查询（需要多步骤），生成执行计划并返回 JSON。"""

        response = await llm.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0
        )

        plan_text = response.choices[0].message.content.strip()

        # 清理 markdown 代码块
        if plan_text.startswith("```json"):
            plan_text = plan_text[7:]
        if plan_text.startswith("```"):
            plan_text = plan_text[3:]
        if plan_text.endswith("```"):
            plan_text = plan_text[:-3]
        plan_text = plan_text.strip()

        # 解析 JSON
        plan = json.loads(plan_text)

        # 检查是否是简单查询
        if plan.get("simple"):
            logger.info("[Planner] Simple query, no plan needed")
            return {
                "is_complex_query": False,
                "query_plan": None
            }

        # 复杂查询，返回计划
        logger.info(f"[Planner] Complex query, generated {len(plan.get('steps', []))} steps")

        return {
            "is_complex_query": True,
            "query_plan": plan
        }

    except Exception as e:
        logger.error(f"[Planner] Error: {e}")
        # 出错时当作简单查询处理
        return {
            "is_complex_query": False,
            "query_plan": None
        }
