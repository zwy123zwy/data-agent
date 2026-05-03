"""
工作流控制器 — Human-in-the-Loop 的生命周期管理

【在系统中的地位】
  本控制器管理所有工作流运行时的生命周期状态 (running/paused/cancelled)。
  它是 Human Feedback 机制的底层支撑——当工作流需要人工审批时，
  WorkflowController 暂停执行、等待用户反馈、然后恢复或取消。

【模块连接】
  上游 (谁调用 WorkflowController):
    - api/streaming_graph_controller.py → 创建/管理 SSE 流式工作流
    - api/graph_controller.py           → 创建/管理同步工作流
    - workflows/nodes/human_feedback_node.py → 暂停等待人工反馈

  下游 (前端):
    - 前端通过 SSE event:paused 接收暂停通知
    - 前端通过 resume API 发送反馈后恢复执行

  Java 对应:
    WorkflowController ≈ LangGraph interrupt 机制 + WorkflowStateManager

【Human Feedback 流程】
  1. 用户发起查询 (humanFeedback=true)
  2. PlanExecutor → HumanFeedbackNode
  3. LangGraph interrupt 触发，工作流暂停
  4. WorkflowController 记录暂停状态 (status=paused)
  5. SSE event:paused 发送给前端
  6. 用户在前端审批/拒绝
  7. 前端再次调用 /api/stream/search?threadId=xxx&humanFeedbackContent=...
  8. Command(resume={...}) 恢复 LangGraph 执行
  9. approve → 继续执行 / reject → 重新规划
"""
from typing import Dict, Optional, Any
from datetime import datetime
import asyncio
import uuid
import logging

logger = logging.getLogger(__name__)


class WorkflowRunState:
    """工作流运行状态"""

    def __init__(self, workflow_id: str, agent_id: int, query: str):
        self.workflow_id = workflow_id
        self.agent_id = agent_id
        self.query = query
        self.status = "running"  # running, paused, completed, cancelled, error
        self.current_node = None
        self.state_data: Dict[str, Any] = {}
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.pause_event: Optional[asyncio.Event] = None
        self.cancel_event: Optional[asyncio.Event] = None
        self.feedback_data: Optional[Dict[str, Any]] = None


class WorkflowController:
    """工作流控制器"""

    def __init__(self):
        self.workflows: Dict[str, WorkflowRunState] = {}
        self.lock = asyncio.Lock()

    def create_workflow(self, agent_id: int, query: str) -> str:
        """创建工作流"""
        workflow_id = str(uuid.uuid4())
        state = WorkflowRunState(workflow_id, agent_id, query)
        self.workflows[workflow_id] = state
        logger.info(f"Created workflow: {workflow_id}")
        return workflow_id

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowRunState]:
        """获取工作流状态"""
        return self.workflows.get(workflow_id)

    async def pause_workflow(self, workflow_id: str) -> bool:
        """暂停工作流"""
        async with self.lock:
            state = self.get_workflow(workflow_id)
            if not state:
                return False

            if state.status != "running":
                return False

            state.status = "paused"
            state.pause_event = asyncio.Event()
            state.updated_at = datetime.now()
            logger.info(f"Paused workflow: {workflow_id}")
            return True

    async def resume_workflow(self, workflow_id: str, feedback: Optional[Dict[str, Any]] = None) -> bool:
        """恢复工作流"""
        async with self.lock:
            state = self.get_workflow(workflow_id)
            if not state:
                return False

            if state.status != "paused":
                return False

            state.status = "running"
            state.feedback_data = feedback
            state.updated_at = datetime.now()

            # 触发恢复事件
            if state.pause_event:
                state.pause_event.set()

            logger.info(f"Resumed workflow: {workflow_id}")
            return True

    async def cancel_workflow(self, workflow_id: str) -> bool:
        """取消工作流"""
        async with self.lock:
            state = self.get_workflow(workflow_id)
            if not state:
                return False

            if state.status in ["completed", "cancelled"]:
                return False

            state.status = "cancelled"
            state.updated_at = datetime.now()

            # 触发取消事件
            if state.cancel_event:
                state.cancel_event.set()

            # 如果是暂停状态，也要触发恢复事件
            if state.pause_event:
                state.pause_event.set()

            logger.info(f"Cancelled workflow: {workflow_id}")
            return True

    async def complete_workflow(self, workflow_id: str) -> bool:
        """完成工作流"""
        async with self.lock:
            state = self.get_workflow(workflow_id)
            if not state:
                return False

            state.status = "completed"
            state.updated_at = datetime.now()
            logger.info(f"Completed workflow: {workflow_id}")
            return True

    async def error_workflow(self, workflow_id: str, error: str) -> bool:
        """工作流错误"""
        async with self.lock:
            state = self.get_workflow(workflow_id)
            if not state:
                return False

            state.status = "error"
            state.state_data["error"] = error
            state.updated_at = datetime.now()
            logger.error(f"Workflow error: {workflow_id}, {error}")
            return True

    async def wait_for_resume(self, workflow_id: str, timeout: Optional[float] = None) -> bool:
        """等待工作流恢复"""
        state = self.get_workflow(workflow_id)
        if not state or not state.pause_event:
            return False

        try:
            if timeout:
                await asyncio.wait_for(state.pause_event.wait(), timeout=timeout)
            else:
                await state.pause_event.wait()

            # 检查是否被取消
            if state.status == "cancelled":
                return False

            return True
        except asyncio.TimeoutError:
            logger.warning(f"Workflow resume timeout: {workflow_id}")
            return False

    def update_node(self, workflow_id: str, node_name: str):
        """更新当前节点"""
        state = self.get_workflow(workflow_id)
        if state:
            state.current_node = node_name
            state.updated_at = datetime.now()

    def update_state_data(self, workflow_id: str, key: str, value: Any):
        """更新状态数据"""
        state = self.get_workflow(workflow_id)
        if state:
            state.state_data[key] = value
            state.updated_at = datetime.now()

    def get_state_data(self, workflow_id: str, key: str) -> Optional[Any]:
        """获取状态数据"""
        state = self.get_workflow(workflow_id)
        if state:
            return state.state_data.get(key)
        return None

    def get_feedback_data(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """获取反馈数据"""
        state = self.get_workflow(workflow_id)
        if state:
            return state.feedback_data
        return None

    def cleanup_workflow(self, workflow_id: str):
        """清理工作流"""
        if workflow_id in self.workflows:
            del self.workflows[workflow_id]
            logger.info(f"Cleaned up workflow: {workflow_id}")

    def list_workflows(self, status: Optional[str] = None) -> list:
        """列出工作流"""
        workflows = []
        for wf_id, state in self.workflows.items():
            if status is None or state.status == status:
                workflows.append({
                    "workflow_id": wf_id,
                    "agent_id": state.agent_id,
                    "query": state.query,
                    "status": state.status,
                    "current_node": state.current_node,
                    "created_at": state.created_at.isoformat(),
                    "updated_at": state.updated_at.isoformat()
                })
        return workflows


# 全局工作流控制器实例
_controller: Optional[WorkflowController] = None


def get_workflow_controller() -> WorkflowController:
    """获取工作流控制器实例"""
    global _controller
    if _controller is None:
        _controller = WorkflowController()
    return _controller
