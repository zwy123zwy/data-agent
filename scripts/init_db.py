"""
数据库初始化脚本

创建数据库和表结构
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import engine, Base
from app.models.agent import Agent  # noqa: F401
from app.models.datasource import Datasource  # noqa: F401
from app.models.agent_datasource import AgentDatasource  # noqa: F401
from app.models.agent_run import AgentRun  # noqa: F401
from app.models.agent_run_event import AgentRunEvent  # noqa: F401
from app.models.agent_artifact import AgentArtifactRecord  # noqa: F401


async def init_database():
    """初始化数据库"""
    print("🚀 开始初始化数据库...")

    async with engine.begin() as conn:
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)

    print("✅ 数据库表创建成功！")
    print("\n已创建的表:")
    print("  - agent")
    print("  - datasource")
    print("  - agent_datasource")


async def drop_database():
    """删除所有表（慎用！）"""
    print("⚠️  警告：即将删除所有表...")
    confirm = input("确认删除？(yes/no): ")

    if confirm.lower() == "yes":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        print("✅ 所有表已删除")
    else:
        print("❌ 操作已取消")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="数据库初始化脚本")
    parser.add_argument(
        "--drop",
        action="store_true",
        help="删除所有表（危险操作）"
    )

    args = parser.parse_args()

    if args.drop:
        asyncio.run(drop_database())
    else:
        asyncio.run(init_database())
