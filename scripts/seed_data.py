"""
种子数据脚本

插入测试数据
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import async_session_maker
from app.models.agent import Agent


async def seed_data():
    """插入种子数据"""
    print("🌱 开始插入种子数据...")

    async with async_session_maker() as session:
        # 创建测试 Agent
        agents = [
            Agent(
                name="销售分析助手",
                description="分析销售数据，生成销售报告",
                status="published"
            ),
            Agent(
                name="用户行为分析",
                description="分析用户行为数据，提供用户画像",
                status="draft"
            ),
            Agent(
                name="财务数据分析",
                description="分析财务数据，生成财务报表",
                status="draft"
            ),
        ]

        session.add_all(agents)
        await session.commit()

        print(f"✅ 成功插入 {len(agents)} 个 Agent")
        for agent in agents:
            print(f"  - {agent.name} (status: {agent.status})")


if __name__ == "__main__":
    asyncio.run(seed_data())
