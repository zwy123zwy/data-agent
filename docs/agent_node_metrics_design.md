# Agent Node Metrics Design

## 概述

对每个 LangGraph 工作流节点的执行进行结构化埋点，输出 JSON 格式日志，支持后续接入 Langfuse/Prometheus/Grafana 等观测系统。

## 数据模型

### NodeMetrics（单节点指标）

| 字段 | 类型 | 说明 |
|------|------|------|
| `threadId` | string | 工作流线程 ID（UUID） |
| `agentId` | string | Agent ID |
| `sessionId` | string | 会话 ID（可选） |
| `nodeName` | string | Java 兼容节点名（如 SqlGenerateNode） |
| `startTime` | ISO 8601 | 节点开始时间 |
| `endTime` | ISO 8601 | 节点结束时间 |
| `durationMs` | int | 执行耗时（毫秒） |
| `status` | string | `success` / `error` / `paused` / `running` |
| `retryCount` | int | 重试次数 |
| `errorType` | string | 异常类名（仅 error 状态） |
| `errorMessage` | string | 错误信息前 200 字符（仅 error 状态） |

### NodeMetricsTracker（聚合收集器）

每个 `threadId` 对应一个 Tracker 实例，在流式执行结束后输出汇总。

| 汇总字段 | 说明 |
|---------|------|
| `totalNodes` | 总节点执行次数 |
| `succeeded` | 成功节点数 |
| `failed` | 失败节点数 |
| `totalDurationMs` | 所有节点总耗时 |
| `avgDurationMs` | 平均耗时 |
| `maxDurationMs` | 最大耗时 |

## 核心指标定义

| 指标 | 计算方式 | 目标 |
|------|---------|------|
| **端到端成功率** | `succeeded / totalNodes` (不含 paused) | > 95% |
| **端到端耗时 P50/P90/P99** | 所有 `durationMs` 的百分位 | P99 < 60s |
| **Intent 准确率** | `data_analysis` 被正确分类的比例 | > 95% |
| **Schema 表召回率** | 激活数据源的表被正确包含在 schema 中的比例 | > 98% |
| **SQL 执行成功率** | `SqlExecuteNode` status=success 的比例 | > 90% |
| **SQL 语义正确率** | SemanticConsistency 通过的比例 | > 85% |
| **Python 执行成功率** | `PythonExecuteNode` 状态为 success 的比例 | > 80% |
| **Plan 校验通过率** | Plan validation 首次通过的比例 | > 90% |
| **HumanFeedback 拒绝后修复成功率** | reject 后重规划最终通过的比例 | > 60% |
| **最终报告数据一致性率** | 报告中引用的数据与实际查询结果一致的比例 | > 95% |

## 日志格式

### 单节点日志

```json
{
  "threadId": "a1b2c3d4-...",
  "agentId": "1",
  "sessionId": "",
  "nodeName": "SqlGenerateNode",
  "startTime": "2026-05-05T22:30:00.123456+00:00",
  "endTime": "2026-05-05T22:30:02.456789+00:00",
  "durationMs": 2333,
  "status": "success",
  "retryCount": 0,
  "errorType": null,
  "errorMessage": null
}
```

### 汇总日志

```
[MetricsSummary] thread=a1b2... nodes=7 ok=6 fail=0 totalMs=45230 avgMs=6461 maxMs=15200
```

## 接入方案

1. **当前**: 结构化 JSON 日志 → 可用 `jq` / `grep` 分析
2. **短期**: 接入 Langfuse (已在 `app/core/config.py` 预留 `LangfuseSettings`)
3. **长期**: 导出 Prometheus metrics → Grafana dashboard

## 实现文件

- `app/services/node_metrics.py` — NodeMetrics + NodeMetricsTracker
- `app/api/streaming_graph_controller.py` — 集成点（每个节点执行后自动记录）
- `tests/test_node_metrics.py` — 10 个单元测试
