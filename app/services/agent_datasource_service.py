"""
Agent-数据源关联服务 — 管理多对多绑定关系
"""
from typing import Optional, List
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.agent_datasource import AgentDatasource
from ..models.agent_datasource_tables import AgentDatasourceTables
from ..models.agent import Agent
from ..models.datasource import Datasource
from ..schemas.agent_datasource import AgentDatasourceResponse
from ..schemas.datasource import DatasourceResponse


class AgentDatasourceService:
    """Agent-Datasource 多对多关联管理"""

    @staticmethod
    async def bind_datasource(
        db: AsyncSession,
        agent_id: int,
        datasource_id: int,
        is_active: bool = True
    ) -> AgentDatasource:
        """绑定数据源到 Agent"""
        agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = agent_result.scalar_one_or_none()
        if not agent:
            raise ValueError("Agent not found")

        datasource_result = await db.execute(
            select(Datasource).where(Datasource.id == datasource_id)
        )
        datasource = datasource_result.scalar_one_or_none()
        if not datasource:
            raise ValueError("Datasource not found")

        existing_result = await db.execute(
            select(AgentDatasource).where(
                and_(
                    AgentDatasource.agent_id == agent_id,
                    AgentDatasource.datasource_id == datasource_id
                )
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            raise ValueError("Datasource already bound to this Agent")

        if is_active:
            result = await db.execute(
                select(AgentDatasource).where(AgentDatasource.agent_id == agent_id)
            )
            for ad in result.scalars().all():
                ad.is_active = False

        agent_datasource = AgentDatasource(
            agent_id=agent_id,
            datasource_id=datasource_id,
            is_active=is_active
        )
        db.add(agent_datasource)
        await db.flush()
        await db.refresh(agent_datasource)
        return agent_datasource

    @staticmethod
    async def unbind_datasource(
        db: AsyncSession,
        agent_id: int,
        datasource_id: int
    ) -> bool:
        """解绑数据源"""
        result = await db.execute(
            select(AgentDatasource).where(
                and_(
                    AgentDatasource.agent_id == agent_id,
                    AgentDatasource.datasource_id == datasource_id
                )
            )
        )
        agent_datasource = result.scalar_one_or_none()
        if not agent_datasource:
            return False

        await db.delete(agent_datasource)
        await db.flush()
        return True

    @staticmethod
    async def list_agent_datasources(
        db: AsyncSession,
        agent_id: int
    ) -> List[AgentDatasourceResponse]:
        """列出 Agent 的所有数据源，直接返回 Response 对象"""
        agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
        if not agent_result.scalar_one_or_none():
            raise ValueError("Agent not found")

        query = (
            select(AgentDatasource, Datasource)
            .join(Datasource, AgentDatasource.datasource_id == Datasource.id)
            .where(AgentDatasource.agent_id == agent_id)
            .order_by(AgentDatasource.created_at.desc())
        )
        result = await db.execute(query)
        rows = result.all()

        responses = []
        for agent_ds, datasource in rows:
            # 查 selectTables
            tables_result = await db.execute(
                select(AgentDatasourceTables.table_name)
                .where(AgentDatasourceTables.agent_datasource_id == agent_ds.id)
                .order_by(AgentDatasourceTables.table_name)
            )
            select_tables = [row[0] for row in tables_result.all()]

            responses.append(AgentDatasourceResponse(
                id=agent_ds.id,
                agent_id=agent_ds.agent_id,
                datasource_id=agent_ds.datasource_id,
                is_active=bool(agent_ds.is_active),
                created_at=agent_ds.created_at,
                updated_at=getattr(agent_ds, "updated_at", None),
                datasource=DatasourceResponse.model_validate(datasource),
                select_tables=select_tables,
            ))

        return responses

    @staticmethod
    async def get_active_datasource(
        db: AsyncSession,
        agent_id: int
    ) -> Optional[Datasource]:
        """获取 Agent 的激活数据源"""
        query = (
            select(Datasource)
            .join(AgentDatasource, AgentDatasource.datasource_id == Datasource.id)
            .where(
                and_(
                    AgentDatasource.agent_id == agent_id,
                    AgentDatasource.is_active == True
                )
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def activate_datasource(
        db: AsyncSession,
        agent_id: int,
        datasource_id: int
    ) -> AgentDatasource:
        """激活指定的数据源"""
        result = await db.execute(
            select(AgentDatasource).where(AgentDatasource.agent_id == agent_id)
        )
        for ad in result.scalars().all():
            ad.is_active = False

        target_result = await db.execute(
            select(AgentDatasource).where(
                and_(
                    AgentDatasource.agent_id == agent_id,
                    AgentDatasource.datasource_id == datasource_id
                )
            )
        )
        target = target_result.scalar_one_or_none()
        if not target:
            raise ValueError("Agent-Datasource binding not found")

        target.is_active = True
        await db.flush()
        await db.refresh(target)
        return target

    @staticmethod
    async def toggle_datasource(
        db: AsyncSession,
        agent_id: int,
        datasource_id: int,
        is_active: bool,
    ) -> AgentDatasource:
        """切换数据源激活状态 — 对齐 Java toggleDatasourceForAgent()"""
        target_result = await db.execute(
            select(AgentDatasource).where(
                and_(
                    AgentDatasource.agent_id == agent_id,
                    AgentDatasource.datasource_id == datasource_id,
                )
            )
        )
        target = target_result.scalar_one_or_none()
        if not target:
            raise ValueError("Agent-Datasource binding not found")

        # 如果要激活，先停用该 Agent 下所有其他数据源
        if is_active:
            result = await db.execute(
                select(AgentDatasource).where(AgentDatasource.agent_id == agent_id)
            )
            for ad in result.scalars().all():
                ad.is_active = False

        target.is_active = is_active
        await db.flush()
        await db.refresh(target)
        return target

    @staticmethod
    async def update_datasource_tables(
        db: AsyncSession,
        agent_id: int,
        datasource_id: int,
        tables: List[str],
    ):
        """更新 Agent 数据源选中的表 — 对齐 Java updateDatasourceTables()"""
        target_result = await db.execute(
            select(AgentDatasource).where(
                and_(
                    AgentDatasource.agent_id == agent_id,
                    AgentDatasource.datasource_id == datasource_id,
                )
            )
        )
        target = target_result.scalar_one_or_none()
        if not target:
            raise ValueError("Agent-Datasource binding not found")

        # 删除旧的表选择
        await db.execute(
            select(AgentDatasourceTables).where(
                AgentDatasourceTables.agent_datasource_id == target.id
            )
        )
        old_tables = (await db.execute(
            select(AgentDatasourceTables).where(
                AgentDatasourceTables.agent_datasource_id == target.id
            )
        )).scalars().all()
        for old in old_tables:
            await db.delete(old)

        # 创建新的表选择
        for table_name in tables:
            adt = AgentDatasourceTables(
                agent_datasource_id=target.id,
                table_name=table_name,
            )
            db.add(adt)

        await db.flush()
