from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.agent import Agent
from ..schemas.agent import AgentCreate, AgentUpdate
from ..core.base_service import BaseService


class AgentService(BaseService[Agent]):
    """Agent 业务逻辑服务"""
    model = Agent

    @staticmethod
    async def create_agent(db: AsyncSession, agent_data: AgentCreate) -> Agent:
        agent = Agent(
            name=agent_data.name,
            description=agent_data.description,
            status="draft",
            category=agent_data.category,
            prompt=agent_data.prompt,
            admin_id=agent_data.admin_id,
        )
        db.add(agent)
        await db.flush()
        await db.refresh(agent)
        return agent

    @staticmethod
    async def get_agent(db: AsyncSession, agent_id: int) -> Optional[Agent]:
        return await AgentService.get(db, agent_id)

    @staticmethod
    async def list_agents(
        db: AsyncSession,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[List[Agent], int]:
        filters = []
        if status:
            filters.append(Agent.status == status)
        return await AgentService.list(
            db, filters=filters, order_by=Agent.created_at.desc(), skip=skip, limit=limit
        )

    @staticmethod
    async def update_agent(db: AsyncSession, agent_id: int, agent_data: AgentUpdate) -> Optional[Agent]:
        update_data = agent_data.model_dump(exclude_unset=True)
        return await AgentService.update(db, agent_id, update_data)

    @staticmethod
    async def delete_agent(db: AsyncSession, agent_id: int) -> bool:
        return await AgentService.delete(db, agent_id)

    @staticmethod
    async def publish_agent(db: AsyncSession, agent_id: int) -> Optional[Agent]:
        return await AgentService.update(db, agent_id, {"status": "published"})

    @staticmethod
    async def offline_agent(db: AsyncSession, agent_id: int) -> Optional[Agent]:
        return await AgentService.update(db, agent_id, {"status": "offline"})
