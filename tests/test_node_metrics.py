"""
NodeMetrics 节点指标追踪测试
"""
import time
import json
import pytest
from app.services.node_metrics import NodeMetrics, NodeMetricsTracker


class TestNodeMetrics:
    """单个 NodeMetrics 对象"""

    def test_initial_state(self):
        m = NodeMetrics(thread_id="t1", agent_id=1, node_name="TestNode")
        assert m.thread_id == "t1"
        assert m.agent_id == "1"
        assert m.node_name == "TestNode"
        assert m.status == "running"
        assert m.duration_ms == 0
        assert m.error_type is None

    def test_start_sets_time(self):
        m = NodeMetrics(thread_id="t1", agent_id=1, node_name="N")
        m.start()
        assert m.start_time is not None
        assert "T" in m.start_time  # ISO format

    def test_finish_success(self):
        m = NodeMetrics(thread_id="t1", agent_id=1, node_name="N")
        m.start()
        time.sleep(0.01)
        m.finish("success")
        assert m.status == "success"
        assert m.end_time is not None
        assert m.duration_ms > 0

    def test_finish_error(self):
        m = NodeMetrics(thread_id="t1", agent_id=1, node_name="N")
        m.start()
        m.finish("error", error=ValueError("bad thing"))
        assert m.status == "error"
        assert m.error_type == "ValueError"
        assert "bad thing" in m.error_message

    def test_to_dict_fields(self):
        m = NodeMetrics(thread_id="t1", agent_id=42, node_name="SqlNode", session_id="s1")
        m.start()
        m.retry_count = 2
        m.finish("success")
        d = m.to_dict()
        assert d["threadId"] == "t1"
        assert d["agentId"] == "42"
        assert d["sessionId"] == "s1"
        assert d["nodeName"] == "SqlNode"
        assert d["status"] == "success"
        assert d["retryCount"] == 2
        assert d["durationMs"] >= 0  # may be 0 if start/finish in same ms
        assert d["startTime"]
        assert d["endTime"]
        assert d["errorType"] is None
        assert d["errorMessage"] is None

    def test_error_message_truncation(self):
        m = NodeMetrics(thread_id="t", agent_id=1, node_name="N")
        m.start()
        long_msg = "x" * 500
        m.finish("error", error=RuntimeError(long_msg))
        assert len(m.error_message) <= 200


class TestNodeMetricsTracker:
    """NodeMetricsTracker 收集器"""

    def test_empty_summary(self):
        t = NodeMetricsTracker("tid", 1)
        s = t.summary()
        assert s == {"totalNodes": 0}

    def test_multiple_nodes(self):
        t = NodeMetricsTracker("tid", 1, "sid")
        for name in ["IntentNode", "SqlNode", "PythonNode"]:
            m = t.start_node(name)
            m.finish("success")
        assert len(t.node_executions) == 3
        s = t.summary()
        assert s["totalNodes"] == 3
        assert s["succeeded"] == 3
        assert s["failed"] == 0
        assert s["threadId"] == "tid"
        assert s["sessionId"] == "sid"

    def test_mixed_status(self):
        t = NodeMetricsTracker("tid", 1)
        m1 = t.start_node("OkNode")
        m1.finish("success")
        m2 = t.start_node("FailNode")
        m2.finish("error")
        m3 = t.start_node("PausedNode")
        m3.finish("paused")
        s = t.summary()
        assert s["succeeded"] == 1
        assert s["failed"] == 1  # paused != failed, counts as non-success

    def test_duration_stats(self):
        t = NodeMetricsTracker("tid", 1)
        for name in ["A", "B", "C"]:
            m = t.start_node(name)
            time.sleep(0.01)
            m.finish("success")
        s = t.summary()
        assert s["totalDurationMs"] > 0
        assert s["avgDurationMs"] > 0
        assert s["maxDurationMs"] > 0
        assert s["maxDurationMs"] >= s["avgDurationMs"]
