"""
BaseService — 通用 CRUD 服务基类
减少各 Service 的重复代码
"""
from typing import TypeVar, Optional, List, Tuple, Generic
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from .database import Base

T = TypeVar("T", bound=Base)


class BaseService(Generic[T]):
    """通用 CRUD 服务基类

    用法:
        class AgentService(BaseService[Agent]):
            model = Agent
    """
    model: type[T] = None

    @classmethod
    async def create(cls, db: AsyncSession, data: dict) -> T:
        """创建记录"""
        obj = cls.model(**data)
        db.add(obj)
        await db.flush()
        await db.refresh(obj)
        return obj

    @classmethod
    async def get(cls, db: AsyncSession, id: int) -> Optional[T]:
        """根据 ID 获取记录"""
        result = await db.execute(select(cls.model).where(cls.model.id == id))
        return result.scalar_one_or_none()

    @classmethod
    async def list(
        cls,
        db: AsyncSession,
        filters: list = None,
        order_by=None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[T], int]:
        """列出记录（带分页和过滤）

        Args:
            db: 数据库会话
            filters: SQLAlchemy where 条件列表
            order_by: 排序字段
            skip: 分页偏移
            limit: 每页数量

        Returns:
            (记录列表, 总数)
        """
        query = select(cls.model)
        count_query = select(func.count(cls.model.id))

        if filters:
            query = query.where(*filters)
            count_query = count_query.where(*filters)

        if order_by is not None:
            query = query.order_by(order_by)

        query = query.offset(skip).limit(limit)

        result = await db.execute(query)
        items = result.scalars().all()

        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        return list(items), total

    @classmethod
    async def update(cls, db: AsyncSession, id: int, data: dict) -> Optional[T]:
        """更新记录"""
        obj = await cls.get(db, id)
        if not obj:
            return None
        for field, value in data.items():
            setattr(obj, field, value)
        await db.flush()
        await db.refresh(obj)
        return obj

    @classmethod
    async def delete(cls, db: AsyncSession, id: int) -> bool:
        """删除记录"""
        obj = await cls.get(db, id)
        if not obj:
            return False
        await db.delete(obj)
        await db.flush()
        return True
