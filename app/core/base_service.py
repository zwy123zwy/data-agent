"""
BaseService — 通用 CRUD 服务基类 (类似 Java 的 BaseMapper/BaseService)

【在系统中的地位】
  这是所有 Service 的父类，提供 CRUD 的标准实现。
  每个 Service 只需声明 model 类属性即可获得完整的增删改查能力。

【继承关系】
  BaseService (本文件)
    ├── AgentService          → app/services/agent_service.py
    ├── DatasourceService     → app/services/datasource_service.py
    ├── SemanticModelService  → app/services/semantic_model_service.py
    └── ... (其他 Service)

【使用模式】
  class AgentService(BaseService[Agent]):
      model = Agent

  # 子类自动获得这些方法:
  #   BaseService.create(db, {name: "xxx"})
  #   BaseService.get(db, id)
  #   BaseService.list(db, filters=[...], skip=0, limit=100)
  #   BaseService.update(db, id, {name: "new"})
  #   BaseService.delete(db, id)

【与 Java 对应关系】
  Java: MyBatis-Plus BaseMapper / IService
  Python: 本文件 BaseService (SQLAlchemy 实现)
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

    子类必须设置:
        model: ORM Model 类 (必须继承 Base)
    """
    model: type[T] = None

    @classmethod
    async def create(cls, db: AsyncSession, data: dict) -> T:
        """创建记录

        Args:
            db:   数据库会话 (由 FastAPI 依赖注入 get_db() 提供)
            data: 字段字典, 如 {"name": "test", "status": "draft"}

        Returns:
            新创建的 ORM 对象 (含自增 ID)

        流程: dict → ORM Model → db.add → flush → refresh → 返回
        """
        obj = cls.model(**data)
        db.add(obj)
        await db.flush()      # flush 获取自增 ID，但不提交事务
        await db.refresh(obj) # refresh 从 DB 重新加载完整行
        return obj

    @classmethod
    async def get(cls, db: AsyncSession, id: int) -> Optional[T]:
        """根据 ID 获取记录

        Returns:
            ORM 对象或 None (未找到时)
        """
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
        """列出记录 (带分页和过滤)

        Args:
            db:       数据库会话
            filters:  SQLAlchemy where 条件列表, 如 [Agent.status == "published"]
            order_by: 排序字段, 如 Agent.created_at.desc()
            skip:     分页偏移 (offset)
            limit:    每页数量

        Returns:
            (记录列表, 总数) 元组

        SQL 等价:
            SELECT * FROM table WHERE filters ORDER BY order_by LIMIT limit OFFSET skip;
            SELECT COUNT(*) FROM table WHERE filters;
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
        """更新记录

        Args:
            db:   数据库会话
            id:   记录 ID
            data: 要更新的字段字典, 如 {"name": "new_name"}

        Returns:
            更新后的 ORM 对象或 None

        流程: get → setattr 逐字段赋值 → flush → refresh → 返回
        """
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
        """删除记录

        Returns:
            True (删除成功) 或 False (记录不存在)
        """
        obj = await cls.get(db, id)
        if not obj:
            return False
        await db.delete(obj)
        await db.flush()
        return True
