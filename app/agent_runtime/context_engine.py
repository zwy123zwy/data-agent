# [阶段1] ContextEngine — 装配 RuntimeContext（Harness Memory #4）

from __future__ import annotations

import logging
from typing import Literal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.context import DatasetRef, Message, Permissions, RuntimeContext
from app.services.multi_turn import get_multi_turn_manager
from app.services.agent_datasource_service import AgentDatasourceService
from app.services.agent_service import AgentService
from app.services.semantic_model_service import SemanticModelService

logger = logging.getLogger(__name__)

ModeType = Literal["smart_query", "deep_research", "report", "chitchat", "clarification"]


class ContextEngine:
    """[阶段1] 在 Run 开始前一次性装配上下文，供 Tool 与 Runner 只读使用。"""

    async def build_context(
        self,
        *,
        agent_id: int,
        user_query: str,
        thread_id: str,
        db: AsyncSession,
        mode: ModeType = "smart_query",
        run_id: str | None = None,
    ) -> RuntimeContext:
        agent = await AgentService.get_agent(db, agent_id)
        if not agent:
            raise ValueError(f"Agent 不存在: {agent_id}")

        datasets: list[DatasetRef] = []
        semantic_parts: list[str] = []

        agent_ds_list = await AgentDatasourceService.list_agent_datasources(db, agent_id)
        active = next((item for item in agent_ds_list if item.is_active == 1), None)

        if active:
            ds = active.datasource
            dialect = (ds.type or "mysql").lower()
            for table_name in active.select_tables or []:
                datasets.append(
                    DatasetRef(
                        datasource_id=active.datasource_id,
                        datasource_name=ds.name or "",
                        database_name=ds.database_name or "",
                        table_name=table_name,
                        dialect=dialect,
                    )
                )
                info = await SemanticModelService.get_table_semantic_info(
                    db, agent_id, active.datasource_id, table_name
                )
                if info:
                    semantic_parts.append(info)

        memory: list[Message] = []
        multi_turn = get_multi_turn_manager().get_context_for_prompt(thread_id)
        if multi_turn:
            memory.append(Message(role="system", content=multi_turn[:4000]))

        permissions = Permissions(
            allow_write_operations=False,
            allow_python_execution=True,
            max_sql_result_rows=10000,
        )

        ctx = RuntimeContext(
            run_id=run_id or str(uuid4()),
            thread_id=thread_id,
            agent_id=agent_id,
            user_query=user_query,
            mode=mode,
            datasets=datasets,
            semantic_model={"prompt": "\n".join(semantic_parts)} if semantic_parts else {},
            business_knowledge=[],
            permissions=permissions,
            memory=memory,
        )
        logger.info(
            "[阶段1][ContextEngine] run_id=%s agent_id=%s datasets=%d mode=%s",
            ctx.run_id,
            agent_id,
            len(datasets),
            mode,
        )
        return ctx
