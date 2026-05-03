from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.datasource import Datasource
from ..schemas.datasource import DatasourceCreate, DatasourceUpdate
from ..core.base_service import BaseService
import aiomysql
import aiosqlite


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
        db: AsyncSession, type: Optional[str] = None, skip: int = 0, limit: int = 100,
    ) -> tuple[List[Datasource], int]:
        filters = [Datasource.type == type] if type else None
        return await DatasourceService.list(
            db, filters=filters, order_by=Datasource.created_at.desc(), skip=skip, limit=limit,
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
        datasource = await DatasourceService.get_datasource(db, datasource_id)
        if not datasource:
            return False, "Datasource not found"

        try:
            if datasource.type == "mysql":
                conn = await aiomysql.connect(
                    host=datasource.host, port=datasource.port or 3306,
                    user=datasource.username, password=datasource.password,
                    db=datasource.database, connect_timeout=5,
                )
                await conn.ensure_closed()
                message = "MySQL connection successful"
            elif datasource.type == "sqlite":
                async with aiosqlite.connect(datasource.connection_url or datasource.database) as conn:
                    await conn.execute("SELECT 1")
                message = "SQLite connection successful"
            elif datasource.type == "postgresql":
                return False, "PostgreSQL support not implemented yet"
            else:
                return False, f"Unsupported database type: {datasource.type}"

            datasource.test_status = "success"
            await db.flush()
            await db.refresh(datasource)
            return True, message

        except Exception as e:
            datasource.test_status = "failed"
            await db.flush()
            await db.refresh(datasource)
            return False, f"Connection failed: {str(e)}"
