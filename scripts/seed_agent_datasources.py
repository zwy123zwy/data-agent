"""
Agent-Datasource 关联测试数据脚本
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import async_session_maker
from app.models.agent_datasource import AgentDatasource


async def seed_agent_datasources():
    """插入 Agent-Datasource 关联测试数据"""
    print("🌱 开始插入 Agent-Datasource 关联测试数据...")

    async with async_session_maker() as session:
        # 假设已经有 Agent ID 1, 2, 3 和 Datasource ID 1, 2
        # Agent 1 绑定 Datasource 1（激活）
        # Agent 2 绑定 Datasource 2（激活）
        bindings = [
            AgentDatasource(
                agent_id=1,
                datasource_id=1,
                is_active=True
            ),
            AgentDatasource(
                agent_id=2,
                datasource_id=2,
                is_active=True
            ),
        ]

        session.add_all(bindings)
        await session.commit()

        print(f"✅ 成功插入 {len(bindings)} 个 Agent-Datasource 关联")
        for binding in bindings:
            print(f"  - Agent {binding.agent_id} → Datasource {binding.datasource_id} (active: {binding.is_active})")


if __name__ == "__main__":
    asyncio.run(seed_agent_datasources())
