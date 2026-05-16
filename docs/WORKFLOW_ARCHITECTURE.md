# workflow 16节点架构：拓扑、数据流、状态映射

> 对齐 Java DataAgentConfiguration.nl2sqlGraph()
> 日期: 2026-05-15

---

## 三阶段总览

```
Phase 1 (线性)                              Phase 2 (循环)                    Phase 3 (收尾)

START                                      ┌─────────────────┐
  │                                        │  PlanExecutor   │
  ▼                                        │  读取 query_plan │
[1] IntentRecognition                      │  决定 next_node │
  │  (data_analysis)                       └──┬──┬──┬──┬────┘
  ▼                                          │  │  │  │
[2] KnowledgeRecall                          │  │  │  └── human_feedback → (approve)→PlanExecutor
  │                                          │  │  │                      → (reject)→Planner
  ▼                                          │  │  └──── report_generator → END
[3] QueryRewrite                             │  │
  │                                          │  └────────── python_generate → python_execute
  ▼                                          │                  │               │
[4] SchemaRecall                             │                  ▼          (retry/fallback)
  │                                          │            python_analyze      │
  ▼                                          │                  │            ▼
[5] TableRelation (retry×3)                  │                  └──→ plan_executor
  │                                          │
  ▼                                          └──────────── sql_generate → semantic_consistency
[6] FeasibilityAssessment                                  │    ▲               │
  │                                              (retry)──┘    └──(fail)───────┘
  ▼                                                               (pass)
[7] Planner                                                         │
  │                                                                 ▼
  └──→ PlanExecutor ◄─────────────────────── sql_execute ───────────┘
```

---

## 逐节点：输入 / 输出 / LLM 调用

图例： `IN` = 从 state 读取，`OUT` = 写入 state，`🤖` = 调用 LLM

---

### [1] IntentRecognition

```
IN:   user_query, multi_turn_context
OUT:  intent (data_analysis | chitchat)
      classification
🤖:   llm_service.chat(INTENT_SYSTEM_PROMPT, user_query)
ROUTE: data_analysis → [2] knowledge_recall
       chitchat      → END
```

状态：state 初始化时有输入层 4 个 key，此节点写入 intent 层 2 个 key。

---

### [2] KnowledgeRecall

```
IN:   user_query, agent_id, multi_turn_context
OUT:  recalled_knowledge (markdown 文本，带 [来源: xxx] 标注)
      knowledge_items (list[dict])
      recalled_business_terms
      recalled_agent_knowledge
🤖:   LLM 重写查询 → RAG 向量检索 (Chroma) → 格式化结果
DB:   MySQL business_knowledge / agent_knowledge 表
      Chroma agent_{id}_knowledge collection
ROUTE: → [3] query_rewrite
```

状态：写入 RAG 层 4 个 key。

---

### [3] QueryRewrite

```
IN:   user_query, recalled_knowledge
OUT:  rewritten_query (增强/消歧后的查询文本)
🤖:   llm_service.chat(QUERY_REWRITE_SYSTEM_PROMPT, prompt)
ROUTE: rewritten → [4] schema_recall
       empty     → END
```

状态：写入 QUERY 层 1 个 key（rewritten_query）。

---

### [4] SchemaRecall

```
IN:   agent_id
OUT:  schema (DDL 文本)
      schema_info (结构化 dict: tables, columns, foreign_keys)
DB:   通过 AgentDatasourceService 获取激活数据源
      通过 SchemaService 连接用户数据库查询 information_schema
ROUTE: schema 非空 → [5] table_relation
       schema 空   → END
```

状态：写入 SCHEMA 层 4 个 key（schema, schema_info, table_documents, column_documents）。

---

### [5] TableRelation

```
IN:   agent_id, schema_info.tables, schema_info.columns
OUT:  schema_info (ENHANCED: 添加 relations 数组)
      db_dialect_type
      table_relation_exception (如果失败)
🤖:   LLM 推理隐式表关系
LOGIC:
  1. 显式外键检测 → type: "explicit_fk"
  2. 同名字段匹配 → type: "same_name" (排除 id/name/created_at 等通用字段)
  3. LLM 语义推理 → type: "llm_inferred"
RETRY: max 3 次
ROUTE: success     → [6] feasibility
       failure <3  → self-loop (retry)
       failure >=3 → END
```

状态：更新 SCHEMA 层 schema_info；写入 TRACE 层 table_relation_exception / table_relation_retry_count。

---

### [6] FeasibilityAssessment

```
IN:   canonical_query, schema, recalled_knowledge
OUT:  feasibility_result {feasible: bool, reason: str}
🤖:   llm_service.chat(FEASIBILITY_SYSTEM_PROMPT, prompt)
ROUTE: feasible     → [7] planner
       not feasible → END
```

状态：写入 PLAN 层 1 个 key（feasibility_result）。

---

### [7] Planner

```
IN:   canonical_query, schema, recalled_knowledge
      semantic_model_prompt (controller 预构建)
      plan_validation_error (重规划时)
      agent_id (加载 prompt-config DB 覆盖)
OUT:  query_plan {
        execution_plan: [
          {step_id, type: "sql_generate"|"python_generate", description, instruction}
        ],
        thought_process: "..."
      }
      is_complex_query (steps > 1)
🤖:   llm_service.chat(PLANNER_SYSTEM_PROMPT + DB覆盖, prompt)
ROUTE: → [8] plan_executor
```

状态：写入 PLAN 层 2 个 key（query_plan, is_complex_query）。

---

### [8] PlanExecutor (循环调度核心)

```
IN:   query_plan, plan_current_step
      human_review_enabled, is_only_nl2sql
      plan_validation_status, plan_next_node (loop-back)
LOGIC:
  1. 解析 query_plan JSON
  2. 校验 plan 结构（steps 存在、type 合法）
  3. 取 execution_plan[current_step - 1]
  4. 根据 step.type 决定 next_node
OUT:  plan_next_node
      plan_current_step (递增)
      plan_validation_status
      plan_repair_count
      plan_validation_error (plan 格式错误时)
ROUTE:
  step.type == "sql_generate"    → [9]
  step.type == "python_generate" → [12]
  current_step > len(steps)      → [15] report_generator
  human_feedback enabled         → [16]
```

状态：不调用 LLM，纯调度逻辑。

---

### [9] SqlGenerate

```
IN:   canonical_query, current_instruction (从 plan 提取)
      schema, recalled_knowledge, db_dialect_type
      sql_regenerate_reason (重试原因)
      sql_result_list_memory (前序 SQL 结果，用于上下文)
OUT:  generated_sql
      sql_generate_count
      sql_regenerate_reason
🤖:   llm_service.chat(SQL_GENERATION_SYSTEM_PROMPT, prompt)
RETRY: max settings.max_sql_retry_count
ROUTE: sql OK → [10] semantic_consistency
       no sql, retries left → self-loop
       no sql, maxed        → END
```

状态：写入 SQL 层 3 个 key。

---

### [10] SemanticConsistency

```
IN:   canonical_query, generated_sql
      schema, recalled_knowledge, db_dialect_type
OUT:  semantic_consistency_result (bool)
🤖:   llm_service.chat(SEMANTIC_CHECK_SYSTEM_PROMPT, prompt)
ROUTE: pass → [11] sql_execute
       fail → [9]  sql_generate (重试)
```

状态：写入 SQL 层 1 个 key。

---

### [11] SqlExecute

```
IN:   generated_sql, agent_id
      sql_result_list_memory, sql_step_results (累积)
      query_plan (获取当前步骤编号)
OUT:  sql_result (list[dict])
      sql_result_list_memory (追加)
      sql_step_results (keyed by step number)
      sql_error (失败时)
EXEC: DatasourceHandler → 连接用户数据库执行 SQL
ROUTE: success → [8] plan_executor (下一步)
       error   → [9] sql_generate (重试)
```

状态：写入 SQL 层 4 个 key。不调用 LLM。

---

### [12] PythonGenerate

```
IN:   canonical_query, current_instruction
      sql_result (当前步骤数据)
      sql_result_list_memory (所有前序 SQL 结果)
      last_code, last_error (重试上下文)
      python_tries_count
OUT:  python_code
      python_tries_count
🤖:   llm_service.chat(PYTHON_GENERATION_SYSTEM_PROMPT, prompt)
RETRY: max settings.code_executor.python_max_tries_count
ROUTE: → [13] python_execute
```

状态：写入 PYTHON 层 2 个 key。

---

### [13] PythonExecute

```
IN:   python_code, sql_result
      python_tries_count
OUT:  python_output (stdout)
      python_charts (图表文件路径列表)
      python_data (返回的结构化数据)
      python_is_success (bool)
      python_error (stderr)
      python_fallback_mode (超过最大重试次数)
EXEC: CodeExecutor (local subprocess | Docker | AI-sim)
ROUTE: success       → [14] python_analyze
       error, tries  → [12] python_generate (retry)
       error, maxed  → [14] python_analyze (fallback)
```

状态：写入 PYTHON 层 6 个 key。不调用 LLM。

---

### [14] PythonAnalyze

```
IN:   python_output, python_charts, python_data
      sql_result (当前步骤)
      sql_step_results (所有步骤)
      python_fallback_mode
OUT:  python_analysis (LLM 叙述性分析文本)
🤖:   llm_service.chat(prompt, analysis_context)
ROUTE: → [8] plan_executor (下一步)
```

状态：写入 PYTHON 层 1 个 key。

---

### [15] ReportGenerator

```
IN:   canonical_query, query_plan
      sql_result_list_memory (所有 SQL 结果)
      python_analysis, python_output, python_charts
      agent_id (加载 prompt-config DB 覆盖)
OUT:  html_report (ECharts HTML)
      markdown_report
      report (legacy)
      display_style
🤖:   llm_service.chat(DEFAULT_REPORT_SYSTEM_PROMPT + DB覆盖, prompt)
      + CHART_RECOMMEND_SYSTEM_PROMPT (图表推荐)
ROUTE: → END
```

状态：写入 REPORT 层 3 个 key + DISPLAY 层。

---

### [16] HumanFeedback

```
IN:   query_plan (用于展示)
      plan_repair_count (拒绝次数)
      plan_validation_error
      human_next_node (外部 resume 写入)
LOGIC:
  1. interrupt() → LangGraph 暂停
  2. SSE event: paused → 前端展示审批 UI
  3. 用户操作 → 前端再次请求 → Command(resume={action, reason})
  4. approve → plan_next_node = human_next_node
  5. reject  → plan_next_node = planner (重规划)
OUT:  human_feedback_data
      plan_repair_count (reject 时递增)
ROUTE: approve → [8] plan_executor
       reject  → [7] planner
       max reject → END
```

状态：写入 FEEDBACK 层 3 个 key。不调用 LLM。

---

## State Key 分组及生产/消费关系

### 1. INPUT (4 keys) — Controller 写入

| Key | 生产者 | 消费者 |
|-----|--------|--------|
| agent_id | controller | [1][2][4][5][7][11][15] |
| user_query | controller | [1][2][3] |
| is_only_nl2sql | controller | [8] |
| multi_turn_context | controller | [1][2] |

### 2. INTENT (2 keys) — [1] 写入

| Key | 生产者 | 消费者 |
|-----|--------|--------|
| intent | [1] | route_after_intent |
| classification | [1] | SSE 输出 |

### 3. RAG (4 keys) — [2] 写入

| Key | 生产者 | 消费者 |
|-----|--------|--------|
| recalled_knowledge | [2] | [3][6][7][9][10] |
| knowledge_items | [2] | SSE 输出 |
| recalled_business_terms | [2] | (备用) |
| recalled_agent_knowledge | [2] | (备用) |

### 4. QUERY (2 keys) — [3] 写入

| Key | 生产者 | 消费者 |
|-----|--------|--------|
| rewritten_query | [3] | route, helper |
| canonical_query | (helper) | [6][7][9][10][12][15] |

### 5. SCHEMA (8 keys) — [4][5] 写入 + controller 注入

| Key | 生产者 | 消费者 |
|-----|--------|--------|
| schema | [4] | [5][6][7][9][10] |
| schema_info | [4][5] | SSE 输出 |
| table_documents | [4] | (备用) |
| column_documents | [4] | (备用) |
| db_dialect_type | [5] | [9][10] |
| semantic_model_prompt | controller | [7] |
| table_relation_exception | [5] | route |
| table_relation_retry_count | [5] | route |

### 6. PLAN (7 keys) — [6][7][8] 写入

| Key | 生产者 | 消费者 |
|-----|--------|--------|
| feasibility_result | [6] | route, SSE |
| query_plan | [7] | [8][11][15][16] |
| is_complex_query | [7] | (备用) |
| plan_current_step | [8] | [8] self |
| plan_next_node | [8] | route |
| plan_validation_status | [8] | [8] self |
| plan_repair_count | [8][16] | [8][16] |
| plan_validation_error | [8] | [7] (重规划时) |

### 7. SQL (7 keys) — [9][10][11] 写入

| Key | 生产者 | 消费者 |
|-----|--------|--------|
| generated_sql | [9] | [10][11], SSE |
| sql_generate_count | [9] | route |
| sql_regenerate_reason | [9] | route, [9] (重试) |
| semantic_consistency_result | [10] | route |
| sql_result | [11] | [12][13][14], SSE |
| sql_result_list_memory | [11] | [9][12][15] |
| sql_error | [11] | route, SSE |
| sql_step_results | [11] | [12][14] |

### 8. DISPLAY (1 key) — [15] 写入

| Key | 生产者 | 消费者 |
|-----|--------|--------|
| display_style | [15] | SSE 输出 |

### 9. PYTHON (9 keys) — [12][13][14] 写入

| Key | 生产者 | 消费者 |
|-----|--------|--------|
| python_code | [12] | [13], SSE |
| python_output | [13] | [14][15] |
| python_error | [13] | route |
| python_charts | [13] | [14][15] |
| python_data | [13] | [14] |
| python_analysis | [14] | [15] |
| python_is_success | [13] | route |
| python_tries_count | [13] | route |
| python_fallback_mode | [13] | [14] |

### 10. FEEDBACK (3 keys) — controller + [16] 写入

| Key | 生产者 | 消费者 |
|-----|--------|--------|
| human_review_enabled | controller | [8][16] |
| human_feedback_data | [16] | controller (SSE) |
| human_next_node | controller (resume) | [16] |

### 11. REPORT (3 keys) — [15] 写入

| Key | 生产者 | 消费者 |
|-----|--------|--------|
| html_report | [15] | SSE |
| markdown_report | [15] | SSE |
| report | [15] | SSE |

### 12. TRACE (2 keys) — 任意节点写入

| Key | 生产者 | 消费者 |
|-----|--------|--------|
| error | 任意节点 | route, controller |
| trace_thread_id | controller | (备用) |

---

## 数据流依赖链

```
user_query ──┬──→ [1] intent ──→ route
             │
             ├──→ [2] recalled_knowledge ──┬──→ [3] rewritten_query
             │                              │
             │                              ├──→ [6] feasibility ──→ route
             │                              │
             │                              ├──→ [7] query_plan ──→ [8] dispatch
             │                              │
             │                              ├──→ [9] generated_sql ──→ [10] check ──→ [11] sql_result ──┐
             │                              │                                                          │
             │                              └──→ [12] python_code ──→ [13] output ──→ [14] analysis ──┤
             │                                                                                         │
             └──→ [4] schema ──→ [5] schema_info (enhanced) ──→ [9][10]                               │
                                                                                                        │
                                                                                                        ▼
                                                                                     [15] report ──→ END
```

---

## 对应 Java 版本

| Python 节点 | Java 节点类 | Java Dispatcher |
|---|---|---|
| intent_recognition | IntentRecognitionNode | IntentRecognitionDispatcher |
| knowledge_recall | EvidenceRecallNode | (线性) |
| query_rewrite | QueryEnhanceNode | QueryEnhanceDispatcher |
| schema_recall | SchemaRecallNode | SchemaRecallDispatcher |
| table_relation | TableRelationNode | TableRelationDispatcher |
| feasibility | FeasibilityAssessmentNode | FeasibilityAssessmentDispatcher |
| planner | PlannerNode | (线性) |
| plan_executor | PlanExecutorNode | PlanExecutorDispatcher |
| sql_generate | SqlGenerateNode | SqlGenerateDispatcher |
| semantic_consistency | SemanticConsistencyNode | SemanticConsistenceDispatcher |
| sql_execute | SqlExecuteNode | SQLExecutorDispatcher |
| python_generate | PythonGenerateNode | (线性) |
| python_execute | PythonExecuteNode | PythonExecutorDispatcher |
| python_analyze | PythonAnalyzeNode | (线性) |
| report_generator | ReportGeneratorNode | (线性) |
| human_feedback | HumanFeedbackNode | HumanFeedbackDispatcher |
