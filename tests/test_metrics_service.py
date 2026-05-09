"""Phase 7 核心指标聚合服务单元测试

验证 10 个核心指标:
  1. 端到端成功率
  2. 端到端耗时 P50/P90/P99
  3. Intent 准确率
  4. SQL 执行成功率
  5. SQL 语义正确率
  6. Python 执行成功率
  7. Plan 校验通过率
  8. HumanFeedback 拒绝后修复成功率
  9. 最终报告数据一致性率
  10. Schema 表召回率 (需 golden label, 暂为 None)
"""
import pytest
import json
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.database import Base
from app.models.workflow_execution_metrics import WorkflowExecutionMetrics
from app.services.metrics_aggregation_service import MetricsAggregationService, _percentile


# ── In-memory SQLite for testing ──────────────────────────────────────────
@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


# ── Helpers ───────────────────────────────────────────────────────────────
async def _insert_records(db: AsyncSession, count: int, **overrides):
    """插入 count 条执行记录, 可覆盖字段"""
    defaults = {
        "thread_id": "test-tid-{}",
        "agent_id": 1,
        "status": "success",
        "total_duration_ms": 5000,
        "total_nodes": 16,
        "succeeded_nodes": 16,
        "failed_nodes": 0,
        "intent_classification": "data_analysis",
        "sql_generated": True,
        "sql_executed": True,
        "sql_success": True,
        "sql_semantic_pass": True,
        "python_executed": True,
        "python_success": True,
        "plan_first_pass": True,
        "plan_repair_count": 0,
        "report_generated": True,
        "hf_enabled": False,
        "hf_rejected": False,
        "hf_reject_count": 0,
        "hf_final_status": None,
        "intent_expected": None,
        "schema_tables_expected": None,
    }
    defaults.update(overrides)

    for i in range(count):
        record = WorkflowExecutionMetrics(
            thread_id=defaults["thread_id"].format(i),
            agent_id=defaults["agent_id"],
            status=defaults["status"],
            total_duration_ms=defaults["total_duration_ms"],
            total_nodes=defaults["total_nodes"],
            succeeded_nodes=defaults["succeeded_nodes"],
            failed_nodes=defaults["failed_nodes"],
            intent_classification=defaults["intent_classification"],
            sql_generated=defaults["sql_generated"],
            sql_executed=defaults["sql_executed"],
            sql_success=defaults["sql_success"],
            sql_semantic_pass=defaults["sql_semantic_pass"],
            python_executed=defaults["python_executed"],
            python_success=defaults["python_success"],
            plan_first_pass=defaults["plan_first_pass"],
            plan_repair_count=defaults["plan_repair_count"],
            report_generated=defaults["report_generated"],
            hf_enabled=defaults["hf_enabled"],
            hf_rejected=defaults["hf_rejected"],
            hf_reject_count=defaults["hf_reject_count"],
            hf_final_status=defaults["hf_final_status"],
            intent_expected=defaults["intent_expected"],
            schema_tables_expected=defaults["schema_tables_expected"],
            create_time=datetime.utcnow() - timedelta(hours=i),
        )
        db.add(record)
    await db.commit()


# ── Percentile tests ──────────────────────────────────────────────────────
class TestPercentile:
    def test_empty(self):
        assert _percentile([], 50) == 0.0

    def test_single_value(self):
        assert _percentile([100], 50) == 100

    def test_p50(self):
        assert _percentile([1, 2, 3, 4, 5], 50) == 3

    def test_p90_of_10(self):
        values = sorted([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
        # n=10, p90 → idx = int(10*90/100 + 0.5) - 1 = int(9.5) - 1 = 8
        assert _percentile(values, 90) == 90

    def test_p99_rounding(self):
        values = sorted(range(1, 101))  # 1..100
        assert _percentile(values, 99) > 0


# ── Core metrics tests ────────────────────────────────────────────────────
class TestCoreMetrics:
    @pytest.mark.asyncio
    async def test_e2e_success_rate_100(self, db_session):
        await _insert_records(db_session, 10, status="success")
        summary = await MetricsAggregationService.get_summary(db_session)
        assert summary["totalExecutions"] == 10
        assert summary["e2eSuccessRate"] == 100.0

    @pytest.mark.asyncio
    async def test_e2e_success_rate_mixed(self, db_session):
        await _insert_records(db_session, 7, status="success")
        await _insert_records(db_session, 3, status="error", total_duration_ms=1000, total_nodes=3)
        summary = await MetricsAggregationService.get_summary(db_session)
        assert summary["totalExecutions"] == 10
        assert summary["e2eSuccessRate"] == 70.0

    @pytest.mark.asyncio
    async def test_e2e_latency_percentiles(self, db_session):
        for i, ms in enumerate([100, 200, 300, 500, 1000, 1500, 2000, 3000, 5000, 10000]):
            await _insert_records(db_session, 1, total_duration_ms=ms, thread_id=f"lat-{i}")
        summary = await MetricsAggregationService.get_summary(db_session)
        lat = summary["e2eLatency"]
        assert lat["p50Ms"] > 0
        assert lat["p90Ms"] > lat["p50Ms"]
        assert lat["p99Ms"] >= lat["p90Ms"]
        assert lat["avgMs"] > 0

    @pytest.mark.asyncio
    async def test_intent_accuracy_with_labels(self, db_session):
        # 正确的: classification == expected
        await _insert_records(db_session, 8, intent_classification="data_analysis",
                              intent_expected="data_analysis")
        # 错误的: classification != expected
        await _insert_records(db_session, 2, intent_classification="chitchat",
                              intent_expected="data_analysis")
        summary = await MetricsAggregationService.get_summary(db_session)
        assert summary["intentAccuracy"] == 80.0
        assert summary["intentLabeledCount"] == 10

    @pytest.mark.asyncio
    async def test_intent_accuracy_no_labels(self, db_session):
        await _insert_records(db_session, 5)
        summary = await MetricsAggregationService.get_summary(db_session)
        assert summary["intentAccuracy"] is None

    @pytest.mark.asyncio
    async def test_sql_success_rate(self, db_session):
        await _insert_records(db_session, 8, sql_executed=True, sql_success=True)
        await _insert_records(db_session, 2, sql_executed=True, sql_success=False)
        summary = await MetricsAggregationService.get_summary(db_session)
        assert summary["sqlSuccessRate"] == 80.0
        assert summary["sqlExecutedCount"] == 10

    @pytest.mark.asyncio
    async def test_sql_success_rate_no_sql(self, db_session):
        await _insert_records(db_session, 5, sql_executed=False, sql_success=False, sql_generated=False)
        summary = await MetricsAggregationService.get_summary(db_session)
        assert summary["sqlSuccessRate"] is None

    @pytest.mark.asyncio
    async def test_sql_semantic_rate(self, db_session):
        await _insert_records(db_session, 9, sql_generated=True, sql_semantic_pass=True)
        await _insert_records(db_session, 1, sql_generated=True, sql_semantic_pass=False)
        summary = await MetricsAggregationService.get_summary(db_session)
        assert summary["sqlSemanticPassRate"] == 90.0

    @pytest.mark.asyncio
    async def test_python_success_rate(self, db_session):
        await _insert_records(db_session, 7, python_executed=True, python_success=True)
        await _insert_records(db_session, 3, python_executed=True, python_success=False)
        summary = await MetricsAggregationService.get_summary(db_session)
        assert summary["pythonSuccessRate"] == 70.0
        assert summary["pythonExecutedCount"] == 10

    @pytest.mark.asyncio
    async def test_python_success_rate_no_python(self, db_session):
        await _insert_records(db_session, 5, python_executed=False, python_success=False)
        summary = await MetricsAggregationService.get_summary(db_session)
        assert summary["pythonSuccessRate"] is None

    @pytest.mark.asyncio
    async def test_plan_first_pass_rate(self, db_session):
        await _insert_records(db_session, 8, plan_first_pass=True, total_nodes=16)
        await _insert_records(db_session, 2, plan_first_pass=False, total_nodes=16)
        summary = await MetricsAggregationService.get_summary(db_session)
        assert summary["planFirstPassRate"] == 80.0
        assert summary["planCount"] == 10

    @pytest.mark.asyncio
    async def test_plan_first_pass_rate_excludes_short_runs(self, db_session):
        """total_nodes <= 3 的记录不计入 Plan 统计 (可能是 error 提前退出)"""
        await _insert_records(db_session, 5, plan_first_pass=False, total_nodes=3)
        summary = await MetricsAggregationService.get_summary(db_session)
        assert summary["planFirstPassRate"] is None  # 无符合条件的记录

    @pytest.mark.asyncio
    async def test_hf_fix_rate(self, db_session):
        # 被拒绝后最终通过
        await _insert_records(db_session, 6, hf_enabled=True, hf_rejected=True,
                              hf_final_status="approved", total_nodes=18)
        # 被拒绝后最终失败
        await _insert_records(db_session, 4, hf_enabled=True, hf_rejected=True,
                              hf_final_status="max_rejected", total_nodes=10)
        summary = await MetricsAggregationService.get_summary(db_session)
        assert summary["hfFixRate"] == 60.0
        assert summary["hfRejectedCount"] == 10

    @pytest.mark.asyncio
    async def test_hf_fix_rate_no_rejects(self, db_session):
        await _insert_records(db_session, 5, hf_enabled=False, hf_rejected=False)
        summary = await MetricsAggregationService.get_summary(db_session)
        assert summary["hfFixRate"] is None

    @pytest.mark.asyncio
    async def test_report_consistency_rate(self, db_session):
        await _insert_records(db_session, 8, report_generated=True, status="success")
        await _insert_records(db_session, 2, report_generated=False, status="error")
        summary = await MetricsAggregationService.get_summary(db_session)
        assert summary["reportConsistencyRate"] == 80.0

    @pytest.mark.asyncio
    async def test_schema_recall_rate_none(self, db_session):
        """Schema 召回率需要 golden label, 当前返回 None"""
        await _insert_records(db_session, 5)
        summary = await MetricsAggregationService.get_summary(db_session)
        assert summary["schemaRecallRate"] is None

    @pytest.mark.asyncio
    async def test_empty_no_records(self, db_session):
        summary = await MetricsAggregationService.get_summary(db_session)
        assert summary["totalExecutions"] == 0
        assert "message" in summary


# ── record_execution tests ─────────────────────────────────────────────────
class TestRecordExecution:
    @pytest.mark.asyncio
    async def test_record_success(self, db_session):
        await MetricsAggregationService.record_execution(
            db_session,
            thread_id="rec-1",
            agent_id=42,
            status="success",
            total_duration_ms=12345,
            total_nodes=16,
            succeeded_nodes=16,
            failed_nodes=0,
            intent_classification="data_analysis",
            sql_generated=True, sql_executed=True, sql_success=True, sql_semantic_pass=True,
            python_executed=True, python_success=True,
            plan_first_pass=True, plan_repair_count=0,
            report_generated=True,
            hf_enabled=False,
            node_durations={"IntentRecognitionNode": 500, "PlannerNode": 2000},
        )
        summary = await MetricsAggregationService.get_summary(db_session, agent_id=42)
        assert summary["totalExecutions"] == 1
        assert summary["e2eSuccessRate"] == 100.0

    @pytest.mark.asyncio
    async def test_record_multiple(self, db_session):
        for i in range(5):
            await MetricsAggregationService.record_execution(
                db_session,
                thread_id=f"rec-{i}",
                agent_id=1,
                status="success",
                total_duration_ms=(i + 1) * 1000,
                total_nodes=16,
                succeeded_nodes=16,
                failed_nodes=0,
            )
        summary = await MetricsAggregationService.get_summary(db_session, agent_id=1)
        assert summary["totalExecutions"] == 5


# ── Model field tests ─────────────────────────────────────────────────────
class TestWorkflowExecutionMetricsModel:
    @pytest.mark.asyncio
    async def test_defaults_after_flush(self, db_session):
        """SQLAlchemy server defaults 在 flush 后生效"""
        m = WorkflowExecutionMetrics(thread_id="t1", agent_id=1)
        db_session.add(m)
        await db_session.flush()
        assert m.status == "success"
        assert m.total_duration_ms == 0
        assert m.total_nodes == 0
        assert m.sql_generated is False
        assert m.python_executed is False
        assert m.plan_first_pass is False
        assert m.report_generated is False
        assert m.hf_enabled is False
        assert m.hf_rejected is False

    @pytest.mark.asyncio
    async def test_create_time_after_flush(self, db_session):
        m = WorkflowExecutionMetrics(thread_id="t1", agent_id=1)
        db_session.add(m)
        await db_session.flush()
        assert m.create_time is not None

    def test_node_durations_json(self):
        m = WorkflowExecutionMetrics(
            thread_id="t1", agent_id=1,
            node_durations_json=json.dumps({"PlannerNode": 2000}),
        )
        parsed = json.loads(m.node_durations_json)
        assert parsed["PlannerNode"] == 2000
