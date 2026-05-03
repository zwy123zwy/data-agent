"""
Agent-数据源关联服务 — 管理多对多绑定关系

【在系统中的地位】
  Agent 和数据源之间是多对多关系: 一个 Agent 可以绑定多个数据源，
  一个数据源也可以被多个 Agent 共享。但同一时刻，一个 Agent 只有一个
  "激活"的数据源 (is_active=True)。

【模块连接】
  上游 (谁调用 AgentDatasourceService):
    - api/agent_datasource_controller.py → 绑定/解绑/列表/激活 API
    - api/streaming_graph_controller.py  → 流式查询前获取激活数据源
    - workflows/nodes/schema_recall.py   → 获取激活数据源用于 Schema 发现

  被依赖:
    - models/agent_datasource.py:AgentDatasource → ORM Model (MySQL 关联表)
    - models/agent.py:Agent                       → Agent ORM Model
    - models/datasource.py:Datasource             → Datasource ORM Model

  Java 对应:
    AgentDatasourceService ≈ AgentDatasourceServiceImpl.java

【激活机制】
  一个 Agent 只能有一个激活数据源。当绑定新数据源并设置为激活时，
  旧数据源的 is_active 自动设为 False。工作流执行时通过
  get_active_datasource() 获取当前激活的数据源。
"""
from typing import Optional, List
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.agent_datasource import AgentDatasource
from ..models.agent import Agent
from ..models.datasource import Datasource
from ..schemas.agent_datasource import AgentDatasourceCreate


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
        # 验证 Agent 是否存在
        agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = agent_result.scalar_one_or_none()
        if not agent:
            raise ValueError("Agent not found")

        # 验证 Datasource 是否存在
        datasource_result = await db.execute(
            select(Datasource).where(Datasource.id == datasource_id)
        )
        datasource = datasource_result.scalar_one_or_none()
        if not datasource:
            raise ValueError("Datasource not found")

        # 检查是否已经绑定
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

        # 如果设置为激活，先将其他数据源设为非激活
        if is_active:
            await db.execute(
                select(AgentDatasource)
                .where(AgentDatasource.agent_id == agent_id)
            )
            # 更新所有该 Agent 的数据源为非激活
            result = await db.execute(
                select(AgentDatasource).where(AgentDatasource.agent_id == agent_id)
            )
            for ad in result.scalars().all():
                ad.is_active = False

        # 创建关联
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
    ) -> tuple[List[tuple[AgentDatasource, Datasource]], int]:
        """列出 Agent 的所有数据源"""
        # 验证 Agent 是否存在
        agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = agent_result.scalar_one_or_none()
        if not agent:
            raise ValueError("Agent not found")

        # 查询关联和数据源详情
        query = (
            select(AgentDatasource, Datasource)
            .join(Datasource, AgentDatasource.datasource_id == Datasource.id)
            .where(AgentDatasource.agent_id == agent_id)
            .order_by(AgentDatasource.created_at.desc())
        )

        result = await db.execute(query)
        items = result.all()

        # 获取总数
        count_query = select(func.count(AgentDatasource.id)).where(
            AgentDatasource.agent_id == agent_id
        )
        count_result = await db.execute(count_query)
        total = count_result.scalar()

        return items, total

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
        # 先将所有数据源设为非激活
        result = await db.execute(
            select(AgentDatasource).where(AgentDatasource.agent_id == agent_id)
        )
        for ad in result.scalars().all():
            ad.is_active = False

        # 激活指定数据源
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
