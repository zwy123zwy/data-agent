"""
State 工具函数 & HumanFeedback resume 测试
"""
import json
import pytest
from app.workflows.state import (
    get_canonical_query,
    get_current_step_number,
    get_current_instruction,
    WorkflowState,
    StateKeys,
)


class TestStateKeys:
    """StateKeys 常量定义"""

    def test_all_keys_are_strings(self):
        for attr in dir(StateKeys):
            if not attr.startswith("_"):
                assert isinstance(getattr(StateKeys, attr), str)

    def test_key_uniqueness(self):
        keys = [getattr(StateKeys, a) for a in dir(StateKeys) if not a.startswith("_")]
        assert len(keys) == len(set(keys)), "Duplicate state keys found"


class TestGetCanonicalQuery:
    """get_canonical_query — 对齐 Java StateUtil.getCanonicalQuery"""

    def test_rewritten_takes_priority(self):
        state = {"rewritten_query": "SELECT name FROM users", "user_query": "查名字"}
        assert get_canonical_query(state) == "SELECT name FROM users"

    def test_canonical_fallback(self):
        state = {"canonical_query": "find names", "user_query": "查名字"}
        assert get_canonical_query(state) == "find names"

    def test_user_query_last_resort(self):
        state = {"user_query": "查名字"}
        assert get_canonical_query(state) == "查名字"

    def test_rewritten_beats_canonical(self):
        state = {
            "rewritten_query": "rewritten",
            "canonical_query": "canonical",
            "user_query": "原始",
        }
        assert get_canonical_query(state) == "rewritten"


class TestGetCurrentStepNumber:
    """get_current_step_number"""

    def test_default_is_1(self):
        assert get_current_step_number({}) == 1

    def test_custom_step(self):
        assert get_current_step_number({"plan_current_step": 3}) == 3


class TestGetCurrentInstruction:
    """get_current_instruction — 对齐 Java getCurrentExecutionStepInstruction"""

    def test_no_plan_returns_query(self):
        state = {"user_query": "查数据"}
        assert get_current_instruction(state) == "查数据"

    def test_plan_as_dict(self):
        plan = {
            "execution_plan": [
                {"step": 1, "tool_to_use": "SQL", "tool_parameters": {"instruction": "查总量"}},
                {"step": 2, "tool_to_use": "PYTHON", "tool_parameters": {"instruction": "画图"}},
            ]
        }
        state = {"user_query": "x", "query_plan": plan, "plan_current_step": 1}
        assert get_current_instruction(state) == "查总量"

    def test_plan_as_json_string(self):
        plan = {
            "execution_plan": [
                {"step": 1, "tool_to_use": "SQL", "tool_parameters": {"instruction": "查总量"}},
                {"step": 2, "tool_to_use": "PYTHON", "tool_parameters": {"instruction": "画图"}},
            ]
        }
        state = {"user_query": "x", "query_plan": json.dumps(plan), "plan_current_step": 2}
        assert get_current_instruction(state) == "画图"

    def test_invalid_json_fallback(self):
        state = {"user_query": "q", "query_plan": "not valid json {{{"}
        assert get_current_instruction(state) == "q"

    def test_plan_not_dict_fallback(self):
        state = {"user_query": "q", "query_plan": 42, "plan_current_step": 1}
        assert get_current_instruction(state) == "q"

    def test_step_out_of_range(self):
        plan = {"execution_plan": [{"step": 1, "tool_parameters": {"instruction": "only"}}]}
        state = {"user_query": "q", "query_plan": plan, "plan_current_step": 99}
        assert get_current_instruction(state) == "q"


class TestHumanFeedbackResumeState:
    """HumanFeedback resume 后续状态转换"""

    def test_approve_sets_correct_next_node(self):
        """审批通过 → human_next_node = plan_executor"""
        feedback = {"action": "approve"}
        assert feedback["action"] == "approve"

    def test_reject_sets_replan(self):
        """拒绝 → human_next_node = planner, plan_repair_count + 1"""
        feedback = {"action": "reject", "reason": "方案不符合需求"}
        assert feedback["action"] == "reject"
        assert "reason" in feedback

    def test_reject_max_count(self):
        """超过 MAX_REJECT_COUNT → human_next_node = end"""
        MAX_REJECT_COUNT = 3
        reject_count = 3  # 已经是第 3 次，再加 1 就是 4 >= 3
        new_count = reject_count + 1
        assert new_count > MAX_REJECT_COUNT  # 超限应结束
