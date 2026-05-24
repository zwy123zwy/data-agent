# [阶段2] Harness Tool 链常量（不 import app.workflows）
# [Harness: Tool Access #1]
#
# NL2SQL_PLAN_JSON: smart_query 的固定执行计划 JSON。
#   当前 smart_query 是单步 NL2SQL（1 step × sql_execute），
#   与 V1 NL2SQL_PLAN 语义对齐。Phase 4 Planner 会生成多步动态计划替换此常量。
#
# NL2SQL_INSTRUCTION: 注入 generate_sql prompt 的步骤指令文本。

import json

# [阶段2] smart_query 单步 NL2SQL 计划（对齐 V1 NL2SQL_PLAN 语义）
_SMART_QUERY_PLAN = {
    "execution_plan": [
        {
            "step": 1,
            "tool": "sql_execute",
            "instruction": "根据用户问题查询相关数据",
            "tool_parameters": {},
        }
    ]
}

NL2SQL_PLAN_JSON: str = json.dumps(_SMART_QUERY_PLAN, ensure_ascii=False)
NL2SQL_INSTRUCTION: str = "根据用户问题查询相关数据"
