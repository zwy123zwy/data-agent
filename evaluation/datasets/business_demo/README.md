# 电商业务 Demo 评测数据集

## 概述

模拟一个在线商城的数据分析场景，包含 5 张业务表的完整电商数据模型。

## 数据模型

```
categories (商品类目)          products (商品)
┌──────────────────┐          ┌──────────────────┐
│ id               │◄─────────│ category_id      │
│ name             │          │ id               │
│ parent_id ──┐    │          │ name             │
│ sort_order     │    │          │ price            │
└──────────────────┘          │ cost             │
       │                      │ stock            │
       │ 自引用 (二级类目)      │ status           │
       └──────────────────────┘                  │
                              └──────┬───────────┘
                                     │
users (用户)                         │
┌──────────────────┐                 │
│ id               │                 │
│ name             │                 │
│ city             │                 │
│ vip_level        │                 │
└──────┬───────────┘                 │
       │                             │
       │ orders (订单)               │
       │ ┌──────────────────┐        │
       ├─│ user_id          │        │
       │ │ id               │        │
       │ │ total_amount     │        │
       │ │ status           │        │
       │ │ created_at       │        │
       │ └──────┬───────────┘        │
       │        │                    │
       │        │ order_items (明细) │
       │        │ ┌──────────────┐   │
       │        ├─│ order_id     │   │
       │        │ │ product_id ──┼───┘
       │        │ │ quantity    │
       │        │ │ unit_price  │
       │        │ │ subtotal    │
       │        │ └──────────────┘
```

## 数据规模

| 表 | 行数 | 说明 |
|---|------|------|
| categories | 10 | 4 一级类目 + 6 二级类目 |
| products | 20 | 活跃商品 + 1 个已下架商品 |
| users | 15 | 分布在 8 个城市 |
| orders | 25 | 含 1 个已取消订单 |
| order_items | 40 | 平均每单 1.6 件商品 |

## 评测用例覆盖

- **难度分布**: easy 10 / medium 12 / hard 6 / extra_hard 2 = 30 题
- **SQL 特性覆盖**:
  - 基础: SELECT, WHERE, ORDER BY, LIMIT
  - 聚合: COUNT, SUM, AVG, GROUP BY, HAVING
  - 连接: INNER JOIN, LEFT JOIN (2~4 表)
  - 子查询: IN, NOT IN, 标量子查询
  - 时间: DATE_FORMAT, DATE_ADD, DATEDIFF, 时间范围
  - 窗口函数: RANK, LAG, NTILE, ROWS BETWEEN
  - CTE: WITH 递归/非递归
  - 条件: CASE WHEN, NULLIF, COALESCE

## 使用方式

此数据集**不写入数据库**，仅用于:
1. 学习理解 Text-to-SQL 评测的数据结构
2. 手动验证 SQL 的正确性和执行结果
3. 作为评测脚本 `run_evaluation.py` 的输入

实际评测时，评测脚本会自动将这些 DDL 和 seed data 导入测试数据库。
