"""核心指标查询 API"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..services.metrics_aggregation_service import MetricsAggregationService

router = APIRouter(prefix="/api", tags=["指标查询"])


@router.get("/metrics/summary")
async def get_metrics_summary(
    agentId: int | None = Query(None, description="Agent ID，为空统计所有"),
    days: int = Query(7, ge=1, le=90, description="统计时间窗口（天）"),
    db: AsyncSession = Depends(get_db),
):
    """获取核心指标聚合"""
    return await MetricsAggregationService.get_summary(db, agent_id=agentId, days=days)


@router.get("/metrics/recent")
async def get_recent_executions(
    agentId: int | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """获取最近执行记录"""
    return await MetricsAggregationService.get_recent_executions(db, agent_id=agentId, limit=limit)
