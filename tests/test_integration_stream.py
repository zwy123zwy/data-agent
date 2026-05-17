"""
集成测试 — SSE 流式协议和会话 API

运行前确保服务已启动: uvicorn app.main:app --host 0.0.0.0 --port 8200
"""

import requests
import json
import time
import pytest

BASE_URL = "http://localhost:8200"
AGENT_ID = 3


def _parse_sse_lines(response) -> list[dict]:
    """解析 SSE 响应为事件列表"""
    events = []
    current_data = None
    current_event = None
    for line in response.iter_lines(decode_unicode=True):
        if not line:
            if current_data is not None:
                events.append({
                    "event": current_event or "message",
                    "data": json.loads(current_data),
                })
                current_data = None
                current_event = None
            continue
        if line.startswith("event: "):
            current_event = line[7:]
        elif line.startswith("data: "):
            current_data = line[6:]
    return events


class TestSSEStreamNormalComplete:
    """集成测试: GET /api/stream/search 正常完成"""

    def test_simple_query_completes(self):
        """简单数据查询能正常完成并收到 complete 事件"""
        response = requests.get(
            f"{BASE_URL}/api/stream/search",
            params={"agentId": AGENT_ID, "query": "查询订单总金额"},
            stream=True,
            timeout=300,
        )
        assert response.status_code == 200
        events = _parse_sse_lines(response)
        assert len(events) >= 2, f"Expected >=2 events, got {len(events)}: {[e['event'] for e in events]}"

        last_event = events[-1]
        assert last_event["event"] == "complete"
        assert last_event["data"]["complete"] is True

    def test_sse_data_has_required_fields(self):
        """每个 data 事件包含 GraphNodeResponse 全部字段"""
        response = requests.get(
            f"{BASE_URL}/api/stream/search",
            params={"agentId": AGENT_ID, "query": "查询订单总金额"},
            stream=True,
            timeout=300,
        )
        assert response.status_code == 200
        events = _parse_sse_lines(response)

        for evt in events:
            d = evt["data"]
            assert "agentId" in d, f"Missing agentId in {d}"
            assert "threadId" in d, f"Missing threadId in {d}"
            assert "nodeName" in d, f"Missing nodeName in {d}"
            assert "textType" in d, f"Missing textType in {d}"
            assert "text" in d, f"Missing text in {d}"
            assert "error" in d, f"Missing error in {d}"
            assert "complete" in d, f"Missing complete in {d}"

    def test_chitchat_ends_immediately(self):
        """闲聊问题立即结束，不进入分析管道"""
        response = requests.get(
            f"{BASE_URL}/api/stream/search",
            params={"agentId": AGENT_ID, "query": "你好"},
            stream=True,
            timeout=60,
        )
        assert response.status_code == 200
        events = _parse_sse_lines(response)
        assert len(events) == 2, f"Expected 2 events, got {len(events)}"
        assert events[0]["data"]["nodeName"] == "IntentRecognitionNode"
        assert events[1]["event"] == "complete"

    def test_node_names_are_java_compatible(self):
        """所有 nodeName 使用 Java 兼容名称（驼峰 + Node 后缀）"""
        response = requests.get(
            f"{BASE_URL}/api/stream/search",
            params={"agentId": AGENT_ID, "query": "查询订单总金额"},
            stream=True,
            timeout=300,
        )
        assert response.status_code == 200
        events = _parse_sse_lines(response)
        java_nodes = {
            "IntentRecognitionNode", "EvidenceRecallNode", "QueryEnhanceNode",
            "SchemaRecallNode", "TableRelationNode", "FeasibilityAssessmentNode",
            "PlannerNode", "PlanExecutorNode", "SqlGenerateNode",
            "SemanticConsistencyNode", "SqlExecuteNode", "PythonGenerateNode",
            "PythonExecuteNode", "PythonAnalyzeNode", "ReportGeneratorNode",
            "HumanFeedbackNode",
        }
        for evt in events:
            node_name = evt["data"].get("nodeName", "")
            if node_name:
                assert node_name in java_nodes, f"Unknown nodeName: {node_name}"


class TestSSEContentTypes:
    """集成测试: SSE textType 正确性"""

    def test_sql_node_has_sql_type(self):
        """SqlGenerateNode 输出 textType=SQL"""
        response = requests.get(
            f"{BASE_URL}/api/stream/search",
            params={"agentId": AGENT_ID, "query": "查询订单总金额"},
            stream=True,
            timeout=300,
        )
        assert response.status_code == 200
        events = _parse_sse_lines(response)
        sql_events = [e for e in events if e["data"]["nodeName"] == "SqlGenerateNode"]
        assert len(sql_events) >= 1, "No SqlGenerateNode events"
        for e in sql_events:
            assert e["data"]["textType"] == "SQL", f"Expected SQL, got {e['data']['textType']}"

    def test_result_set_has_result_set_type(self):
        """SqlExecuteNode 输出 textType=RESULT_SET"""
        response = requests.get(
            f"{BASE_URL}/api/stream/search",
            params={"agentId": AGENT_ID, "query": "查询订单总金额"},
            stream=True,
            timeout=300,
        )
        assert response.status_code == 200
        events = _parse_sse_lines(response)
        exec_events = [e for e in events if e["data"]["nodeName"] == "SqlExecuteNode"]
        if exec_events:
            for e in exec_events:
                if not e["data"].get("error"):
                    assert e["data"]["textType"] == "RESULT_SET"

    def test_progress_nodes_have_text_type(self):
        """中间节点进度输出 textType=TEXT"""
        response = requests.get(
            f"{BASE_URL}/api/stream/search",
            params={"agentId": AGENT_ID, "query": "查询订单总金额"},
            stream=True,
            timeout=300,
        )
        assert response.status_code == 200
        events = _parse_sse_lines(response)
        text_nodes = {"IntentRecognitionNode", "EvidenceRecallNode", "QueryEnhanceNode",
                       "SchemaRecallNode", "FeasibilityAssessmentNode", "PlannerNode"}
        for evt in events:
            if evt["data"]["nodeName"] in text_nodes:
                assert evt["data"]["textType"] == "TEXT", \
                    f"{evt['data']['nodeName']} expected TEXT, got {evt['data']['textType']}"


class TestSessionAndMessageAPI:
    """集成测试: 会话和消息 API"""

    def test_create_and_delete_session(self):
        """创建会话 → 删除会话"""
        resp = requests.post(f"{BASE_URL}/api/agent/{AGENT_ID}/sessions", json={})
        assert resp.status_code in (200, 201)
        data = resp.json()
        session_id = data["id"]
        assert data["agentId"] == AGENT_ID

        # 删除
        resp = requests.delete(f"{BASE_URL}/api/sessions/{session_id}")
        assert resp.status_code in (200, 201)

    def test_rename_session(self):
        """重命名会话"""
        resp = requests.post(f"{BASE_URL}/api/agent/{AGENT_ID}/sessions", json={})
        session_id = resp.json()["id"]

        resp = requests.put(
            f"{BASE_URL}/api/sessions/{session_id}/rename",
            params={"title": "集成测试标题"},
        )
        assert resp.status_code in (200, 201)
        assert resp.json()["success"] is True

        requests.delete(f"{BASE_URL}/api/sessions/{session_id}")

    def test_pin_session(self):
        """置顶/取消置顶会话"""
        resp = requests.post(f"{BASE_URL}/api/agent/{AGENT_ID}/sessions", json={})
        session_id = resp.json()["id"]

        # 置顶
        resp = requests.put(f"{BASE_URL}/api/sessions/{session_id}/pin?isPinned=true")
        assert resp.status_code in (200, 201)

        # 取消置顶
        resp = requests.put(f"{BASE_URL}/api/sessions/{session_id}/pin?isPinned=false")
        assert resp.status_code in (200, 201)

        requests.delete(f"{BASE_URL}/api/sessions/{session_id}")

    def test_list_sessions(self):
        """列出 Agent 会话"""
        resp = requests.get(f"{BASE_URL}/api/agent/{AGENT_ID}/sessions")
        assert resp.status_code in (200, 201)
        sessions = resp.json()
        assert isinstance(sessions, list)


class TestMessageAPI:
    """集成测试: 消息 API"""

    def test_send_and_list_messages(self):
        """发送消息 → 查看消息列表"""
        resp = requests.post(f"{BASE_URL}/api/agent/{AGENT_ID}/sessions", json={})
        session_id = resp.json()["id"]

        # 发送消息
        resp = requests.post(
            f"{BASE_URL}/api/sessions/{session_id}/messages",
            json={"role": "user", "content": "测试消息", "messageType": "text"},
        )
        assert resp.status_code in (200, 201)

        # 查看消息
        resp = requests.get(f"{BASE_URL}/api/sessions/{session_id}/messages")
        assert resp.status_code in (200, 201)
        messages = resp.json()
        assert len(messages) >= 1
        assert messages[-1]["content"] == "测试消息"

        requests.delete(f"{BASE_URL}/api/sessions/{session_id}")

    def test_message_types(self):
        """验证 messageType 字段支持"""
        resp = requests.post(f"{BASE_URL}/api/agent/{AGENT_ID}/sessions", json={})
        session_id = resp.json()["id"]

        for msg_type in ["text", "html", "html-report", "markdown-report"]:
            resp = requests.post(
                f"{BASE_URL}/api/sessions/{session_id}/messages",
                json={"role": "assistant", "content": f"test {msg_type}", "messageType": msg_type},
            )
            assert resp.status_code in (200, 201), f"Failed for messageType={msg_type}"

        resp = requests.get(f"{BASE_URL}/api/sessions/{session_id}/messages")
        messages = resp.json()
        types_found = {m["messageType"] for m in messages}
        for msg_type in ["text", "html", "html-report", "markdown-report"]:
            assert msg_type in types_found, f"messageType {msg_type} not found"

        requests.delete(f"{BASE_URL}/api/sessions/{session_id}")


class TestReportDownload:
    """集成测试: 报告下载"""

    def test_html_report_download(self):
        """下载 HTML 报告"""
        resp = requests.post(f"{BASE_URL}/api/agent/{AGENT_ID}/sessions", json={})
        session_id = resp.json()["id"]

        # 先发一条消息
        requests.post(
            f"{BASE_URL}/api/sessions/{session_id}/messages",
            json={"role": "assistant", "content": "<p>test</p>", "messageType": "html"},
        )

        resp = requests.post(
            f"{BASE_URL}/api/sessions/{session_id}/reports/html",
            data="<h1>测试报告</h1><p>集成测试内容</p>",
            headers={"Content-Type": "text/plain"},
        )
        assert resp.status_code in (200, 201)
        assert "<h1>测试报告</h1>" in resp.text
        assert "content-type" in {k.lower(): v.lower() for k, v in resp.headers.items()}

        requests.delete(f"{BASE_URL}/api/sessions/{session_id}")


class TestSSEErrorHandling:
    """集成测试: SSE 错误处理"""

    def test_invalid_agent_returns_error(self):
        """不存在的 Agent 返回 error 事件"""
        response = requests.get(
            f"{BASE_URL}/api/stream/search",
            params={"agentId": 99999, "query": "test"},
            stream=True,
            timeout=30,
        )
        assert response.status_code == 200
        events = _parse_sse_lines(response)
        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) >= 1

    def test_empty_query_rejected(self):
        """空查询被拒绝 (422)"""
        response = requests.get(
            f"{BASE_URL}/api/stream/search",
            params={"agentId": AGENT_ID, "query": ""},
            stream=True,
            timeout=30,
        )
        assert response.status_code == 422


class TestMultiTurnQuery:
    """集成测试: 多轮对话"""

    def test_multi_turn_with_thread_id(self):
        """使用 threadId 实现多轮上下文"""
        # 第一轮
        resp1 = requests.get(
            f"{BASE_URL}/api/stream/search",
            params={"agentId": AGENT_ID, "query": "查询订单总金额"},
            stream=True,
            timeout=300,
        )
        events1 = _parse_sse_lines(resp1)
        thread_id = events1[0]["data"]["threadId"]
        assert events1[-1]["event"] == "complete"

        # 第二轮 — 使用同一个 threadId
        resp2 = requests.get(
            f"{BASE_URL}/api/stream/search",
            params={"agentId": AGENT_ID, "threadId": thread_id, "query": "那按月份分组呢"},
            stream=True,
            timeout=300,
        )
        events2 = _parse_sse_lines(resp2)
        assert len(events2) >= 2
        assert events2[-1]["event"] == "complete"
