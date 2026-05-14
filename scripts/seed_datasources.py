"""
Datasource 测试数据脚本
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import async_session_maker
from app.models.datasource import Datasource


async def seed_datasources():
    """插入 Datasource 测试数据"""
    print("🌱 开始插入 Datasource 测试数据...")

    async with async_session_maker() as session:
        # 创建测试 Datasource
        datasources = [
            Datasource(
                name="本地MySQL数据库",
                type="mysql",
                host="localhost",
                port=3306,
                database_name="dataagent",
                username="root",
                password="123456",
                test_status="unknown"
            ),
            Datasource(
                name="测试SQLite数据库",
                type="sqlite",
                database_name="test.db",
                connection_url="sqlite:///./test.db",
                test_status="unknown"
            ),
        ]

        session.add_all(datasources)
        await session.commit()

        print(f"✅ 成功插入 {len(datasources)} 个 Datasource")
        for ds in datasources:
            print(f"  - {ds.name} (type: {ds.type})")


if __name__ == "__main__":
    asyncio.run(seed_datasources())
