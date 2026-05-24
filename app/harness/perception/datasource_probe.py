# [阶段2] 数据源与语义模型一次探测（供 Preflight / builder 只读）
# [Harness: Memory #4] 探测 Agent 绑定的激活数据源、已选表和语义片段，生成快照。
#
# tables[:5] 语义警告逻辑:
#   仅对前 5 张表检查语义模型是否存在。这是采样而非全量检查 —
#   如果 Agent 配置了 50 张表，每张都查语义模型会导致 DB 查询爆炸。
#   前 5 张表缺失语义模型就记录 semantic_warn=True，在 Preflight 阶段提示用户完善。

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.harness.types.context import DatasetRef
from app.harness.types.datasource_probe import DatasourceProbeSnapshot
from app.services.agent_datasource_service import AgentDatasourceService
from app.services.semantic_model_service import SemanticModelService

logger = logging.getLogger(__name__)


async def run_datasource_probe(
    db: AsyncSession,
    *,
    agent_id: int,
    load_semantic: bool = True,
) -> DatasourceProbeSnapshot:
    """[阶段2] 拉取激活数据源、已选表与语义片段。"""
    agent_ds_list = await AgentDatasourceService.list_agent_datasources(db, agent_id)
    active = next((item for item in agent_ds_list if item.is_active == 1), None)
    if not active:
        return DatasourceProbeSnapshot(has_datasource=False)

    ds = active.datasource
    dialect = (ds.type or "mysql").lower()
    tables = list(active.select_tables or [])
    datasets: list[DatasetRef] = []
    semantic_parts: list[str] = []
    semantic_warn = False

    for table_name in tables:
        datasets.append(
            DatasetRef(
                datasource_id=active.datasource_id,
                datasource_name=ds.name or "",
                database_name=ds.database_name or "",
                table_name=table_name,
                dialect=dialect,
            )
        )
        if load_semantic:
            info = await SemanticModelService.get_table_semantic_info(
                db, agent_id, active.datasource_id, table_name
            )
            if info:
                semantic_parts.append(info)
            elif table_name in tables[:5]:
                semantic_warn = True

    snap = DatasourceProbeSnapshot(
        has_datasource=True,
        datasource_id=active.datasource_id,
        dialect=dialect,
        select_tables=tables,
        semantic_warn=semantic_warn,
        semantic_prompt="\n".join(semantic_parts),
        datasets=datasets,
    )
    logger.info(
        "[阶段2][DatasourceProbe] agent_id=%s tables=%d semantic_warn=%s",
        agent_id,
        len(tables),
        semantic_warn,
    )
    return snap
