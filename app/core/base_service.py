"""
BaseService — 通用 CRUD 服务基类 (类似 Java MyBatis-Plus BaseMapper)

【逐行讲解】
  全文每个语句都有编号注释，对应下方"逐行解释"。
  建议从上往下读代码，遇到编号就跳到下方看解释。

【架构定位】
  这是所有 Service 的父类，提供 CRUD 的标准实现。
  每个 Service 只需声明 model 类属性即可获得完整的增删改查能力。

【继承关系】
  BaseService (本文件)
    ├── AgentService          → app/services/agent_service.py
    ├── DatasourceService     → app/services/datasource_service.py
    ├── SemanticModelService  → app/services/semantic_model_service.py
    └── ...

【Java 对应】
  Java:  MyBatis-Plus BaseMapper<T> / IService<T>
  Python: 本文件 (纯 SQLAlchemy 实现，约 150 行替代 MyBatis-Plus 3 万行)

【替代方案对比 — 见文件末尾】
"""

# ① 泛型类型变量: T 可以是任何继承 Base 的 ORM 类
#    例: T = Agent, T = Datasource 等 → 让 IDE 能推断 list() 返回 List[Agent]
from typing import TypeVar, Optional, List, Tuple, Generic

# ② SQLAlchemy 的 select() 构建 SELECT 语句
#    func.count() 构建 COUNT(*) 聚合
#    delete() 构建 DELETE 语句
from sqlalchemy import select, func, delete

# ③ AsyncSession = 异步数据库会话 (基于 aiomysql 驱动)
#    所有数据库操作都是 await 的，不阻塞事件循环
from sqlalchemy.ext.asyncio import AsyncSession

# ④ Base = 所有 ORM Model 的父类
#    class Agent(Base) → Agent 自动注册到 Base.metadata
#    这里 import Base 是为了 constrain T 的类型上界
from .database import Base

# ⑤ 声明泛型变量 T，bound=Base 表示 T 必须是 Base 的子类
#    Generic[T] 让 BaseService[Agent] 成为泛型类
#    这样 list() 的返回值能被 IDE 自动推断为 Tuple[List[Agent], int]
T = TypeVar("T", bound=Base)


# ⑥ class BaseService(Generic[T]): 声明为泛型类
#    BaseService[Agent] → IDE 知道 self.model 是 Agent 类型
class BaseService(Generic[T]):
    """
    通用 CRUD 服务基类

    用法:
        class AgentService(BaseService[Agent]):
            model = Agent      # ← 只需要这一行，CRUD 全有了
    """

    # ⑦ model 类属性: 子类必须覆盖此项
    #    例: model = Agent   →   cls.model 即 Agent ORM 类
    #        cls.model.__tablename__ = "agent"
    model: type[T] = None

    # ==================================================================
    # CREATE — 新增一条记录
    # ==================================================================

    @classmethod
    # ⑧ @classmethod: 第一个参数是 cls (类本身)，不是 self (实例)
    #    调用方式: AgentService.create(db, {"name": "x"})
    #    不需要 AgentService().create(...)，省去了实例化
    async def create(cls, db: AsyncSession, data: dict) -> T:
        # ⑨ cls.model(**data) = Agent(name="x", description="y")
        #    ** 是字典解包: {"name": "x"} → name="x"
        #    等价于: obj = Agent(name=data["name"], description=data.get("description"))
        obj = cls.model(**data)

        # ⑩ db.add(obj): 把 ORM 对象放入 session 的待提交队列
        #    此时还没写 MySQL，只是标记为"待插入"
        db.add(obj)

        # ⑪ await db.flush(): 把 INSERT 语句真发给 MySQL
        #    但事务未提交 (commit)，其他连接还看不到
        #    为什么要 flush? → 为了拿到自增 ID
        #    不 flush 的话 obj.id 是 None (MySQL 还没分配 ID)
        await db.flush()

        # ⑫ await db.refresh(obj): 从 MySQL 重新读取这一行
        #    补齐 MySQL 端的默认值、触发器计算结果
        #    此时 obj.id 已填充为自增 ID，obj.created_at 也补上了
        await db.refresh(obj)

        # ⑬ 返回完整 ORM 对象 (含 id, created_at 等)
        return obj

    # ==================================================================
    # READ — 根据 ID 查一条
    # ==================================================================

    @classmethod
    async def get(cls, db: AsyncSession, id: int) -> Optional[T]:
        # ⑭ select(cls.model) = SELECT * FROM agent
        #    .where(cls.model.id == id) = WHERE agent.id = 5
        query = select(cls.model).where(cls.model.id == id)

        # ⑮ await db.execute(query): 把 SQL 发给 MySQL
        #    返回 Result 对象 (游标包装)
        result = await db.execute(query)

        # ⑯ result.scalar_one_or_none():
        #    取出结果中第一列第一行 → ORM 对象
        #    如果有正好 1 行 → 返回 Agent 对象
        #    如果有 0 行       → 返回 None
        #    如果超过 1 行     → 抛异常 (因为 WHERE id= 不应该多行)
        return result.scalar_one_or_none()

    # ==================================================================
    # LIST — 分页列表查询
    # ==================================================================

    @classmethod
    async def list(
        cls,
        db: AsyncSession,
        filters: list = None,   # ⑰ 过滤条件列表: [Agent.status == "published", Agent.name.like("%x%")]
        order_by=None,           # ⑱ 排序: Agent.created_at.desc()
        skip: int = 0,           # ⑲ 偏移量 (OFFSET): 第 0 行开始
        limit: int = 100,        # ⑳ 每页数量 (LIMIT): 最多 100 行
    ) -> Tuple[List[T], int]:
        # 返回值: (数据列表, 总行数)

        # ㉑ 构建查询: SELECT * FROM agent
        query = select(cls.model)

        # ㉒ 构建计数: SELECT COUNT(agent.id) FROM agent
        count_query = select(func.count(cls.model.id))

        # ㉓ 如果传了过滤条件，两个 SQL 都加上 WHERE
        #     query:        SELECT * FROM agent WHERE status = 'published'
        #     count_query:  SELECT COUNT(agent.id) FROM agent WHERE status = 'published'
        #    *filters 的 * 是解包: [a, b] → where(a, b) → WHERE a AND b
        if filters:
            query = query.where(*filters)
            count_query = count_query.where(*filters)

        # ㉔ 如果有排序条件，加到查询 SQL 上
        #    query.order_by(Agent.created_at.desc()) → ORDER BY agent.created_at DESC
        if order_by is not None:
            query = query.order_by(order_by)

        # ㉕ 分页: OFFSET skip LIMIT limit
        #    例: skip=20, limit=10 → 跳过前 20 条，取 10 条 (第 3 页)
        query = query.offset(skip).limit(limit)

        # ㉖ 执行数据查询 → MySQL 返回结果集
        result = await db.execute(query)

        # ㉗ result.scalars().all():
        #    .scalars() → 提取每行的第一列 (ORM 对象)
        #    .all()     → 取出所有行，转为 list
        #    返回: [Agent(id=1), Agent(id=2), ...]
        items = result.scalars().all()

        # ㉘ 执行计数查询 → MySQL 返回总行数
        count_result = await db.execute(count_query)

        # ㉙ count_result.scalar():
        #    取第一行第一列的值 (COUNT 的结果是一个数字)
        #    or 0: 如果结果是 None (空表)，返回 0
        total = count_result.scalar() or 0

        # ㉚ 返回元组: (数据列表, 总数)
        #    list(items) 把 scalars() 结果包装成标准 Python list
        return list(items), total

    # ==================================================================
    # UPDATE — 更新记录
    # ==================================================================

    @classmethod
    async def update(cls, db: AsyncSession, id: int, data: dict) -> Optional[T]:
        # ㉛ 复用 get(): 先查出要更新的对象
        #    为什么不直接 UPDATE WHERE id=?
        #    → 为了返回更新后的完整对象 (直接 UPDATE 不会返回)
        #    → 而且可以先校验记录是否存在
        obj = await cls.get(db, id)

        # ㉜ 记录不存在 → 返回 None，调用方自行处理 404
        if not obj:
            return None

        # ㉝ 逐字段赋值: setattr 动态设属性
        #    data = {"name": "new_name", "status": "published"}
        #    等价于:
        #      obj.name = "new_name"
        #      obj.status = "published"
        #    为什么不用直接 UPDATE? → SQLAlchemy 的 unit of work 模式:
        #      它跟踪每个 ORM 对象的脏字段，只更新变了的列
        #      SET name='new_name', status='published' ← 只更新这两个
        for field, value in data.items():
            setattr(obj, field, value)

        # ㉞ flush(): 把 UPDATE 语句发给 MySQL
        #    SQLAlchemy 自动生成: UPDATE agent SET name=?, status=? WHERE id=?
        await db.flush()

        # ㉟ refresh(): 从 MySQL 重读，补齐触发器/默认值/onupdate
        await db.refresh(obj)

        return obj

    # ==================================================================
    # DELETE — 删除记录
    # ==================================================================

    @classmethod
    async def delete(cls, db: AsyncSession, id: int) -> bool:
        # ㊱ 先查出来
        obj = await cls.get(db, id)

        # ㊲ 不存在 → 返回 False
        if not obj:
            return False

        # ㊳ await db.delete(obj): 标记对象为"待删除"
        #    对应 SQL: DELETE FROM agent WHERE id = 5
        await db.delete(obj)

        # ㊴ flush(): 把 DELETE 发到 MySQL
        await db.flush()

        return True


# ============================================================================
# 替代方案分析 (逐行解释结束，下面讨论"是否有更好的框架/写法")
# ============================================================================
#
# ┌─────────────────┬──────────────────────────────────────────────────────┐
# │ 方案              │ 评价                                                  │
# ├─────────────────┼──────────────────────────────────────────────────────┤
# │ 1. 保持现状       │ ✅ 零依赖，150行业务代码                                 │
# │   (当前方案)      │ ✅ 显式控制: 每一步都可见 (add/flush/refresh/commit)       │
# │                  │ ❌ 手写 SQLAlchemy 样板代码                              │
# │                  │ ❌ 没有类型安全的过滤条件构建                              │
# ├─────────────────┼──────────────────────────────────────────────────────┤
# │ 2. SQLModel      │ ✅ Pydantic + SQLAlchemy 二合一，定义一次即可             │
# │   (推荐替代)      │ ✅ 自带 CRUD: model.save(), model.delete()               │
# │                  │ ✅ 完美整合 FastAPI: response_model 直接用同一个类          │
# │                  │ ❌ 新库，团队需要学习; ORM 层灵活性不如纯 SQLAlchemy         │
# │                  │                                                       │
# │                  │ 对比现在的代码量:                                         │
# │                  │   现在: Agent(Base) + AgentResponse(BaseModel) 两套定义  │
# │                  │   SQLModel: class Agent(SQLModel, table=True) 一套即可   │
# ├─────────────────┼──────────────────────────────────────────────────────┤
# │ 3. tortoise-orm  │ ✅ Django ORM 风格的异步 ORM                            │
# │                  │ ✅ CRUD 最简洁: await Agent.filter(status="x").all()   │
# │                  │ ❌ 生态不如 SQLAlchemy，迁移成本高                        │
# ├─────────────────┼──────────────────────────────────────────────────────┤
# │ 4. Prisma Client │ ✅ TypeScript/Go/Rust 风格，类型安全极强                  │
# │   Python         │ ✅ 自动从 schema.prisma 生成模型                         │
# │                  │ ❌ 需要额外维护 .prisma 文件，引入外部工具链                 │
# ├─────────────────┼──────────────────────────────────────────────────────┤
# │ 5. Django ORM    │ ✅ 最成熟的 Python ORM，文档和社区最好                     │
# │   (换框架)        │ ❌ 要换成 Django 全家桶，不能嵌入 FastAPI                  │
# ├─────────────────┼──────────────────────────────────────────────────────┤
# │ 6. 写原生 SQL    │ ✅ 性能最好，控制力最强                                    │
# │   (不推荐)        │ ❌ SQL 注入风险; 拼字符串极易出错                          │
# │                  │ ❌ 丧失了 ORM 的对象映射和单元工作 (unit of work)           │
# └─────────────────┴──────────────────────────────────────────────────────┘
#
# 【我的建议】
#   对于这个项目，当前方案 (1) 是最合适的:
#     - 只有 ~150 行，维护成本低
#     - 团队已经熟悉 SQLAlchemy (Java 版也是类似设计)
#     - 每个 Service 只需 class AgentService(BaseService[Agent]): model = Agent
#
#   如果重构的话，方案 2 (SQLModel) 减代码最多:
#     - models/*.py + schemas/*.py 可以合并为一个文件
#     - 不需要 BaseService，CRUD 直接写在 Model 上
#     - 和 FastAPI 是同一个作者 (tiangolo)，设计上天然契合
#     - 迁移路径: pip install sqlmodel → 改 Base 为 SQLModel → 合并 schema
#       (可以渐进迁移，SQLModel 完全兼容现有 SQLAlchemy)
