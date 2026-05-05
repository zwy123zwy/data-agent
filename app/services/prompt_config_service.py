"""
PromptConfig Service — 对齐 Java UserPromptServiceImpl
用户自定义 Prompt 配置的 CRUD 服务
"""
import uuid
import logging
from typing import Optional, List
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.prompt_config import PromptConfig
from ..schemas.prompt_config import PromptConfigSaveRequest

logger = logging.getLogger(__name__)


class PromptConfigService:
    """Prompt 配置管理服务"""

    @staticmethod
    async def save_or_update(db: AsyncSession, dto: PromptConfigSaveRequest) -> PromptConfig:
        """保存或更新 — 对齐 Java saveOrUpdateConfig"""
        if dto.id:
            # 更新已有配置
            cfg = await db.get(PromptConfig, dto.id)
            if cfg:
                cfg.name = dto.name
                cfg.agent_id = dto.agent_id
                cfg.system_prompt = dto.optimization_prompt
                cfg.enabled = dto.enabled if dto.enabled is not None else 1
                cfg.description = dto.description
                cfg.priority = dto.priority or 0
                cfg.display_order = dto.display_order or 0
            else:
                # ID 不存在，创建新配置
                cfg = PromptConfig(
                    id=dto.id,
                    name=dto.name,
                    prompt_type=dto.prompt_type,
                    agent_id=dto.agent_id,
                    system_prompt=dto.optimization_prompt,
                    enabled=dto.enabled if dto.enabled is not None else 1,
                    description=dto.description,
                    priority=dto.priority or 0,
                    display_order=dto.display_order or 0,
                    creator=dto.creator,
                )
                db.add(cfg)
        else:
            # 新建配置，生成 UUID
            cfg = PromptConfig(
                id=uuid.uuid4().hex,
                name=dto.name,
                prompt_type=dto.prompt_type,
                agent_id=dto.agent_id,
                system_prompt=dto.optimization_prompt,
                enabled=dto.enabled if dto.enabled is not None else True,
                description=dto.description,
                priority=dto.priority or 0,
                display_order=dto.display_order or 0,
                creator=dto.creator,
            )
            db.add(cfg)

        await db.flush()
        await db.refresh(cfg)
        logger.info(f"[PromptConfig] Saved: id={cfg.id} type={cfg.prompt_type}")
        return cfg

    @staticmethod
    async def get_by_id(db: AsyncSession, config_id: str) -> Optional[PromptConfig]:
        return await db.get(PromptConfig, config_id)

    @staticmethod
    async def get_all(db: AsyncSession) -> List[PromptConfig]:
        r = await db.execute(select(PromptConfig).order_by(PromptConfig.create_time.desc()))
        return list(r.scalars().all())

    @staticmethod
    async def get_by_type(
        db: AsyncSession, prompt_type: str, agent_id: Optional[int] = None
    ) -> List[PromptConfig]:
        """按类型查询 — 对齐 Java getConfigsByType"""
        q = select(PromptConfig).where(PromptConfig.prompt_type == prompt_type)
        if agent_id is not None:
            q = q.where(PromptConfig.agent_id == agent_id)
        q = q.order_by(PromptConfig.priority.desc(), PromptConfig.display_order)
        r = await db.execute(q)
        return list(r.scalars().all())

    @staticmethod
    async def get_active_by_type(
        db: AsyncSession, prompt_type: str, agent_id: Optional[int] = None
    ) -> Optional[PromptConfig]:
        """获取当前激活的配置 — 对齐 Java getActiveConfigByType（返回优先级最高的）"""
        q = (
            select(PromptConfig)
            .where(PromptConfig.prompt_type == prompt_type, PromptConfig.enabled == 1)
        )
        if agent_id is not None:
            q = q.where(PromptConfig.agent_id == agent_id)
        q = q.order_by(PromptConfig.priority.desc()).limit(1)
        r = await db.execute(q)
        return r.scalar_one_or_none()

    @staticmethod
    async def get_active_all_by_type(
        db: AsyncSession, prompt_type: str, agent_id: Optional[int] = None
    ) -> List[PromptConfig]:
        """获取所有激活的配置 — 对齐 Java getActiveConfigsByType"""
        q = (
            select(PromptConfig)
            .where(PromptConfig.prompt_type == prompt_type, PromptConfig.enabled == 1)
        )
        if agent_id is not None:
            q = q.where(PromptConfig.agent_id == agent_id)
        q = q.order_by(PromptConfig.priority.desc(), PromptConfig.display_order)
        r = await db.execute(q)
        return list(r.scalars().all())

    @staticmethod
    async def delete_config(db: AsyncSession, config_id: str) -> bool:
        cfg = await db.get(PromptConfig, config_id)
        if not cfg:
            return False
        await db.delete(cfg)
        await db.flush()
        logger.info(f"[PromptConfig] Deleted: {config_id}")
        return True

    @staticmethod
    async def enable_config(db: AsyncSession, config_id: str) -> bool:
        cfg = await db.get(PromptConfig, config_id)
        if not cfg:
            return False
        cfg.enabled = 1
        await db.flush()
        logger.info(f"[PromptConfig] Enabled: {config_id}")
        return True

    @staticmethod
    async def disable_config(db: AsyncSession, config_id: str) -> bool:
        cfg = await db.get(PromptConfig, config_id)
        if not cfg:
            return False
        cfg.enabled = 0
        await db.flush()
        logger.info(f"[PromptConfig] Disabled: {config_id}")
        return True

    @staticmethod
    async def batch_enable(db: AsyncSession, ids: List[str]) -> bool:
        await db.execute(
            update(PromptConfig).where(PromptConfig.id.in_(ids)).values(enabled=1)
        )
        await db.flush()
        logger.info(f"[PromptConfig] Batch enabled: {ids}")
        return True

    @staticmethod
    async def batch_disable(db: AsyncSession, ids: List[str]) -> bool:
        await db.execute(
            update(PromptConfig).where(PromptConfig.id.in_(ids)).values(enabled=0)
        )
        await db.flush()
        logger.info(f"[PromptConfig] Batch disabled: {ids}")
        return True

    @staticmethod
    async def update_priority(db: AsyncSession, config_id: str, priority: int) -> bool:
        cfg = await db.get(PromptConfig, config_id)
        if not cfg:
            return False
        cfg.priority = priority
        await db.flush()
        return True

    @staticmethod
    async def update_display_order(db: AsyncSession, config_id: str, order: int) -> bool:
        cfg = await db.get(PromptConfig, config_id)
        if not cfg:
            return False
        cfg.display_order = order
        await db.flush()
        return True
