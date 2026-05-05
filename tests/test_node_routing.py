"""
节点路由测试 — PlanExecutor, HumanFeedback, Intent 路由
"""
import json
import pytest
from app.workflows.nodes.plan_executor import (
    route_after_plan_executor,
    plan_executor_node,
    _validate_plan,
    SQL_GENERATE_NODE,
    PYTHON_GENERATE_NODE,
    REPORT_GENERATOR_NODE,
    HUMAN_FEEDBACK_NODE,
)
from app.workflows.nodes.human_feedback_node import (
    route_after_human_feedback,
)
from app.workflows.graph import (
    route_after_intent,
    route_after_query_rewrite,
    route_after_schema_recall,
    route_after_sql_generate,
    route_after_semantic_check,
    route_after_sql_execute,
    route_after_python_execute,
)


def _state(**kwargs):
    return dict(kwargs)


VALID_PLAN = {
    "thought_process": "分析用户数据",
    "execution_plan": [
        {"step": 1, "tool_to_use": "SQL_GENERATE_NODE", "tool_parameters": {"instruction": "查询总量"}},
        {"step": 2, "tool_to_use": "REPORT_GENERATOR_NODE", "tool_parameters": {"summary_and_recommendations": "总结"}},
    ],
}


class TestPlanValidation:
    """Plan 结构校验"""

    def test_valid_plan(self):
        assert _validate_plan(VALID_PLAN) is None

    def test_empty_plan(self):
        assert _validate_plan({}) is not None
        assert _validate_plan(None) is not None

    def test_no_execution_steps(self):
        assert _validate_plan({"execution_plan": []}) is not None

    def test_invalid_tool_name(self):
        plan = {"execution_plan": [{"step": 1, "tool_to_use": "INVALID_NODE", "tool_parameters": {}}]}
        assert _validate_plan(plan) is not None

    def test_sql_missing_instruction(self):
        plan = {"execution_plan": [{"step": 1, "tool_to_use": "SQL_GENERATE_NODE", "tool_parameters": {}}]}
        assert _validate_plan(plan) is not None

    def test_python_missing_instruction(self):
        plan = {"execution_plan": [{"step": 1, "tool_to_use": "PYTHON_GENERATE_NODE", "tool_parameters": {}}]}
        assert _validate_plan(plan) is not None

    def test_report_missing_summary(self):
        plan = {"execution_plan": [{"step": 1, "tool_to_use": "REPORT_GENERATOR_NODE", "tool_parameters": {}}]}
        assert _validate_plan(plan) is not None

    def test_old_format_steps(self):
        """兼容旧格式: steps 而非 execution_plan"""
        plan = {"steps": [{"step": 1, "tool_to_use": "SQL_GENERATE_NODE", "tool_parameters": {"instruction": "x"}}]}
        assert _validate_plan(plan) is None


class TestPlanExecutorRouting:
    """PlanExecutor 条件路由"""

    def test_validation_passed_sql(self):
        state = _state(plan_validation_status=True, plan_next_node=SQL_GENERATE_NODE)
        assert route_after_plan_executor(state) == "sql_generate"

    def test_validation_passed_python(self):
        state = _state(plan_validation_status=True, plan_next_node=PYTHON_GENERATE_NODE)
        assert route_after_plan_executor(state) == "python_generate"

    def test_validation_passed_report(self):
        state = _state(plan_validation_status=True, plan_next_node=REPORT_GENERATOR_NODE)
        assert route_after_plan_executor(state) == "report_generator"

    def test_validation_passed_human_feedback(self):
        state = _state(plan_validation_status=True, plan_next_node=HUMAN_FEEDBACK_NODE)
        assert route_after_plan_executor(state) == "human_feedback"

    def test_validation_failed_repair(self):
        state = _state(plan_validation_status=False, plan_repair_count=1)
        assert route_after_plan_executor(state) == "planner"

    def test_validation_failed_max_repair(self):
        state = _state(plan_validation_status=False, plan_repair_count=4)
        assert route_after_plan_executor(state) == "end"

    def test_unknown_next_node_defaults_to_report(self):
        state = _state(plan_validation_status=True, plan_next_node="UNKNOWN")
        assert route_after_plan_executor(state) == "report_generator"

    def test_old_format_sql(self):
        state = _state(plan_validation_status=True, plan_next_node="sql_query")
        assert route_after_plan_executor(state) == "sql_generate"

    def test_old_format_python(self):
        state = _state(plan_validation_status=True, plan_next_node="python_analysis")
        assert route_after_plan_executor(state) == "python_generate"


class TestHumanFeedbackRouting:
    """HumanFeedback 条件路由"""

    def test_approve_goes_to_executor(self):
        state = _state(human_next_node="plan_executor")
        assert route_after_human_feedback(state) == "plan_executor"

    def test_reject_goes_to_planner(self):
        state = _state(human_next_node="planner")
        assert route_after_human_feedback(state) == "planner"

    def test_max_reject_goes_to_end(self):
        state = _state(human_next_node="end")
        assert route_after_human_feedback(state) == "end"

    def test_default_to_executor(self):
        state = _state()
        assert route_after_human_feedback(state) == "plan_executor"


class TestIntentRouting:
    """意图识别路由"""

    def test_data_analysis_goes_to_knowledge(self):
        state = _state(intent="data_analysis")
        assert route_after_intent(state) == "knowledge_recall"

    def test_chitchat_goes_to_end(self):
        state = _state(intent="chitchat")
        assert route_after_intent(state) == "end"


class TestQueryRewriteRouting:
    """查询重写路由"""

    def test_rewritten_goes_to_schema(self):
        state = _state(rewritten_query="SELECT ...")
        assert route_after_query_rewrite(state) == "schema_recall"

    def test_empty_goes_to_end(self):
        state = _state(rewritten_query="")
        assert route_after_query_rewrite(state) == "end"


class TestSchemaRecallRouting:
    """Schema 召回路由"""

    def test_schema_goes_to_table_relation(self):
        state = _state(schema="CREATE TABLE ...")
        assert route_after_schema_recall(state) == "table_relation"

    def test_empty_goes_to_end(self):
        state = _state(schema="")
        assert route_after_schema_recall(state) == "end"


class TestSQLRouting:
    """SQL 流水线路由"""

    def test_sql_generated_goes_to_semantic(self):
        state = _state(generated_sql="SELECT 1")
        assert route_after_sql_generate(state) == "semantic_consistency"

    def test_no_sql_retry(self):
        state = _state(generated_sql="", sql_generate_count=0)
        assert route_after_sql_generate(state) == "sql_generate"

    def test_sql_max_retry_ends(self):
        from app.core.config import settings
        state = _state(generated_sql="", sql_generate_count=settings.max_sql_retry_count)
        assert route_after_sql_generate(state) == "end"

    def test_semantic_passed(self):
        state = _state(semantic_consistency_result=True)
        assert route_after_semantic_check(state) == "sql_execute"

    def test_semantic_failed(self):
        state = _state(semantic_consistency_result=False)
        assert route_after_semantic_check(state) == "sql_generate"

    def test_sql_execute_success(self):
        state = _state(sql_error=None)
        assert route_after_sql_execute(state) == "plan_executor"

    def test_sql_execute_error_retry(self):
        state = _state(sql_error="syntax error", sql_generate_count=0)
        assert route_after_sql_execute(state) == "sql_generate"


class TestPythonRouting:
    """Python 流水线路由"""

    def test_success_goes_to_analyze(self):
        state = _state(python_is_success=True)
        assert route_after_python_execute(state) == "python_analyze"

    def test_failure_retry(self):
        state = _state(python_is_success=False, python_tries_count=0)
        assert route_after_python_execute(state) == "python_generate"

    def test_max_retry_fallback(self):
        from app.core.config import settings
        state = _state(python_is_success=False, python_tries_count=settings.code_executor.python_max_tries_count)
        assert route_after_python_execute(state) == "python_analyze"
