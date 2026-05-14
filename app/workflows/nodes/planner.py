"""
计划生成节点 — 对齐 Java PlannerNode

【在系统中的地位】
  Planner 是工作流的"大脑"——它将用户的自然语言问题转化为结构化的
  多步骤执行计划 (JSON)，每个步骤指定要使用的工具和具体指令。

【模块连接】
  上游 (由谁路由到此):
    - feasibility → 可行性评估通过后路由而来
    - plan_executor → 计划校验失败时回来修复 (通过 human_feedback reject)

  下游 (写入 state):
    - state["query_plan"]       → 执行计划 JSON (execution_plan + thought_process)
    - state["is_complex_query"] → 是否多步骤 (超过1步为复杂查询)

  读取 state (LLM 生成计划需要的上下文):
    - state["schema"]              → 数据库 DDL 文本
    - state["recalled_knowledge"]  → 召回的知识
    - state["semantic_model_prompt"] → 语义模型 (字段别名)
    - state["plan_validation_error"] → 上次计划被拒绝的原因 (重规划时)

  路由 (graph.py):
    - planner → plan_executor (无条件，总是进入调度器)

  Java 对应:
    planner_node ≈ PlannerNode.java

【Plan JSON 结构】
  {
    "thought_process": "分析思路...",
    "execution_plan": [
      {"step": 1, "tool_to_use": "SQL_GENERATE_NODE", "tool_parameters": {"instruction": "..."}},
      {"step": 2, "tool_to_use": "PYTHON_GENERATE_NODE", "tool_parameters": {"instruction": "..."}},
      {"step": 3, "tool_to_use": "REPORT_GENERATOR_NODE", "tool_parameters": {"summary_and_recommendations": "..."}}
    ]
  }
"""
from typing import Dict, Any
from ..state import WorkflowState, get_canonical_query
from ...core.llm import llm_service
from ...core.text_utils import clean_code_block
from ...core.database import get_db
from ...services.prompt_config_service import PromptConfigService
import logging
import json

logger = logging.getLogger(__name__)

# 对齐 Java Constant 的节点名称
SQL_GENERATE_NODE = "SQL_GENERATE_NODE"
PYTHON_GENERATE_NODE = "PYTHON_GENERATE_NODE"
REPORT_GENERATOR_NODE = "REPORT_GENERATOR_NODE"

# NL2SQL Only 模式的预设 Plan JSON
NL2SQL_PLAN = {
    "thought_process": "根据问题生成SQL",
    "execution_plan": [
        {
            "step": 1,
            "tool_to_use": SQL_GENERATE_NODE,
            "tool_parameters": {
                "instruction": "SQL生成",
                "sql_query": None
            }
        }
    ]
}

PLANNER_SYSTEM_PROMPT = """你是一个数据分析计划生成专家。
根据用户的问题、数据库结构和已有知识，生成一个多步骤的执行计划。

可用工具类型:
- SQL_GENERATE_NODE: 生成并执行 SQL 查询
- PYTHON_GENERATE_NODE: 生成并执行 Python 数据分析代码
- REPORT_GENERATOR_NODE: 生成最终分析报告

要求:
1. 先在 thought_process 中简要描述你的分析思路，说明你检查了哪些表和字段
2. execution_plan 按逻辑顺序排列步骤
3. 每个步骤的 instruction 必须详细描述该步骤的具体需求（不要留空）
4. SQL_GENERATE_NODE 的 instruction 写详细的 SQL 需求描述（不写具体 SQL）
5. PYTHON_GENERATE_NODE 的 instruction 写详细的编程需求
6. REPORT_GENERATOR_NODE 必须包含 summary_and_recommendations 字段（报告大纲）
7. 步骤编号 step 从 1 开始递增

返回 JSON 格式（不要用 markdown 代码块包裹）:
{
  "thought_process": "简要描述你的分析思路。必须明确提到你检查了哪些表和字段",
  "execution_plan": [
    {
      "step": 1,
      "tool_to_use": "SQL_GENERATE_NODE",
      "tool_parameters": {
        "instruction": "详细的SQL需求描述..."
      }
    },
    {
      "step": 2,
      "tool_to_use": "PYTHON_GENERATE_NODE",
      "tool_parameters": {
        "instruction": "详细的编程需求描述..."
      }
    },
    {
      "step": 3,
      "tool_to_use": "REPORT_GENERATOR_NODE",
      "tool_parameters": {
        "summary_and_recommendations": "报告的大纲、需要回答的关键问题和建议方向"
      }
    }
  ]
}
"""


def _build_user_prompt(canonical_query: str, validation_error: str | None,
                       state: WorkflowState) -> str:
    """构建用户提示 — 对齐 Java PlannerNode.buildUserPrompt"""
    if validation_error is None:
        return canonical_query

    previous_plan = json.dumps(state.get("query_plan", {}), ensure_ascii=False, indent=2)
    return (
        f"IMPORTANT: User rejected previous plan with feedback: \"{validation_error}\"\n\n"
        f"Original question: {canonical_query}\n\n"
        f"Previous rejected plan:\n{previous_plan}\n\n"
        f"CRITICAL: Generate new plan incorporating user feedback (\"{validation_error}\")"
    )


async def _load_planner_prompt(agent_id: int) -> str:
    """加载 Planner 自定义 Prompt — 对齐 Java PlannerNode 使用 UserPromptConfig"""
    try:
        async for db in get_db():
            configs = await PromptConfigService.get_active_all_by_type(
                db, "planner", agent_id=agent_id
            )
            if configs:
                optimizations = "\n\n".join(c.system_prompt for c in configs if c.system_prompt)
                if optimizations:
                    return PLANNER_SYSTEM_PROMPT + "\n\n## 自定义优化规则\n" + optimizations
    except Exception:
        pass
    return PLANNER_SYSTEM_PROMPT


async def planner_node(state: WorkflowState) -> Dict[str, Any]:
    """计划生成节点 — 对齐 Java PlannerNode.apply()

    生成 Plan 对象（JSON），包含 thought_process 和 execution_plan。
    Planner 不直接生成 SQL，仅在 instruction 中描述需求。
    """
    # NL2SQL Only 模式 — 使用预设 Plan
    if state.get("is_only_nl2sql"):
        logger.info("[Planner] NL2SQL Only mode, using preset plan")
        return {"query_plan": json.dumps(NL2SQL_PLAN, ensure_ascii=False)}

    canonical_query = get_canonical_query(state)
    agent_id = state.get("agent_id", 0)
    logger.info(f"[Planner] Using processed query for planning: {canonical_query}")

    # 检查是否为修复模式
    validation_error = state.get("plan_validation_error")
    if validation_error:
        logger.info(f"[Planner] Regenerating plan with user feedback: {validation_error}")

    # 构建 prompt
    schema = state.get("schema", "")
    semantic_model = state.get("semantic_model_prompt", "")
    evidence = state.get("recalled_knowledge", "")
    user_prompt = _build_user_prompt(canonical_query, validation_error, state)

    try:
        # 对齐 Java: 从 DB 加载自定义 Planner Prompt
        system_prompt = await _load_planner_prompt(agent_id)
        if validation_error:
            system_prompt += (
                f"\n\n**USER FEEDBACK (CRITICAL)**: {validation_error}\n"
                f"**Must incorporate this feedback.**"
            )

        full_user_prompt = (
            f"用户问题: {user_prompt}\n\n"
            f"数据库结构:\n{schema}\n\n"
            f"语义模型:\n{semantic_model}\n\n"
            f"知识证据:\n{evidence}\n\n"
            f"请生成执行计划。"
        )

        response = await llm_service.chat(system_prompt, full_user_prompt, temperature=0.0)
        plan_text = clean_code_block(response, lang="json")
        plan = json.loads(plan_text)

        # 校验 Plan 结构
        if "execution_plan" not in plan or not plan["execution_plan"]:
            logger.warning("[Planner] Generated plan has no execution_plan, creating default")
            plan = {
                "thought_process": "用户提出了一个数据分析问题",
                "execution_plan": [
                    {
                        "step": 1,
                        "tool_to_use": SQL_GENERATE_NODE,
                        "tool_parameters": {"instruction": canonical_query}
                    },
                    {
                        "step": 2,
                        "tool_to_use": REPORT_GENERATOR_NODE,
                        "tool_parameters": {"summary_and_recommendations": "根据查询结果生成分析报告"}
                    }
                ]
            }

        steps = plan.get("execution_plan", [])
        logger.info(f"[Planner] Generated plan with {len(steps)} steps: {plan.get('thought_process', '')[:80]}")

        # 如果是简单查询（单步 SQL），转成 Plan 格式
        return {
            "query_plan": json.dumps(plan, ensure_ascii=False),
            "is_complex_query": len(steps) > 1,
        }

    except Exception as e:
        logger.error(f"[Planner] Error: {e}")
        # 降级：生成默认的单步 SQL Plan
        default_plan = {
            "thought_process": "简单地根据用户问题查询数据",
            "execution_plan": [
                {
                    "step": 1,
                    "tool_to_use": SQL_GENERATE_NODE,
                    "tool_parameters": {"instruction": canonical_query}
                }
            ]
        }
        return {
            "query_plan": json.dumps(default_plan, ensure_ascii=False),
            "is_complex_query": False,
        }
