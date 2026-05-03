"""
数据库核心 — 连接所有 ORM Model 与 MySQL 的桥梁

【模块连接】
  所有 models/*.py 中的 ORM Model 都继承自本文件的 Base 类
  所有 services/*.py 通过 get_db() 依赖注入获取数据库会话
  所有 api/*.py 中的控制器通过 Depends(get_db) 获取 db 参数

【使用模式】 (FastAPI 依赖注入)
  @router.get("/xxx")
  async def some_endpoint(db: AsyncSession = Depends(get_db)):
      # db 是一个异步数据库会话，请求结束后自动提交/回滚
      result = await db.execute(select(SomeModel).where(...))
      return result.scalars().all()

【连接池配置】
  pool_size=10     → 最多 10 个常驻连接
  max_overflow=20  → 高峰时可额外创建 20 个
  pool_pre_ping    → 每次使用前检查连接是否存活
  pool_recycle=3600 → 1小时后回收连接 (防止 MySQL 8小时超时)
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator
from .config import settings


# ===== 异步引擎 =====
# 使用 aiomysql 驱动连接 MySQL (异步 IO，不阻塞事件循环)
# settings.database_url 格式: mysql+aiomysql://user:pass@host:port/dbname
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600
)

# ===== 异步 Session 工厂 =====
# 每次调用生成一个新的 AsyncSession 实例
# expire_on_commit=False: 提交后不使对象过期，方便在 commit 后继续访问属性
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


# ===== ORM 基类 =====
# ★ 所有 ORM Model 都继承此类
# 例: class Agent(Base) — Base.metadata 包含所有表的元数据
# init_db() 调用 Base.metadata.create_all 自动建表
class Base(DeclarativeBase):
    """ORM 基类 — 所有 models/*.py 中的模型都继承自它"""
    pass


# ===== 依赖注入 → 获取数据库会话 =====
# ★ FastAPI 核心依赖注入函数
# 使用方式: db: AsyncSession = Depends(get_db)
#
# 请求处理流程:
#   1. 进入端点 → 创建会话
#   2. 执行业务逻辑 (yield session)
#   3. 正常返回 → commit()
#   4. 异常 → rollback()
#   5. 最终 → close()
#
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """依赖注入：获取数据库会话

    Yields:
        AsyncSession: 异步数据库会话

    生命周期:
        - 请求进入时创建
        - 成功时自动 commit
        - 异常时自动 rollback
        - 最后自动 close
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """初始化数据库表 (启动时调用)

    读取 models/ 下所有继承 Base 的 ORM Model
    自动在 MySQL 中创建不存在的表 (CREATE TABLE IF NOT EXISTS)
    不会修改已有表的列 (迁移需手动 ALTER TABLE)
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
