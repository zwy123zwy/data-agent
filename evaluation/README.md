# Text-to-SQL 评测体系

## 目录结构

```
evaluation/
├── README.md                          # 本文件
├── run_evaluation.py                  # 评测主入口
├── metrics/
│   └── sql_metrics.py                 # 指标计算 (EX/EM/SP/VES)
├── datasets/
│   └── business_demo/                 # 电商业务 Demo 数据集
│       ├── README.md                  # 数据集说明
│       ├── schema.sql                 # 表结构 (5表, DDL)
│       ├── seed_data.sql              # 种子数据 (不导入DB, 参考用)
│       └── test_cases.json            # 30条问答对 (NL → SQL)
└── reports/                           # 评测报告输出
    └── YYYY-MM-DD_HH-MM-SS.json
```

## 快速开始

```bash
cd python-agent-v2

# 验证 gold_sql 自身的语法正确性 (不需要数据库)
python -m evaluation.run_evaluation --dataset business_demo

# 按难度过滤
python -m evaluation.run_evaluation --dataset business_demo --difficulty hard
```

## 评测分层

| 层级 | 名称 | 内容 | 指标 | 状态 |
|------|------|------|------|------|
| L2 | SQL 执行评测 | NL→SQL 的准确性和效率 | EX, EM, SP, VES | Phase 1 |
| L3 | Python 分析评测 | Python 代码质量 | 可执行率, 输出正确性 | Phase 2 (规划) |
| L4 | 端到端评测 | 最终报告质量 | LLM-as-Judge 打分 | Phase 3 (规划) |

## 核心指标速览

```
EX (Execution Accuracy)    = 生成的SQL执行结果 == 标准SQL执行结果 ?
EM (Exact Set Match)       = 生成的SQL组件 == 标准SQL组件 ?
SP (Syntax Pass)           = SQL能否成功解析?
VES (Valid Efficiency)     = 生成SQL的执行效率 (执行时间比)
```

## 数据集

### business_demo (自建)
- 5 张表: categories / products / users / orders / order_items
- 30 条 NL→SQL 问答对
- 难度: easy(10) / medium(12) / hard(6) / extra_hard(2)
- 覆盖: JOIN / 聚合 / 子查询 / 窗口函数 / CTE / CASE WHEN

### Spider (计划引入)
- 10,181 条问题，200 个数据库
- 业界标准 Text-to-SQL 评测数据集
- 引入后: `evaluation/datasets/spider/`
