"""
Agent 业务逻辑服务 — 继承 BaseService[Agent]

【在系统中的地位】
  Agent 是系统的核心实体，代表一个"数据分析智能体"。
  每个 Agent 可以绑定数据源、配置知识库、设置 LLM 模型，独立对外提供服务。

【模块连接】
  上游 (谁调用 AgentService):
    - api/agent_controller.py          → CRUD API + API Key 管理
    - api/streaming_graph_controller.py → 流式查询前验证 Agent 是否存在

  继承:
    - core/base_service.py:BaseService → 通用 CRUD (get/create/list/update/delete)

  被依赖:
    - models/agent.py:Agent            → ORM Model (MySQL agent 表)
    - schemas/agent.py:AgentCreate/Update → Pydantic DTO

  Java 对应:
    AgentService ≈ AgentServiceImpl.java

【API Key 管理】
  Agent 支持 API Key 认证，外部系统可通过 API Key 调用该 Agent 的数据分析能力。
  - generate: 生成新的 32 字符 Key
  - mask:    脱敏显示 (前4后4)
  - toggle:  启用/禁用
  - reset:   重新生成 (旧 Key 失效)
"""
import secrets
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
        keyword: Optional[str] = None,
    ) -> tuple[List[Agent], int]:
        filters = []
        if status:
            filters.append(Agent.status == status)
        if keyword:
            kw = f"%{keyword}%"
            filters.append(
                (Agent.name.like(kw)) | (Agent.description.like(kw))
            )
        return await AgentService.list(
            db, filters=filters, order_by=Agent.create_time.desc(), skip=skip, limit=limit
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

    # ==================================================================
    # API Key 管理 — 对齐 Java AgentController
    # ==================================================================

    @staticmethod
    def _generate_api_key() -> str:
        """生成 32 字符 API Key"""
        return secrets.token_hex(16)

    @staticmethod
    def _mask_api_key(key: Optional[str]) -> Optional[str]:
        """脱敏 API Key: 前4后4，中间用 **** 替代"""
        if not key:
            return None
        if len(key) <= 8:
            return key[:2] + "****" + key[-2:]
        return key[:4] + "****" + key[-4:]

    @staticmethod
    async def get_api_key_masked(db: AsyncSession, agent_id: int) -> Optional[str]:
        """获取脱敏后的 API Key"""
        agent = await AgentService.get_agent(db, agent_id)
        if not agent:
            return None
        return AgentService._mask_api_key(agent.api_key)

    @staticmethod
    async def generate_api_key(db: AsyncSession, agent_id: int) -> Optional[Agent]:
        """生成 API Key — 对齐 Java generateApiKey"""
        api_key = AgentService._generate_api_key()
        return await AgentService.update(db, agent_id, {
            "api_key": api_key,
            "api_key_enabled": 1,
        })

    @staticmethod
    async def reset_api_key(db: AsyncSession, agent_id: int) -> Optional[Agent]:
        """重置 API Key — 对齐 Java resetApiKey"""
        api_key = AgentService._generate_api_key()
        return await AgentService.update(db, agent_id, {
            "api_key": api_key,
            "api_key_enabled": 1,
        })

    @staticmethod
    async def delete_api_key(db: AsyncSession, agent_id: int) -> Optional[Agent]:
        """删除 API Key — 对齐 Java deleteApiKey"""
        return await AgentService.update(db, agent_id, {
            "api_key": None,
            "api_key_enabled": 0,
        })

    @staticmethod
    async def toggle_api_key(db: AsyncSession, agent_id: int, enabled: bool) -> Optional[Agent]:
        """启用/禁用 API Key — 对齐 Java toggleApiKey"""
        return await AgentService.update(db, agent_id, {"api_key_enabled": 1 if enabled else 0})
