"""
HumanFeedback 回归测试 — 覆盖 approve / reject / 超限 三种场景

使用 LangGraph 的 Command(resume=...) 机制测试完整的 interrupt → resume 流程。

由于完整工作流需要走 intent → knowledge → rewrite → schema → ... → plan_executor → human_feedback
每个节点都调用 LLM，不适合单元测试。因此构建最小子图仅测试 HumanFeedback 核心流程。
"""

import json
import pytest
from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END

from app.workflows.state import WorkflowState
from app.workflows.nodes.plan_executor import plan_executor_node, route_after_plan_executor
from app.workflows.nodes.human_feedback_node import human_feedback_node, route_after_human_feedback


def _make_test_graph():
    """构建最小测试子图: plan_executor → human_feedback → (loop or END)

    拓扑:
      START → plan_executor → human_feedback (interrupt)
        → approve → plan_executor → (step routing: SQL → END, Report → END)
        → reject  → END
        → max_reject → END

    human_feedback_node.approve 会设置 human_review_enabled=False,
    之后 plan_executor 会按 step 路由到 SQL/Python/Report 而非回到 human_feedback.
    """
    g = StateGraph(WorkflowState)
    g.add_node("plan_executor", plan_executor_node)
    g.add_node("human_feedback", human_feedback_node)
    g.set_entry_point("plan_executor")
    g.add_conditional_edges("plan_executor", route_after_plan_executor, {
        "human_feedback": "human_feedback",
        "sql_generate": END,
        "python_generate": END,
        "report_generator": END,
        "end": END,
    })
    g.add_conditional_edges("human_feedback", route_after_human_feedback, {
        "plan_executor": "plan_executor",
        "planner": END,
        "end": END,
    })
    return g.compile(checkpointer=MemorySaver())


def _build_human_feedback_state(**overrides) -> dict:
    """构建触发 HumanFeedback 的初始 state

    plan_executor 检查 human_review_enabled=True → 路由到 human_feedback
    """
    plan = {
        "thought_process": "测试人工反馈流程",
        "execution_plan": [
            {"step": 1, "tool_to_use": "SQL_GENERATE_NODE",
             "tool_parameters": {"instruction": "查询数据"}},
            {"step": 2, "tool_to_use": "REPORT_GENERATOR_NODE",
             "tool_parameters": {"summary_and_recommendations": "生成报告"}},
        ],
    }
    state = {
        "agent_id": 3,
        "user_query": "测试人工反馈",
        "is_only_nl2sql": False,
        "human_review_enabled": True,
        "plan_repair_count": 0,
        "plan_current_step": 1,
        "query_plan": json.dumps(plan, ensure_ascii=False),
    }
    state.update(overrides)
    return state


class TestHumanFeedbackApprove:
    """场景 1: 用户 approve → 回到 plan_executor（循环）"""

    @pytest.mark.asyncio
    async def test_approve_continues_workflow(self):
        """审批通过后，路由回 plan_executor"""
        workflow = _make_test_graph()
        initial = _build_human_feedback_state()
        config = {"configurable": {"thread_id": "test-hf-approve-1"}}

        # 第一步：执行到 interrupt（human_feedback 节点内触发暂停）
        interrupted = False
        async for event in workflow.astream(initial, config, stream_mode="updates"):
            if "__interrupt__" in event:
                interrupted = True
                break

        assert interrupted, "Should have reached interrupt (human_feedback)"

        # 第二步：resume with approve → 应回到 plan_executor
        resume_cmd = Command(resume={"action": "approve"})
        node_names = []
        async for event in workflow.astream(resume_cmd, config, stream_mode="updates"):
            for name in event:
                node_names.append(name)

        assert "plan_executor" in node_names, \
            f"Should route to plan_executor after approve, got: {node_names}"

    @pytest.mark.asyncio
    async def test_approve_sets_correct_routing(self):
        """审批通过后，human_next_node 设置为 plan_executor"""
        workflow = _make_test_graph()
        initial = _build_human_feedback_state()
        config = {"configurable": {"thread_id": "test-hf-approve-2"}}

        async for event in workflow.astream(initial, config, stream_mode="updates"):
            if "__interrupt__" in event:
                break

        resume_cmd = Command(resume={"action": "approve"})
        async for event in workflow.astream(resume_cmd, config, stream_mode="updates"):
            for node_name, output in event.items():
                if node_name == "human_feedback":
                    assert output.get("human_next_node") == "plan_executor"
                    assert output.get("plan_validation_status") is True
                    return

        pytest.fail("HumanFeedback node not found after resume")


class TestHumanFeedbackReject:
    """场景 2: 用户 reject → END（最小图将 planner 映射到 END）"""

    @pytest.mark.asyncio
    async def test_reject_ends_workflow(self):
        """拒绝后路由到 planner → END（最小图内）"""
        workflow = _make_test_graph()
        initial = _build_human_feedback_state()
        config = {"configurable": {"thread_id": "test-hf-reject-1"}}

        async for event in workflow.astream(initial, config, stream_mode="updates"):
            if "__interrupt__" in event:
                break

        resume_cmd = Command(resume={"action": "reject", "reason": "查询不够全面"})
        node_names = []
        async for event in workflow.astream(resume_cmd, config, stream_mode="updates"):
            for name in event:
                node_names.append(name)

        # 最小图中 planner → END，human_feedback 输出后路由直接到 END
        # route_after_human_feedback 返回 "planner" → 图映射到 END
        assert "planner" not in node_names, \
            "Minimal graph maps planner→END, should not see planner node"

    @pytest.mark.asyncio
    async def test_reject_increments_repair_count(self):
        """拒绝后 plan_repair_count 递增"""
        workflow = _make_test_graph()
        initial = _build_human_feedback_state(plan_repair_count=0)
        config = {"configurable": {"thread_id": "test-hf-reject-2"}}

        async for event in workflow.astream(initial, config, stream_mode="updates"):
            if "__interrupt__" in event:
                break

        resume_cmd = Command(resume={"action": "reject", "reason": "不完整"})
        async for event in workflow.astream(resume_cmd, config, stream_mode="updates"):
            for node_name, output in event.items():
                if node_name == "human_feedback":
                    assert output.get("plan_repair_count") == 1
                    assert output.get("human_next_node") == "planner"
                    return

        pytest.fail("HumanFeedback node not found after resume")

    @pytest.mark.asyncio
    async def test_reject_with_reason_preserved(self):
        """拒绝原因被保留在 plan_validation_error 中"""
        workflow = _make_test_graph()
        initial = _build_human_feedback_state()
        config = {"configurable": {"thread_id": "test-hf-reject-3"}}

        async for event in workflow.astream(initial, config, stream_mode="updates"):
            if "__interrupt__" in event:
                break

        reason = "需要增加按地区分组的分析"
        resume_cmd = Command(resume={"action": "reject", "reason": reason})
        async for event in workflow.astream(resume_cmd, config, stream_mode="updates"):
            for node_name, output in event.items():
                if node_name == "human_feedback":
                    assert output.get("plan_validation_error") == reason
                    return

        pytest.fail("HumanFeedback node not found after resume")


class TestHumanFeedbackMaxReject:
    """场景 3: 多次 reject 超限 → END"""

    @pytest.mark.asyncio
    async def test_max_reject_ends_workflow(self):
        """拒绝次数达到 MAX_REJECT_COUNT(3) 后路由到 end"""
        workflow = _make_test_graph()
        initial = _build_human_feedback_state(plan_repair_count=2)
        config = {"configurable": {"thread_id": "test-hf-max-reject-1"}}

        async for event in workflow.astream(initial, config, stream_mode="updates"):
            if "__interrupt__" in event:
                break

        resume_cmd = Command(resume={"action": "reject", "reason": "还是不行"})
        async for event in workflow.astream(resume_cmd, config, stream_mode="updates"):
            for node_name, output in event.items():
                if node_name == "human_feedback":
                    assert output.get("human_next_node") == "end"
                    assert output.get("plan_repair_count") == 3
                    return

        pytest.fail("HumanFeedback node not found after resume")

    @pytest.mark.asyncio
    async def test_second_reject_still_to_planner(self):
        """第 2 次拒绝（count=1→2）仍在限制内，human_next_node=planner"""
        workflow = _make_test_graph()
        initial = _build_human_feedback_state(plan_repair_count=1)
        config = {"configurable": {"thread_id": "test-hf-max-reject-2"}}

        async for event in workflow.astream(initial, config, stream_mode="updates"):
            if "__interrupt__" in event:
                break

        resume_cmd = Command(resume={"action": "reject", "reason": "再改改"})
        async for event in workflow.astream(resume_cmd, config, stream_mode="updates"):
            for node_name, output in event.items():
                if node_name == "human_feedback":
                    assert output.get("human_next_node") == "planner", \
                        f"Reject #2 should route to planner, got {output.get('human_next_node')}"
                    assert output.get("plan_repair_count") == 2
                    return

        pytest.fail("HumanFeedback node not found after resume")


class TestHumanFeedbackRoutingDirect:
    """HumanFeedback 路由函数直接测试 — 补充覆盖"""

    def test_route_after_approve(self):
        from app.workflows.nodes.human_feedback_node import route_after_human_feedback
        assert route_after_human_feedback({"human_next_node": "plan_executor"}) == "plan_executor"

    def test_route_after_reject(self):
        from app.workflows.nodes.human_feedback_node import route_after_human_feedback
        assert route_after_human_feedback({"human_next_node": "planner"}) == "planner"

    def test_route_after_max_reject(self):
        from app.workflows.nodes.human_feedback_node import route_after_human_feedback
        assert route_after_human_feedback({"human_next_node": "end"}) == "end"

    def test_route_defaults_to_plan_executor(self):
        from app.workflows.nodes.human_feedback_node import route_after_human_feedback
        assert route_after_human_feedback({}) == "plan_executor"
        assert route_after_human_feedback({"human_next_node": "unknown"}) == "plan_executor"
