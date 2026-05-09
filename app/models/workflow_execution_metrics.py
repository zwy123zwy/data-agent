"""工作流执行指标 — 每次流式查询结束后记录聚合指标，支撑 10 个核心指标的落地"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Boolean, Float, Text
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


class WorkflowExecutionMetrics(Base):
    """每次 /api/stream/search 执行完成后写入一条记录"""

    __tablename__ = "workflow_execution_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(String(36), index=True, comment="工作流线程ID")
    agent_id: Mapped[int] = mapped_column(Integer, index=True, comment="Agent ID")
    session_id: Mapped[Optional[str]] = mapped_column(String(36), default="", comment="会话ID")
    status: Mapped[str] = mapped_column(String(20), default="success", comment="success/error/paused")

    # --- E2E 耗时 (支撑 P50/P90/P99) ---
    total_duration_ms: Mapped[int] = mapped_column(Integer, default=0, comment="端到端总耗时ms")
    total_nodes: Mapped[int] = mapped_column(Integer, default=0)
    succeeded_nodes: Mapped[int] = mapped_column(Integer, default=0)
    failed_nodes: Mapped[int] = mapped_column(Integer, default=0)

    # --- 节点级成功/失败标志 ---
    intent_classification: Mapped[Optional[str]] = mapped_column(String(50), comment="data_analysis/chitchat/unanswerable")
    sql_generated: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否生成了SQL")
    sql_executed: Mapped[bool] = mapped_column(Boolean, default=False, comment="SQL是否执行")
    sql_success: Mapped[bool] = mapped_column(Boolean, default=False, comment="SQL执行是否成功")
    sql_semantic_pass: Mapped[bool] = mapped_column(Boolean, default=False, comment="语义一致性是否通过")
    python_executed: Mapped[bool] = mapped_column(Boolean, default=False, comment="Python是否执行")
    python_success: Mapped[bool] = mapped_column(Boolean, default=False, comment="Python执行是否成功")
    plan_first_pass: Mapped[bool] = mapped_column(Boolean, default=False, comment="Plan首次校验即通过")
    plan_repair_count: Mapped[int] = mapped_column(Integer, default=0, comment="Plan修复次数")
    report_generated: Mapped[bool] = mapped_column(Boolean, default=False, comment="报告是否生成")

    # --- HumanFeedback ---
    hf_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    hf_rejected: Mapped[bool] = mapped_column(Boolean, default=False)
    hf_reject_count: Mapped[int] = mapped_column(Integer, default=0)
    hf_final_status: Mapped[Optional[str]] = mapped_column(String(20), comment="approved/rejected/max_rejected")

    # --- 节点级耗时 (JSON 字符串，便于后续解析) ---
    node_durations_json: Mapped[Optional[str]] = mapped_column(Text, comment="各节点耗时JSON: {nodeName: ms}")

    # --- 质量指标 (需 golden dataset 标注) ---
    intent_expected: Mapped[Optional[str]] = mapped_column(String(50), comment="golden label for intent")
    schema_tables_expected: Mapped[Optional[int]] = mapped_column(Integer, comment="golden: expected table count")

    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
