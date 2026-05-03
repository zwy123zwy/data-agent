# Text-to-SQL 评测体系

## 目录结构

```
evaluation/
├── README.md                          # 本文件
├── run_evaluation.py                  # 评测主入口 (validate / sql-only / full 三种模式)
├── sql_generator.py                   # 独立 SQL 生成器 (LLM → SQL, 不依赖完整工作流)
├── test_database.py                   # SQLite 测试数据库 (schema + seed data + MySQL→SQLite 方言转换)
├── metrics/
│   ├── sql_metrics.py                 # L2 指标: SP / EX / EM / VES
│   ├── python_metrics.py              # L3 指标: PER / POC / PQS (代码可执行率/输出正确性/质量)
│   └── report_metrics.py              # L4 指标: LLM-as-Judge 报告评分 (完整性/准确性/可读性/洞察/可视化)
├── datasets/
│   └── business_demo/                 # 电商业务 Demo 数据集
│       ├── README.md                  # 数据集说明
│       ├── schema.sql                 # 表结构 (5表 MySQL DDL)
│       ├── seed_data.sql              # 种子数据 (不入DB, 参考+SQLite导入用)
│       └── test_cases.json            # 30条问答对 (NL → SQL)
├── databases/                         # 评测运行时生成的 SQLite 文件 (gitignore)
└── reports/                           # 评测报告输出 (gitignore)
    └── YYYY-MM-DD_HH-MM-SS.json
```

## 快速开始

```bash
cd python-agent-v2

# 模式1: 验证 gold_sql 自身语法 (不需要 LLM, 不需要数据库)
python -m evaluation.run_evaluation --dataset business_demo --mode validate

# 模式2: SQL 生成 + 执行评测 (需要 LLM API Key)
python -m evaluation.run_evaluation --dataset business_demo --mode sql-only

# 模式3: 完整评测 L2+L3+L4 (需要 LLM API Key)
python -m evaluation.run_evaluation --dataset business_demo --mode full

# 按难度过滤
python -m evaluation.run_evaluation --dataset business_demo --difficulty hard

# 跳过 LLM 调用 (sql-only/full 模式中，不调用 LLM 生成 SQL)
python -m evaluation.run_evaluation --dataset business_demo --mode sql-only --no-llm
```

## 评测分层

| 层级 | 名称 | 内容 | 指标 | 状态 |
|------|------|------|------|------|
| L2 | SQL 执行评测 | NL→SQL 的准确性和效率 | EX, EM, SP, VES | Phase 2 |
| L3 | Python 分析评测 | Python 代码质量 | PER, POC, PQS | Phase 3 (框架完成, 待接入工作流) |
| L4 | 端到端评测 | 最终报告质量 | LLM-as-Judge 5维打分 | Phase 4 (框架完成, 待接入工作流) |

## 核心指标速览

```
L2 — SQL 评测:
  SP  (Syntax Pass)          = 生成的 SQL 能否通过语法解析?
  EM  (Exact Set Match)       = 生成的 SQL 组件 == 标准 SQL 组件?
  EX  (Execution Accuracy)    = 生成的 SQL 执行结果 == 标准 SQL 执行结果?
  VES (Valid Efficiency)      = min(1.0, gold_time / gen_time)  效率评分

L3 — Python 评测:
  PER (Python Execution Rate) = 代码能否成功执行?
  POC (Python Output Correct) = 执行输出是否包含预期结果?
  PQS (Python Quality Score)  = 代码质量 (安全检查/向量化/错误处理)

L4 — 报告评测 (LLM-as-Judge):
  完整性 (Completeness)       = 是否回答了所有用户问题?
  准确性 (Accuracy)           = 数据引用是否正确? 有无幻觉?
  可读性 (Readability)        = 结构是否清晰? 格式是否规范?
  洞察深度 (Insight Depth)    = 是否有超出预期的分析洞见?
  可视化质量 (Visual Quality) = 图表是否恰当、清晰?
```

## 技术架构

### SQLite 测试数据库

评测使用 SQLite 自包含数据库，不依赖外部 MySQL:

- **schema 转换**: MySQL DDL → SQLite DDL (AUTO_INCREMENT → AUTOINCREMENT, DECIMAL → REAL, 去掉 COMMENT/ENGINE)
- **方言转换**: 运行时将 MySQL SQL 转为 SQLite SQL (DATE_FORMAT → strftime, DATEDIFF → julianday, NOW → datetime('now'), 窗口函数/CTE 保留)
- **括号平衡**: `_find_matching_paren` 正确处理嵌套函数调用的括号深度

### SQL 方言转换示例

| MySQL | SQLite |
|-------|--------|
| `DATE_FORMAT(date, '%Y-%m')` | `strftime('%Y-%m', date)` |
| `NOW()` | `datetime('now')` |
| `DATE_SUB(NOW(), INTERVAL 30 DAY)` | `datetime(datetime('now'), '-30 days')` |
| `DATEDIFF(NOW(), col)` | `CAST(julianday(datetime('now')) - julianday(col) AS INTEGER)` |
| `DATE_ADD(date, INTERVAL 7 DAY)` | `datetime(date, '+7 days')` |
| `RANK() OVER (PARTITION BY ...)` | `RANK() OVER (PARTITION BY ...)` (直接兼容) |

## 数据集

### business_demo (自建)
- 5 张表: categories / products / users / orders / order_items
- 30 条 NL→SQL 问答对
- 难度: easy(10) / medium(12) / hard(6) / extra_hard(2)
- 覆盖: JOIN / 聚合 / 子查询 / 窗口函数 / CTE / CASE WHEN / RFM / 留存分析
- 种子数据: 10类目 + 20商品 + 15用户 + 25订单 + 40明细

### Spider (计划引入)
- 10,181 条问题，200 个数据库
- 业界标准 Text-to-SQL 评测数据集
- 引入后: `evaluation/datasets/spider/`

## 验证结果 (2026-05-03)

```
模式: sql-only, LLM: disabled, DB: SQLite
Total:            30
Syntax Pass:      100.0%
Execution Accuracy: 100.0%
ExactSetMatch:    100.0%

[easy       ] SP=100.0% EM=100.0% EX=100.0% (n=10)
[medium     ] SP=100.0% EM=100.0% EX=100.0% (n=12)
[hard       ] SP=100.0% EM=100.0% EX=100.0% (n=6)
[extra_hard ] SP=100.0% EM=100.0% EX=100.0% (n=2)
```
