"""指标聚合服务 — 落地 Phase 7 的 10 个核心指标

指标定义见 docs/agent_node_metrics_design.md

使用方式:
  1. 每次工作流执行完后调用 record_execution() 写入 DB
  2. 调用 get_summary() 获取指标聚合结果
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, case

from ..models.workflow_execution_metrics import WorkflowExecutionMetrics

logger = logging.getLogger(__name__)


def _percentile(sorted_values: list[float], pct: float) -> float:
    """计算百分位 (Nearest Rank)"""
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    idx = max(0, min(n - 1, int(n * pct / 100.0 + 0.5) - 1))
    return sorted_values[idx]


class MetricsAggregationService:
    """核心指标聚合查询服务"""

    @staticmethod
    async def record_execution(
        db: AsyncSession,
        *,
        thread_id: str,
        agent_id: int,
        session_id: str = "",
        status: str = "success",
        total_duration_ms: int = 0,
        total_nodes: int = 0,
        succeeded_nodes: int = 0,
        failed_nodes: int = 0,
        intent_classification: str | None = None,
        sql_generated: bool = False,
        sql_executed: bool = False,
        sql_success: bool = False,
        sql_semantic_pass: bool = False,
        python_executed: bool = False,
        python_success: bool = False,
        plan_first_pass: bool = False,
        plan_repair_count: int = 0,
        report_generated: bool = False,
        hf_enabled: bool = False,
        hf_rejected: bool = False,
        hf_reject_count: int = 0,
        hf_final_status: str | None = None,
        node_durations: dict[str, int] | None = None,
        intent_expected: str | None = None,
        schema_tables_expected: int | None = None,
    ):
        """写入单次执行记录"""
        try:
            record = WorkflowExecutionMetrics(
                thread_id=thread_id,
                agent_id=agent_id,
                session_id=session_id,
                status=status,
                total_duration_ms=total_duration_ms,
                total_nodes=total_nodes,
                succeeded_nodes=succeeded_nodes,
                failed_nodes=failed_nodes,
                intent_classification=intent_classification,
                sql_generated=sql_generated,
                sql_executed=sql_executed,
                sql_success=sql_success,
                sql_semantic_pass=sql_semantic_pass,
                python_executed=python_executed,
                python_success=python_success,
                plan_first_pass=plan_first_pass,
                plan_repair_count=plan_repair_count,
                report_generated=report_generated,
                hf_enabled=hf_enabled,
                hf_rejected=hf_rejected,
                hf_reject_count=hf_reject_count,
                hf_final_status=hf_final_status,
                node_durations_json=json.dumps(node_durations) if node_durations else None,
                intent_expected=intent_expected,
                schema_tables_expected=schema_tables_expected,
            )
            db.add(record)
            await db.commit()
            logger.debug(f"[Metrics] Recorded execution metrics for thread={thread_id}")
        except Exception:
            logger.exception("[Metrics] Failed to record execution metrics (non-fatal)")

    @staticmethod
    async def get_summary(
        db: AsyncSession,
        agent_id: int | None = None,
        days: int = 7,
    ) -> dict:
        """查询核心指标聚合

        返回 10 个核心指标 + E2E 耗时分布。
        agent_id=None 时统计所有 Agent。
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        base_q = select(WorkflowExecutionMetrics).where(
            WorkflowExecutionMetrics.create_time >= cutoff
        )
        if agent_id is not None:
            base_q = base_q.where(WorkflowExecutionMetrics.agent_id == agent_id)

        # 总记录数
        total_q = select(func.count(WorkflowExecutionMetrics.id)).where(
            WorkflowExecutionMetrics.create_time >= cutoff
        )
        if agent_id is not None:
            total_q = total_q.where(WorkflowExecutionMetrics.agent_id == agent_id)
        total_result = await db.execute(total_q)
        total_executions = total_result.scalar() or 0

        if total_executions == 0:
            return {
                "totalExecutions": 0,
                "periodDays": days,
                "agentId": agent_id,
                "message": "所选时间范围内无执行记录",
            }

        # 所有记录 (用于百分位计算)
        records_result = await db.execute(base_q.order_by(WorkflowExecutionMetrics.create_time.desc()))
        records = records_result.scalars().all()

        # ==================================================================
        # 1. 端到端成功率
        # ==================================================================
        success_count = sum(1 for r in records if r.status == "success")
        e2e_success_rate = round(success_count / total_executions * 100, 2) if total_executions else 0

        # ==================================================================
        # 2. 端到端耗时 P50/P90/P99
        # ==================================================================
        durations = sorted([r.total_duration_ms for r in records if r.total_duration_ms > 0])
        e2e_p50 = round(_percentile(durations, 50))
        e2e_p90 = round(_percentile(durations, 90))
        e2e_p99 = round(_percentile(durations, 99))
        e2e_avg = round(sum(durations) / len(durations)) if durations else 0

        # ==================================================================
        # 3. Intent 准确率 (需要有 golden label 的样本)
        # ==================================================================
        intent_labeled = [r for r in records if r.intent_expected and r.intent_classification]
        intent_correct = sum(1 for r in intent_labeled if r.intent_classification == r.intent_expected)
        intent_accuracy = round(intent_correct / len(intent_labeled) * 100, 2) if intent_labeled else None

        # ==================================================================
        # 4. SQL 执行成功率
        # ==================================================================
        sql_executed_records = [r for r in records if r.sql_executed]
        sql_success_count = sum(1 for r in sql_executed_records if r.sql_success)
        sql_success_rate = round(sql_success_count / len(sql_executed_records) * 100, 2) if sql_executed_records else None

        # ==================================================================
        # 5. SQL 语义正确率
        # ==================================================================
        sql_generated_records = [r for r in records if r.sql_generated]
        sql_semantic_pass_count = sum(1 for r in sql_generated_records if r.sql_semantic_pass)
        sql_semantic_rate = round(sql_semantic_pass_count / len(sql_generated_records) * 100, 2) if sql_generated_records else None

        # ==================================================================
        # 6. Python 执行成功率
        # ==================================================================
        python_executed_records = [r for r in records if r.python_executed]
        python_success_count = sum(1 for r in python_executed_records if r.python_success)
        python_success_rate = round(python_success_count / len(python_executed_records) * 100, 2) if python_executed_records else None

        # ==================================================================
        # 7. Plan 校验通过率 (首次即通过)
        # ==================================================================
        plan_records = [r for r in records if r.total_nodes > 3]  # 至少有 planner 节点
        plan_first_pass_count = sum(1 for r in plan_records if r.plan_first_pass)
        plan_pass_rate = round(plan_first_pass_count / len(plan_records) * 100, 2) if plan_records else None

        # ==================================================================
        # 8. HumanFeedback 拒绝后修复成功率
        # ==================================================================
        hf_rejected_records = [r for r in records if r.hf_enabled and r.hf_rejected]
        hf_fixed_count = sum(1 for r in hf_rejected_records if r.hf_final_status == "approved")
        hf_fix_rate = round(hf_fixed_count / len(hf_rejected_records) * 100, 2) if hf_rejected_records else None

        # ==================================================================
        # 9. 最终报告数据一致性率 (有报告且成功的比例)
        # ==================================================================
        report_generated_count = sum(1 for r in records if r.report_generated and r.status == "success")
        report_consistency_rate = round(report_generated_count / total_executions * 100, 2) if total_executions else 0

        # ==================================================================
        # 10. Schema 表召回率 (需要有 golden label 的样本)
        # ==================================================================
        schema_labeled = [r for r in records if r.schema_tables_expected is not None]
        # schema recall 需要实际召回表数，这里暂时从 node_durations_json 取不到准确值
        # 保留字段，待后续从节点信息中提取
        schema_recall_rate = None

        return {
            "totalExecutions": total_executions,
            "periodDays": days,
            "agentId": agent_id,
            # 1. 端到端成功率
            "e2eSuccessRate": e2e_success_rate,
            "e2eSuccessCount": success_count,
            # 2. 端到端耗时
            "e2eLatency": {
                "avgMs": e2e_avg,
                "p50Ms": e2e_p50,
                "p90Ms": e2e_p90,
                "p99Ms": e2e_p99,
            },
            # 3. Intent 准确率 (有标注时)
            "intentAccuracy": intent_accuracy,
            "intentLabeledCount": len(intent_labeled) if intent_labeled else 0,
            # 4. SQL 执行成功率
            "sqlSuccessRate": sql_success_rate,
            "sqlExecutedCount": len(sql_executed_records),
            # 5. SQL 语义正确率
            "sqlSemanticPassRate": sql_semantic_rate,
            # 6. Python 执行成功率
            "pythonSuccessRate": python_success_rate,
            "pythonExecutedCount": len(python_executed_records),
            # 7. Plan 校验通过率
            "planFirstPassRate": plan_pass_rate,
            "planCount": len(plan_records),
            # 8. HumanFeedback 修复成功率
            "hfFixRate": hf_fix_rate,
            "hfRejectedCount": len(hf_rejected_records),
            # 9. 报告数据一致性率
            "reportConsistencyRate": report_consistency_rate,
            # 10. Schema 表召回率 (待实现)
            "schemaRecallRate": schema_recall_rate,
        }

    @staticmethod
    async def get_recent_executions(
        db: AsyncSession,
        agent_id: int | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """获取最近执行记录列表"""
        q = select(WorkflowExecutionMetrics).order_by(
            WorkflowExecutionMetrics.create_time.desc()
        ).limit(limit)
        if agent_id is not None:
            q = q.where(WorkflowExecutionMetrics.agent_id == agent_id)

        result = await db.execute(q)
        records = result.scalars().all()

        return [
            {
                "id": r.id,
                "threadId": r.thread_id,
                "agentId": r.agent_id,
                "status": r.status,
                "totalDurationMs": r.total_duration_ms,
                "totalNodes": r.total_nodes,
                "intentClassification": r.intent_classification,
                "sqlSuccess": r.sql_success,
                "pythonSuccess": r.python_success,
                "reportGenerated": r.report_generated,
                "hfFinalStatus": r.hf_final_status,
                "createTime": r.create_time.isoformat() if r.create_time else None,
            }
            for r in records
        ]
