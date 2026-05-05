"""
数据源服务 — 管理用户数据库连接信息

【在系统中的地位】
  数据源是连接用户业务数据库的"桥梁配置"。它存储连接信息
  (host/port/username/password/database)，支持连接测试。

【模块连接】
  上游 (谁调用 DatasourceService):
    - api/datasource_controller.py → CRUD API + 测试连接
    - api/schema_controller.py     → Schema 发现

  继承:
    - core/base_service.py:BaseService → 通用 CRUD

  被依赖:
    - models/datasource.py:Datasource  → ORM Model (MySQL datasource 表)
    - core/datasource_handler.py → 策略模式，多数据库连接测试

  下游 (谁使用 Datasource 数据):
    - services/schema_service.py       → 读取 Datasource 连接信息，获取表结构
    - services/agent_datasource_service.py → 绑定 Agent-数据源关系

  Java 对应:
    DatasourceService ≈ DatasourceServiceImpl.java

【支持的数据源类型】
  - mysql:      使用 aiomysql 驱动，通过 information_schema 获取元数据
  - sqlite:     使用 aiosqlite 驱动，本地文件数据库
  - postgresql: 计划中 (使用 asyncpg)
  - sqlserver:  计划中
  - oracle:     计划中
  - hive:       计划中
"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.datasource import Datasource
from ..schemas.datasource import DatasourceCreate, DatasourceUpdate
from ..core.base_service import BaseService


class DatasourceService(BaseService[Datasource]):
    """Datasource 业务逻辑服务"""
    model = Datasource

    @staticmethod
    async def create_datasource(db: AsyncSession, datasource_data: DatasourceCreate) -> Datasource:
        datasource = Datasource(
            name=datasource_data.name,
            type=datasource_data.type,
            host=datasource_data.host,
            port=datasource_data.port,
            database=datasource_data.database,
            username=datasource_data.username,
            password=datasource_data.password,
            connection_url=datasource_data.connection_url,
            description=datasource_data.description,
            test_status="untested",
            status="active",
        )
        db.add(datasource)
        await db.flush()
        await db.refresh(datasource)
        return datasource

    @staticmethod
    async def get_datasource(db: AsyncSession, datasource_id: int) -> Optional[Datasource]:
        return await DatasourceService.get(db, datasource_id)

    @staticmethod
    async def list_datasources(
        db: AsyncSession,
        type: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[List[Datasource], int]:
        filters = []
        if type:
            filters.append(Datasource.type == type)
        if status:
            filters.append(Datasource.status == status)
        return await DatasourceService.list(
            db, filters=filters or None, order_by=Datasource.create_time.desc(), skip=skip, limit=limit,
        )

    @staticmethod
    async def update_datasource(db: AsyncSession, datasource_id: int, datasource_data: DatasourceUpdate) -> Optional[Datasource]:
        update_data = datasource_data.model_dump(exclude_unset=True)
        return await DatasourceService.update(db, datasource_id, update_data)

    @staticmethod
    async def delete_datasource(db: AsyncSession, datasource_id: int) -> bool:
        return await DatasourceService.delete(db, datasource_id)

    @staticmethod
    async def test_connection(db: AsyncSession, datasource_id: int) -> tuple[bool, str]:
        """测试数据源连接 — 对齐 Java testConnection()

        使用 DatasourceTypeHandler 策略模式:
          1. 根据 datasource.type 获取对应 Handler
          2. Handler.ping() 执行连接测试
          3. 更新 test_status 到数据库
        """
        from ..core.datasource_handler import get_handler

        datasource = await DatasourceService.get_datasource(db, datasource_id)
        if not datasource:
            return False, "Datasource not found"

        handler = get_handler(datasource.type)
        if not handler:
            return False, f"Unsupported database type: {datasource.type}"

        try:
            success, message = await handler.ping(datasource)
            datasource.test_status = "success" if success else "failed"
            await db.flush()
            await db.refresh(datasource)
            return success, message
        except Exception as e:
            logger = __import__("logging").getLogger(__name__)
            logger.error(f"Error testing connection for datasource {datasource_id}: {e}")
            datasource.test_status = "failed"
            await db.flush()
            await db.refresh(datasource)
            return False, f"Connection failed: {str(e)}"
