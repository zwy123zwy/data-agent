from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.agent import Agent
from ..schemas.agent import AgentCreate, AgentUpdate


class AgentService:
    """Agent 业务逻辑服务"""

    @staticmethod
    async def create_agent(db: AsyncSession, agent_data: AgentCreate) -> Agent:
        """创建 Agent"""
        agent = Agent(
            name=agent_data.name,
            description=agent_data.description,
            status="draft"
        )
        db.add(agent)
        await db.flush()
        await db.refresh(agent)
        return agent

    @staticmethod
    async def get_agent(db: AsyncSession, agent_id: int) -> Optional[Agent]:
        """根据 ID 获取 Agent"""
        result = await db.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_agents(
        db: AsyncSession,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[Agent], int]:
        """列出 Agent（带分页和过滤）"""
        # 构建查询
        query = select(Agent)
        count_query = select(func.count(Agent.id))

        # 状态过滤
        if status:
            query = query.where(Agent.status == status)
            count_query = count_query.where(Agent.status == status)

        # 排序
        query = query.order_by(Agent.created_at.desc())

        # 分页
        query = query.offset(skip).limit(limit)

        # 执行查询
        result = await db.execute(query)
        agents = result.scalars().all()

        # 获取总数
        count_result = await db.execute(count_query)
        total = count_result.scalar()

        return list(agents), total

    @staticmethod
    async def update_agent(
        db: AsyncSession,
        agent_id: int,
        agent_data: AgentUpdate
    ) -> Optional[Agent]:
        """更新 Agent"""
        agent = await AgentService.get_agent(db, agent_id)
        if not agent:
            return None

        # 更新字段
        update_data = agent_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(agent, field, value)

        await db.flush()
        await db.refresh(agent)
        return agent

    @staticmethod
    async def delete_agent(db: AsyncSession, agent_id: int) -> bool:
        """删除 Agent"""
        agent = await AgentService.get_agent(db, agent_id)
        if not agent:
            return False

        await db.delete(agent)
        await db.flush()
        return True

    @staticmethod
    async def publish_agent(db: AsyncSession, agent_id: int) -> Optional[Agent]:
        """发布 Agent"""
        agent = await AgentService.get_agent(db, agent_id)
        if not agent:
            return None

        agent.status = "published"
        await db.flush()
        await db.refresh(agent)
        return agent

    @staticmethod
    async def offline_agent(db: AsyncSession, agent_id: int) -> Optional[Agent]:
        """下线 Agent"""
        agent = await AgentService.get_agent(db, agent_id)
        if not agent:
            return None

        agent.status = "offline"
        await db.flush()
        await db.refresh(agent)
        return agent
