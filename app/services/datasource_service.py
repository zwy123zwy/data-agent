from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.datasource import Datasource
from ..schemas.datasource import DatasourceCreate, DatasourceUpdate
import aiomysql
import aiosqlite


class DatasourceService:
    """Datasource 业务逻辑服务"""

    @staticmethod
    async def create_datasource(db: AsyncSession, datasource_data: DatasourceCreate) -> Datasource:
        """创建 Datasource"""
        datasource = Datasource(
            name=datasource_data.name,
            type=datasource_data.type,
            host=datasource_data.host,
            port=datasource_data.port,
            database=datasource_data.database,
            username=datasource_data.username,
            password=datasource_data.password,
            connection_url=datasource_data.connection_url,
            test_status="untested"
        )
        db.add(datasource)
        await db.flush()
        await db.refresh(datasource)
        return datasource

    @staticmethod
    async def get_datasource(db: AsyncSession, datasource_id: int) -> Optional[Datasource]:
        """根据 ID 获取 Datasource"""
        result = await db.execute(
            select(Datasource).where(Datasource.id == datasource_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_datasources(
        db: AsyncSession,
        type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[Datasource], int]:
        """列出 Datasource（带分页和过滤）"""
        # 构建查询
        query = select(Datasource)
        count_query = select(func.count(Datasource.id))

        # 类型过滤
        if type:
            query = query.where(Datasource.type == type)
            count_query = count_query.where(Datasource.type == type)

        # 排序
        query = query.order_by(Datasource.created_at.desc())

        # 分页
        query = query.offset(skip).limit(limit)

        # 执行查询
        result = await db.execute(query)
        datasources = result.scalars().all()

        # 获取总数
        count_result = await db.execute(count_query)
        total = count_result.scalar()

        return list(datasources), total

    @staticmethod
    async def update_datasource(
        db: AsyncSession,
        datasource_id: int,
        datasource_data: DatasourceUpdate
    ) -> Optional[Datasource]:
        """更新 Datasource"""
        datasource = await DatasourceService.get_datasource(db, datasource_id)
        if not datasource:
            return None

        # 更新字段
        update_data = datasource_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(datasource, field, value)

        await db.flush()
        await db.refresh(datasource)
        return datasource

    @staticmethod
    async def delete_datasource(db: AsyncSession, datasource_id: int) -> bool:
        """删除 Datasource"""
        datasource = await DatasourceService.get_datasource(db, datasource_id)
        if not datasource:
            return False

        await db.delete(datasource)
        await db.flush()
        return True

    @staticmethod
    async def test_connection(db: AsyncSession, datasource_id: int) -> tuple[bool, str]:
        """测试数据源连接"""
        datasource = await DatasourceService.get_datasource(db, datasource_id)
        if not datasource:
            return False, "Datasource not found"

        try:
            if datasource.type == "mysql":
                # 测试 MySQL 连接
                conn = await aiomysql.connect(
                    host=datasource.host,
                    port=datasource.port or 3306,
                    user=datasource.username,
                    password=datasource.password,
                    db=datasource.database,
                    connect_timeout=5
                )
                await conn.ensure_closed()
                message = "MySQL connection successful"

            elif datasource.type == "sqlite":
                # 测试 SQLite 连接
                async with aiosqlite.connect(datasource.connection_url or datasource.database) as conn:
                    await conn.execute("SELECT 1")
                message = "SQLite connection successful"

            elif datasource.type == "postgresql":
                # PostgreSQL 暂不实现，返回提示
                return False, "PostgreSQL support not implemented yet"

            else:
                return False, f"Unsupported database type: {datasource.type}"

            # 更新测试状态
            datasource.test_status = "success"
            await db.flush()
            await db.refresh(datasource)

            return True, message

        except Exception as e:
            # 更新测试状态为失败
            datasource.test_status = "failed"
            await db.flush()
            await db.refresh(datasource)

            return False, f"Connection failed: {str(e)}"
