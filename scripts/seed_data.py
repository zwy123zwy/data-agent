"""
种子数据脚本 — 补齐不同状态的 Agent 基础数据

用法:
    python scripts/seed_data.py    # 重复执行会先清旧数据再插入
"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import async_session_maker
from app.models.agent import Agent
from app.services.agent_service import AgentService
from sqlalchemy import select, delete


async def seed_agents():
    print("Clearing old agents...")

    async with async_session_maker() as session:
        # 清空旧数据，避免主键冲突
        await session.execute(delete(Agent))
        await session.commit()

        agents = [
            # ============================================================
            # published — 已发布 (3 个)
            # ============================================================
            Agent(
                name="电商销售分析助手",
                description="专注于电商平台销售数据分析，自动生成日报/周报/月报，"
                            "支持多维度交叉分析（品类、渠道、地区、时间），"
                            "可识别销售趋势异常并自动预警。",
                status="published",
                avatar="https://api.dicebear.com/7.x/bottts/svg?seed=sales",
                tags="销售,电商,报表,预警,趋势分析",
                category="销售分析",
                prompt="你是一个资深的电商销售数据分析师。分析销售数据时，"
                       "请关注同比环比变化、Top品类/商品、地域分布、渠道效率。"
                       "如发现异常波动，自动标注并给出可能的业务解释。",
                api_key=AgentService._generate_api_key(),
                api_key_enabled=True,
                human_review_enabled=False,
                admin_id=1,
            ),
            Agent(
                name="用户画像与行为分析",
                description="基于用户行为数据构建全方位用户画像，"
                            "包含用户分层（RFM模型）、行为路径分析、留存率分析、"
                            "转化漏斗分析，支持自定义用户分群和精准营销策略推荐。",
                status="published",
                avatar="https://api.dicebear.com/7.x/bottts/svg?seed=user",
                tags="用户画像,行为分析,RFM,留存,漏斗,营销",
                category="用户分析",
                prompt="你是一个用户行为分析专家。分析用户数据时，"
                       "请使用RFM模型做用户分层，分析关键行为路径的转化率，"
                       "识别高价值用户群体和流失风险用户。"
                       "输出要有可执行的运营建议。",
                api_key=AgentService._generate_api_key(),
                api_key_enabled=True,
                human_review_enabled=True,
                admin_id=1,
            ),
            Agent(
                name="财务报表智能分析",
                description="自动化财务报表分析，支持资产负债表、利润表、"
                            "现金流量表的多期对比，杜邦分析、偿债能力/营运能力/"
                            "盈利能力指标计算，财务风险预警。",
                status="published",
                avatar="https://api.dicebear.com/7.x/bottts/svg?seed=finance",
                tags="财务,报表,指标,风险,杜邦分析",
                category="财务分析",
                prompt="你是一个专业的财务分析师。分析财务报表时，"
                       "请严格按照会计准则计算各项财务指标，包括流动比率、"
                       "资产负债率、ROE、毛利率等。对比行业均值给出评估。",
                api_key=AgentService._generate_api_key(),
                api_key_enabled=True,
                human_review_enabled=True,
                admin_id=1,
            ),

            # ============================================================
            # draft — 草稿 (3 个)
            # ============================================================
            Agent(
                name="供应链库存优化分析",
                description="分析供应链库存数据，优化库存周转率和安全库存水平，"
                            "实现智能补货建议和滞销品预警（尚未完成配置）。",
                status="draft",
                avatar="https://api.dicebear.com/7.x/bottts/svg?seed=supply",
                tags="供应链,库存,补货,周转率,ABC分析",
                category="供应链",
                prompt="你是一个供应链分析专家。请基于历史出库数据和库存水平，"
                       "运用ABC分类法和经济订货量模型，给出补货建议。",
                api_key=None,
                api_key_enabled=False,
                human_review_enabled=False,
                admin_id=2,
            ),
            Agent(
                name="市场营销ROI分析",
                description="多平台营销投放效果归因分析，计算各渠道ROI，"
                            "支持首次归因/末次归因/线性归因等多种模型，"
                            "辅助优化营销预算分配（配置中，尚未发布）。",
                status="draft",
                avatar="https://api.dicebear.com/7.x/bottts/svg?seed=marketing",
                tags="营销,ROI,归因,投放,预算",
                category="营销分析",
                prompt="你是一个营销数据分析师。请使用多种归因模型分析各渠道的转化贡献，"
                       "结合投放成本计算ROI，给出最优预算分配方案。",
                api_key=AgentService._generate_api_key(),
                api_key_enabled=False,
                human_review_enabled=False,
                admin_id=2,
            ),
            Agent(
                name="客服质检与情感分析",
                description="基于客服对话日志进行自动质检评分和情感分析，"
                            "识别高频投诉话题、客服话术优化建议（开发中）。",
                status="draft",
                avatar="https://api.dicebear.com/7.x/bottts/svg?seed=service",
                tags="客服,质检,情感分析,NLP,投诉",
                category="客服分析",
                prompt="你是一个客服质检分析员。请根据对话内容评估客服服务质量，"
                       "识别用户情绪变化，提取高频投诉关键词，给出改进建议。",
                api_key=None,
                api_key_enabled=False,
                human_review_enabled=False,
                admin_id=2,
            ),

            # ============================================================
            # offline — 已下线 (2 个)
            # ============================================================
            Agent(
                name="旧版销售数据看板（已下线）",
                description="2024年版本的销售数据看板，已被「电商销售分析助手」替代。"
                            "保留数据但不再对外服务。",
                status="offline",
                avatar="https://api.dicebear.com/7.x/bottts/svg?seed=legacy1",
                tags="销售,看板,旧版,已废弃",
                category="销售分析",
                prompt="这是一个已被替换的旧版 Agent，请使用新版「电商销售分析助手」。",
                api_key=None,
                api_key_enabled=False,
                human_review_enabled=False,
                admin_id=1,
            ),
            Agent(
                name="员工考勤统计（已下线）",
                description="HR 部门考勤数据统计，因功能迁移至 HR 系统而下线。",
                status="offline",
                avatar="https://api.dicebear.com/7.x/bottts/svg?seed=legacy2",
                tags="HR,考勤,旧版,已废弃",
                category="人力资源",
                prompt="此 Agent 已下线，请使用公司 HR 系统进行考勤查询。",
                api_key=None,
                api_key_enabled=False,
                human_review_enabled=False,
                admin_id=3,
            ),
        ]

        session.add_all(agents)
        await session.commit()

        print(f"Inserted {len(agents)} Agents:\n")
        for a in agents:
            print(f"  [{a.status:^9}] id={a.id:<3} {a.name}")
            print(f"            category={a.category}  tags={a.tags}")
            print(f"            api_key={'XXXX' + a.api_key[-4:] if a.api_key else 'None':>12}  "
                  f"api_enabled={a.api_key_enabled}  "
                  f"human_review={a.human_review_enabled}")
            print()


if __name__ == "__main__":
    asyncio.run(seed_agents())
