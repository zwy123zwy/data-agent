"""
回归样例测试 — 8 类场景的路由和状态转换验证

覆盖:
  1. 单表查询        — SQL only, 简单 Plan
  2. 多表 Join       — TableRelation 发现多表关系
  3. 指标口径查询    — 语义模型映射, 复杂 SQL
  4. 趋势分析        — SQL + Python 双步骤
  5. 图表分析        — Python 生成图表
  6. 不可回答问题    — Schema 不匹配 → 不可行
  7. 闲聊问题        — 意图识别为 chitchat
  8. 多轮追问        — 多轮上下文, 查询改写
"""
import json
import pytest
from app.workflows.graph import (
    route_after_intent,
    route_after_query_rewrite,
    route_after_schema_recall,
    route_after_feasibility,
)
from app.workflows.nodes.plan_executor import (
    route_after_plan_executor,
    _validate_plan,
    SQL_GENERATE_NODE,
    PYTHON_GENERATE_NODE,
    REPORT_GENERATOR_NODE,
)
from app.workflows.nodes.human_feedback_node import route_after_human_feedback
from app.workflows.state import get_canonical_query


def _state(**kw):
    return dict(kw)


class TestSingleTableQuery:
    """1. 单表查询 — 用户查询单表聚合"""

    def test_intent_is_data_analysis(self):
        s = _state(intent="data_analysis")
        assert route_after_intent(s) == "knowledge_recall"

    def test_simple_plan_single_sql_step(self):
        plan = {
            "thought_process": "查询 orders 表的总金额",
            "execution_plan": [
                {"step": 1, "tool_to_use": "SQL_GENERATE_NODE",
                 "tool_parameters": {"instruction": "查询本月订单总额"}},
                {"step": 2, "tool_to_use": "REPORT_GENERATOR_NODE",
                 "tool_parameters": {"summary_and_recommendations": "总结订单金额"}},
            ],
        }
        assert _validate_plan(plan) is None
        s = _state(plan_validation_status=True, plan_next_node=SQL_GENERATE_NODE)
        assert route_after_plan_executor(s) == "sql_generate"


class TestMultiTableJoin:
    """2. 多表 Join — TableRelation 已发现多表关系"""

    def test_schema_with_relations_routes_correctly(self):
        s = _state(schema="CREATE TABLE orders (...); CREATE TABLE users (...)")
        assert route_after_schema_recall(s) == "table_relation"

    def test_multi_table_plan_valid(self):
        plan = {
            "thought_process": "需要 join orders 和 users 表",
            "execution_plan": [
                {"step": 1, "tool_to_use": "SQL_GENERATE_NODE",
                 "tool_parameters": {"instruction": "JOIN orders 和 users, 按用户汇总订单金额"}},
                {"step": 2, "tool_to_use": "REPORT_GENERATOR_NODE",
                 "tool_parameters": {"summary_and_recommendations": "汇总多表分析结果"}},
            ],
        }
        assert _validate_plan(plan) is None


class TestMetricQuery:
    """3. 指标口径查询 — 语义模型映射业务术语"""

    def test_rewritten_query_takes_priority(self):
        s = {
            "rewritten_query": "SELECT SUM(amount) FROM orders WHERE status='paid'",
            "canonical_query": "",
            "user_query": "本月销售额",
        }
        assert "SUM" in get_canonical_query(s)

    def test_complex_metric_plan(self):
        plan = {
            "thought_process": "计算毛利率: (收入-成本)/收入",
            "execution_plan": [
                {"step": 1, "tool_to_use": "SQL_GENERATE_NODE",
                 "tool_parameters": {"instruction": "计算总收入、总成本、毛利率"}},
                {"step": 2, "tool_to_use": "REPORT_GENERATOR_NODE",
                 "tool_parameters": {"summary_and_recommendations": "毛利率分析报告"}},
            ],
        }
        assert _validate_plan(plan) is None


class TestTrendAnalysis:
    """4. 趋势分析 — SQL + Python 双步骤"""

    def test_trend_plan_has_sql_and_python(self):
        plan = {
            "thought_process": "先按月汇总数据，再用 Python 做趋势拟合",
            "execution_plan": [
                {"step": 1, "tool_to_use": "SQL_GENERATE_NODE",
                 "tool_parameters": {"instruction": "按月汇总销售额"}},
                {"step": 2, "tool_to_use": "PYTHON_GENERATE_NODE",
                 "tool_parameters": {"instruction": "用线性回归拟合月度趋势，计算增长率"}},
                {"step": 3, "tool_to_use": "REPORT_GENERATOR_NODE",
                 "tool_parameters": {"summary_and_recommendations": "趋势分析报告"}},
            ],
        }
        assert _validate_plan(plan) is None

    def test_python_step_routes_correctly(self):
        s = _state(plan_validation_status=True, plan_next_node=PYTHON_GENERATE_NODE)
        assert route_after_plan_executor(s) == "python_generate"


class TestChartAnalysis:
    """5. 图表分析 — Python 生成 ECharts 配置"""

    def test_chart_plan_with_python(self):
        plan = {
            "thought_process": "用 Python 生成柱状图和饼图",
            "execution_plan": [
                {"step": 1, "tool_to_use": "SQL_GENERATE_NODE",
                 "tool_parameters": {"instruction": "按类别汇总销量"}},
                {"step": 2, "tool_to_use": "PYTHON_GENERATE_NODE",
                 "tool_parameters": {"instruction": "生成柱状图展示各类别销量, 饼图展示占比"}},
                {"step": 3, "tool_to_use": "REPORT_GENERATOR_NODE",
                 "tool_parameters": {"summary_and_recommendations": "带图表的分析报告"}},
            ],
        }
        assert _validate_plan(plan) is None


class TestUnanswerableQuestion:
    """6. 不可回答问题 — Schema 不匹配"""

    def test_empty_schema_routes_to_end(self):
        s = _state(schema="")
        assert route_after_schema_recall(s) == "end"

    def test_infeasible_routes_to_end(self):
        s = _state(feasibility_result={"feasible": False, "reason": "表结构不包含所需字段"})
        from app.workflows.nodes.feasibility import route_after_feasibility
        assert route_after_feasibility(s) == "end"

    def test_rewrite_empty_routes_to_end(self):
        s = _state(rewritten_query="")
        assert route_after_query_rewrite(s) == "end"


class TestChitchat:
    """7. 闲聊问题 — 意图识别拒绝"""

    def test_chitchat_routes_to_end(self):
        s = _state(intent="chitchat")
        assert route_after_intent(s) == "end"

    def test_chitchat_does_not_enter_analysis_pipeline(self):
        """闲聊不会触发 knowledge_recall"""
        s = _state(intent="chitchat")
        next_node = route_after_intent(s)
        assert next_node != "knowledge_recall"
        assert next_node == "end"


class TestMultiTurnConversation:
    """8. 多轮追问 — 上下文注入 + 查询改写"""

    def test_multi_turn_context_preserved(self):
        """多轮上下文影响查询改写"""
        s = {
            "user_query": "那上个月呢？",
            "multi_turn_context": "上一轮: 查询本月销售额为 100 万",
            "rewritten_query": "查询上个月的销售总额",
        }
        assert get_canonical_query(s) == "查询上个月的销售总额"

    def test_follow_up_plan_different_from_original(self):
        """追问生成的 Plan 与原始不同"""
        plan = {
            "thought_process": "用户追问上个月数据，只需单步 SQL",
            "execution_plan": [
                {"step": 1, "tool_to_use": "SQL_GENERATE_NODE",
                 "tool_parameters": {"instruction": "查询上个月销售总额"}},
                {"step": 2, "tool_to_use": "REPORT_GENERATOR_NODE",
                 "tool_parameters": {"summary_and_recommendations": "上个月销售总结"}},
            ],
        }
        assert _validate_plan(plan) is None

    def test_rewritten_with_context_routes_to_schema(self):
        s = _state(rewritten_query="查询上个月销售额按地区分组")
        assert route_after_query_rewrite(s) == "schema_recall"


class TestHumanFeedbackRegression:
    """HumanFeedback 回归: approve / reject / 超限"""

    def test_approve_goes_to_executor(self):
        s = _state(human_next_node="plan_executor")
        assert route_after_human_feedback(s) == "plan_executor"

    def test_reject_goes_to_planner(self):
        s = _state(human_next_node="planner")
        assert route_after_human_feedback(s) == "planner"

    def test_max_reject_goes_to_end(self):
        s = _state(human_next_node="end")
        assert route_after_human_feedback(s) == "end"
