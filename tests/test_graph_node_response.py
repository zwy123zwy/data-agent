"""
GraphNodeResponse 序列化 & SSE 格式测试
对齐 Java GraphNodeResponse.java + ServerSentEvent
"""
import json
import pytest
from app.api.streaming_graph_controller import (
    _build_graph_response,
    _format_sse_data,
    _format_sse_event,
    NODE_NAME_MAP,
    TEXT_TYPE_SQL,
    TEXT_TYPE_JSON,
    TEXT_TYPE_HTML,
    TEXT_TYPE_MARK_DOWN,
    TEXT_TYPE_RESULT_SET,
    TEXT_TYPE_PYTHON,
    TEXT_TYPE_TEXT,
)


class TestGraphNodeResponse:
    """GraphNodeResponse schema 测试 — 对齐 Java GraphNodeResponse.java"""

    def test_all_fields_present(self):
        resp = _build_graph_response(
            agent_id=1, thread_id="uuid-123", node_name="SqlGenerateNode",
            text="SELECT 1", text_type="SQL",
        )
        assert set(resp.keys()) == {
            "agentId", "threadId", "nodeName", "textType", "text", "error", "complete"
        }

    def test_default_values(self):
        resp = _build_graph_response(agent_id=1, thread_id="t", node_name="n", text="x")
        assert resp["textType"] == "TEXT"
        assert resp["error"] is False
        assert resp["complete"] is False

    def test_error_flag(self):
        resp = _build_graph_response(agent_id=1, thread_id="t", node_name="", text="err", error=True)
        assert resp["error"] is True

    def test_complete_flag(self):
        resp = _build_graph_response(agent_id=1, thread_id="t", node_name="", text="", complete=True)
        assert resp["complete"] is True

    def test_agent_id_string(self):
        """agentId 序列化为 string 对齐 Java"""
        resp = _build_graph_response(agent_id=42, thread_id="t", node_name="n", text="x")
        assert resp["agentId"] == "42"

    def test_empty_thread_id(self):
        resp = _build_graph_response(agent_id=1, thread_id="", node_name="n", text="x")
        assert resp["threadId"] == ""


class TestSSEFormat:
    """SSE 格式测试"""

    def test_sse_data_format(self):
        data = {"agentId": "1", "text": "hello", "complete": False}
        sse = _format_sse_data(data)
        assert sse.startswith("data: ")
        assert sse.endswith("\n\n")
        assert "event:" not in sse
        parsed = json.loads(sse[6:-2])
        assert parsed == data

    def test_sse_event_format(self):
        data = {"complete": True}
        sse = _format_sse_event("complete", data)
        assert sse.startswith("event: complete\n")
        assert "data: " in sse
        assert sse.endswith("\n\n")
        # extract data part
        lines = sse.split("\n")
        data_line = [l for l in lines if l.startswith("data: ")][0]
        parsed = json.loads(data_line[6:])
        assert parsed == data

    def test_sse_event_error(self):
        data = {"error": True, "text": "something went wrong"}
        sse = _format_sse_event("error", data)
        assert sse.startswith("event: error\n")
        parsed = json.loads(sse.split("\n")[1][6:])
        assert parsed["error"] is True

    def test_sse_unicode_text(self):
        """SSE 中文字符不转义"""
        data = {"text": "数据分析完成"}
        sse = _format_sse_data(data)
        assert "数据分析完成" in sse
        assert "\\u" not in sse


class TestNodeNameMapping:
    """Python → Java 节点名映射"""

    def test_all_16_nodes_mapped(self):
        assert len(NODE_NAME_MAP) == 16

    def test_intent_node(self):
        assert NODE_NAME_MAP["intent_recognition"] == "IntentRecognitionNode"

    def test_knowledge_node(self):
        assert NODE_NAME_MAP["knowledge_recall"] == "EvidenceRecallNode"

    def test_query_rewrite_node(self):
        assert NODE_NAME_MAP["query_rewrite"] == "QueryEnhanceNode"

    def test_schema_node(self):
        assert NODE_NAME_MAP["schema_recall"] == "SchemaRecallNode"

    def test_table_relation_node(self):
        assert NODE_NAME_MAP["table_relation"] == "TableRelationNode"

    def test_feasibility_node(self):
        assert NODE_NAME_MAP["feasibility"] == "FeasibilityAssessmentNode"

    def test_planner_node(self):
        assert NODE_NAME_MAP["planner"] == "PlannerNode"

    def test_plan_executor_node(self):
        assert NODE_NAME_MAP["plan_executor"] == "PlanExecutorNode"

    def test_sql_nodes(self):
        assert NODE_NAME_MAP["sql_generate"] == "SqlGenerateNode"
        assert NODE_NAME_MAP["semantic_consistency"] == "SemanticConsistencyNode"
        assert NODE_NAME_MAP["sql_execute"] == "SqlExecuteNode"

    def test_python_nodes(self):
        assert NODE_NAME_MAP["python_generate"] == "PythonGenerateNode"
        assert NODE_NAME_MAP["python_execute"] == "PythonExecuteNode"
        assert NODE_NAME_MAP["python_analyze"] == "PythonAnalyzeNode"

    def test_report_node(self):
        assert NODE_NAME_MAP["report_generator"] == "ReportGeneratorNode"

    def test_human_feedback_node(self):
        assert NODE_NAME_MAP["human_feedback"] == "HumanFeedbackNode"

    def test_unknown_node_fallback(self):
        assert NODE_NAME_MAP.get("unknown_node", "unknown_node") == "unknown_node"


class TestTextType:
    """TextType 常量对齐"""

    def test_all_types_defined(self):
        assert TEXT_TYPE_SQL == "SQL"
        assert TEXT_TYPE_JSON == "JSON"
        assert TEXT_TYPE_HTML == "HTML"
        assert TEXT_TYPE_MARK_DOWN == "MARK_DOWN"
        assert TEXT_TYPE_RESULT_SET == "RESULT_SET"
        assert TEXT_TYPE_PYTHON == "PYTHON"
        assert TEXT_TYPE_TEXT == "TEXT"
