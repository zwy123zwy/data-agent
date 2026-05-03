# 从 0 到 1 学习 Spring Data Agent 项目指南

> 面向新手，按学习顺序递进。先理解「是什么」和「怎么跑」，再深入「怎么实现」。

---

## 第 0 章：项目概览 — 这是什么？

### 一句话描述

**一个用自然语言提问，AI 自动生成 SQL + Python 代码分析数据库，最后生成图表的智能数据分析工具。**

### 用户能做什么？

```
用户输入：「上个月销售额最高的 10 个产品是哪些？用柱状图展示」

系统自动：
1. 理解意图 → 这是数据分析请求
2. 召回相关知识 → 哪个表存销售额？字段名叫什么？
3. 生成 SQL → SELECT product_name, SUM(amount) FROM orders WHERE ...
4. 执行 SQL → 拿到查询结果
5. 生成 Python 代码 → 用 matplotlib/echarts 画柱状图
6. 生成报告 → Markdown/HTML 格式，包含图表和数据表
```

### 三个子项目

| 项目 | 技术栈 | 定位 |
|------|--------|------|
| `DataAgent/` | Java Spring Boot + Vue 3 | **生产级完整版**，全部功能 |
| `python-agent-v2/` | Python FastAPI + LangGraph + Vue 3 | **Python 复刻版**，对标 Java 能力 |
| `java-style-mvp/` | Python FastAPI (最简) | **教学 MVP**，理解核心概念 |

**本指南覆盖前两个项目：Java 版本是「参考答案」，Python 版本是「当前实现」。**

---

## 第 1 章：先把项目跑起来

### 1.1 启动 Python 后端

```bash
cd python-agent-v2

# 1. 创建虚拟环境 (首次)
python -m venv .venv
.venv\Scripts\activate    # Windows
source .venv/bin/activate  # Mac/Linux

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置数据库连接 (.env 文件)
DATABASE_URL=mysql+aiomysql://root:password@localhost:3306/dataagent

# 4. 启动服务
python -m app.main
# 访问 http://localhost:8000/docs 查看 API 文档
```

### 1.2 启动 Java 后端

```bash
cd DataAgent/data-agent-management

# H2 内存数据库模式 (开发推荐，无需装 MySQL)
./mvnw spring-boot:run -Dspring-boot.run.profiles=h2

# 访问 http://localhost:8065/h2-console 查看数据库
```

### 1.3 启动前端

```bash
cd DataAgent/data-agent-frontend
npm install
npm run dev

# 访问 http://localhost:3000
```

### 1.4 验证所有服务

| 服务 | 地址 | 验证方式 |
|------|------|---------|
| Python 后端 | `http://localhost:8000/docs` | Swagger 文档页 |
| Python 后端 | `http://localhost:8000/health` | 返回 `{"status": "healthy"}` |
| Java 后端 | `http://localhost:8065` | 返回 API 响应 |
| 前端 | `http://localhost:3000` | 看到智能体列表页 |

---

## 第 2 章：前端 — 用户能看到什么？(页面地图)

### 2.1 技术栈

```
Vue 3 (Composition API) + Element Plus (UI 组件库)
+ ECharts (图表) + Axios (HTTP 请求)
+ Vue Router (路由) + Markdown-it (渲染)
```

### 2.2 页面路由结构

```
/                          → 重定向到 /agents
/agents                    → AgentList    智能体列表页 (首页)
/agent/create              → AgentCreate  创建智能体
/agent/:id                 → AgentDetail  智能体详情/配置页
/agent/:id/run             → AgentRun     运行智能体 (核心对话页)
/model-config              → ModelConfig  模型配置页
```

### 2.3 核心页面详解

#### 页面 1: AgentList（智能体列表）

```
┌──────────────────────────────────────────────┐
│  [Logo] Spring AI Alibaba Data Agent         │
│  [智能体列表]  [模型配置]                     │
├──────────────────────────────────────────────┤
│  [+ 创建智能体]  [搜索框]  [状态筛选]        │
│                                              │
│  ┌─────────────────────────────┐            │
│  │ 🤖 销售分析助手    [已发布] │ [运行]     │
│  │ 分析销售数据，生成报告...    │ [编辑]     │
│  └─────────────────────────────┘            │
│  ┌─────────────────────────────┐            │
│  │ 🤖 用户分析助手    [草稿]   │ [运行]     │
│  └─────────────────────────────┘            │
└──────────────────────────────────────────────┘

调用的 API: GET /api/agent/list?status=&keyword=
```

#### 页面 2: AgentDetail（智能体配置）

这是最复杂的页面，包含 **7 个配置 Tab**：

```
┌──────────────────────────────────────────────┐
│  [< 返回]  [头像] 销售分析助手               │
│                                              │
│  [基础设置] [数据源] [知识库] [语义模型]     │
│  [业务知识] [预设问题] [API 接入]            │
│                                              │
│  Tab1 基础设置: 名称、描述、Prompt、模型选择 │
│  Tab2 数据源:   绑定数据库、选择表 & 字段    │
│  Tab3 知识库:   上传文档、Q&A 知识管理       │
│  Tab4 语义模型: 业务术语 → 字段映射          │
│  Tab5 业务知识: 业务术语库                   │
│  Tab6 预设问题: 推荐问题列表                 │
│  Tab7 API接入:  生成/管理 API Key            │
└──────────────────────────────────────────────┘

对应组件:
- BaseSetting.vue, DataSourceConfig.vue, AgentKnowledgeConfig.vue
- SemanticsConfig.vue, BusinessKnowledgeConfig.vue
- PresetsConfig.vue, AccessApi.vue
```

#### 页面 3: AgentRun（运行 / 对话分析）★ 核心

```
┌──────────────────────────────────────────────────────┐
│  [会话列表]  │         对话区域                      │
│  ┌──────────┐│                                      │
│  │ 新对话    ││   👤 用户: 本月销售额前10的产品？     │
│  │ 销售分析  ││                                      │
│  │ 用户分析  ││   🤖 助手:                           │
│  │ [+ 新会话]││   [SQL 代码]                        │
│  │          ││   SELECT product, SUM(amount)...     │
│  └──────────┘│                                      │
│              │   [数据表格]                         │
│  ┌──────────┐│   | 产品 | 销售额 |                 │
│  │ 预设问题  ││   | ... | ...   |                 │
│  │ · 本月.. ││                                      │
│  │ · 用户.. ││   [图表 📊]                         │
│  └──────────┘│                                      │
│              │   ┌──────────────────┐              │
│ 输入框:      │   [同意] [拒绝] [修改] (人工审批)    │
│ [输入问题...]│                                      │
└──────────────────────────────────────────────────────┘

关键组件:
- ChatSessionSidebar.vue (左侧会话列表)
- PresetQuestions.vue (预设快捷问题)
- MarkdownAgentContainer.vue (AI 回复渲染)
- ResultSetDisplay.vue (数据表格)
- ChartComponent.vue (ECharts 图表)
- HumanFeedback.vue (人工审批按钮)
```

### 2.4 前端如何调用后端？

前端有 **14 个 API Service 文件**，每个对应一组后端 API：

```
src/services/
├── agent.ts              → /api/agent/*          (智能体 CRUD + API Key)
├── datasource.ts         → /api/datasource/*     (数据源 CRUD + 测试)
├── agentDatasource.ts    → /api/agent/{id}/datasources/*  (绑定管理)
├── agentKnowledge.ts     → /api/agent-knowledge/*  (知识库)
├── businessKnowledge.ts  → /api/business-knowledge/* (业务术语)
├── semanticModel.ts      → /api/semantic-model/*   (语义模型)
├── chat.ts               → /api/agent/{id}/sessions, /api/sessions/* (会话)
├── graph.ts              → /api/stream/search      (流式分析 SSE)
├── modelConfig.ts        → /api/model-config/*     (模型配置)
├── presetQuestion.ts     → /api/agent/{id}/preset-questions
├── logicalRelation.ts    → /api/datasource/{id}/logical-relations/*
├── resultSet.ts          → (数据集处理)
├── fileUpload.ts         → /api/upload/*           (文件上传)
└── common.ts             → ApiResponse<T> 类型定义
```

**关键约定**：前端期望的响应格式是 `ApiResponse<T>`：

```typescript
interface ApiResponse<T> {
  success: boolean;   // 是否成功
  message: string;    // 提示消息
  data?: T;           // 实际数据
}
```

---

## 第 3 章：后端架构全景 (Python 版)

### 3.1 目录结构总览

```
python-agent-v2/app/
├── main.py                  # FastAPI 入口，注册所有路由 & 中间件
├── api/                     # 13 个控制器 (API 层)
│   ├── agent_controller.py              # Agent CRUD + API Key
│   ├── datasource_controller.py         # 数据源 CRUD + 表结构
│   ├── agent_datasource_controller.py   # Agent-数据源绑定
│   ├── agent_knowledge_controller.py    # 知识库管理
│   ├── agent_preset_question_controller.py  # 预设问题
│   ├── semantic_model_controller.py     # 语义模型
│   ├── model_config_controller.py       # 模型配置
│   ├── chat_controller.py              # 会话/消息
│   ├── graph_controller.py             # 同步查询
│   ├── streaming_graph_controller.py   # SSE 流式查询 ★
│   ├── query_plan_controller.py        # 查询计划
│   ├── schema_controller.py            # 数据库 Schema
│   └── feedback_controller.py          # 人工反馈
│
├── models/                  # 13 个 ORM 模型 (数据库表)
│   ├── agent.py, datasource.py, knowledge.py
│   ├── semantic_model.py, model_config.py
│   ├── chat_session.py, chat_message.py
│   ├── agent_datasource.py, agent_datasource_tables.py
│   ├── agent_preset_question.py, logical_relation.py
│   ├── query_plan.py, human_feedback.py
│
├── schemas/                 # Pydantic 请求/响应模型
│   └── (一一对应 models/)
│
├── services/                # 业务逻辑层
│   ├── agent_service.py, datasource_service.py
│   ├── knowledge_service.py, semantic_model_service.py
│   ├── chat_service.py, schema_service.py
│   └── ...
│
├── workflows/               # ★ LangGraph 工作流 (核心)
│   ├── graph.py             # 工作流图定义 (拓扑结构)
│   ├── state.py             # WorkflowState (50+ 状态字段)
│   └── nodes/               # 16 个工作流节点
│       ├── intent_recognition.py    # 意图识别
│       ├── knowledge_recall.py      # 知识召回 (RAG)
│       ├── query_rewrite.py         # 查询改写
│       ├── schema_recall.py         # Schema 召回
│       ├── table_relation.py        # 表关系构建
│       ├── feasibility.py           # 可行性评估
│       ├── planner.py               # 计划生成
│       ├── plan_executor.py         # 计划执行器 (循环调度)
│       ├── sql_generate.py          # SQL 生成
│       ├── semantic_consistency.py  # 语义一致性校验
│       ├── sql_execute.py           # SQL 执行
│       ├── python_generate.py       # Python 代码生成
│       ├── python_execute.py        # Python 执行
│       ├── python_analyze.py        # Python 结果分析
│       ├── report_generator.py      # 报告生成
│       └── human_feedback_node.py   # 人工反馈
│
└── core/                    # 基础设施
    ├── config.py            # 配置管理 (Settings)
    ├── database.py          # 数据库连接 (SQLAlchemy async)
    ├── response_middleware.py  # ApiResponse 自动包装
    ├── exception_handlers.py   # 全局异常处理
    └── base_service.py      # 通用 CRUD 基类
```

### 3.2 请求处理流程 (从 HTTP 到响应)

```
HTTP 请求
  │
  ▼
FastAPI Router (api/*.py)
  │  匹配 URL → 调用对应函数
  ▼
Pydantic 校验 (schemas/*.py)
  │  请求体自动校验/转换
  ▼
Service (services/*.py)
  │  业务逻辑，数据库操作
  ▼
SQLAlchemy Model (models/*.py)
  │  ORM 映射 → MySQL 数据库
  ▼
Response (自动包装)
  │  ApiResponseMiddleware → {success, message, data}
  ▼
JSON 响应返回前端
```

---

## 第 4 章：工作流引擎 — 核心魔法 ★★★

这是整个项目最核心的部分。理解了工作流，就理解了整个系统。

### 4.1 什么是 LangGraph StateGraph？

LangGraph 是一个**有向图**，每个节点是一个处理函数，边定义了节点间的流转规则。

```
类比：工厂流水线
  原材料(用户问题) → 工位1(理解意图) → 工位2(查知识库) → ... → 成品(分析报告)
```

### 4.2 完整工作流拓扑

```
                        START
                          │
                          ▼
                   ┌──────────────┐
                   │ 1. 意图识别   │ "这是数据分析还是闲聊？"
                   └──────┬───────┘
                          │
              ┌───────────┼───────────┐
              │ (闲聊)    │           │ (数据分析)
              ▼           │           ▼
            END           │    ┌──────────────┐
                          │    │ 2. 知识召回   │ "销售额在哪个表？"
                          │    └──────┬───────┘
                          │           ▼
                          │    ┌──────────────┐
                          │    │ 3. 查询改写   │ "用更精准的关键词检索"
                          │    └──────┬───────┘
                          │           ▼
                          │    ┌──────────────┐
                          │    │ 4. Schema召回 │ "读取数据库表结构"
                          │    └──────┬───────┘
                          │           ▼
                          │    ┌──────────────┐
                          │    │ 5. 表关系     │ "orders.user_id → users.id"
                          │    └──────┬───────┘
                          │           ▼
                          │    ┌──────────────┐
                          │    │ 6. 可行性评估 │ "这个问题能回答吗？"
                          │    └──────┬───────┘
                          │           ▼
                          │    ┌──────────────┐
                          │    │ 7. 计划生成   │ "分3步: SQL→Python→报告"
                          │    └──────┬───────┘
                          │           ▼
                          │    ┌──────────────────────────────────┐
                          │    │ 8. 计划执行器 (循环调度)          │
                          │    │                                  │
                          │    │  ┌─ SQL 流水线 ──────────────┐  │
                          │    │  │ 8a. 生成SQL → 8b. 语义校验│  │
                          │    │  │    → 8c. 执行SQL          │  │
                          │    │  └──────────────────────────┘  │
                          │    │                                  │
                          │    │  ┌─ Python 流水线 ───────────┐  │
                          │    │  │ 9a. 生成代码 → 9b. 执行   │  │
                          │    │  │   → 9c. 分析结果         │  │
                          │    │  └──────────────────────────┘  │
                          │    │                                  │
                          │    │  ┌─ 人工审批 ──────────────┐   │
                          │    │  │ 10. 人工反馈 (暂停等待)  │   │
                          │    │  └──────────────────────────┘   │
                          │    │                                  │
                          │    │  ┌─ 报告生成 ──────────────┐   │
                          │    │  │ 11. 报告生成 → END       │   │
                          │    │  └──────────────────────────┘   │
                          │    └──────────────────────────────────┘
                          │           │
                          ▼           ▼
                        END         END
```

### 4.3 WorkflowState — 工作流的「记忆」

所有节点通过一个共享的 `WorkflowState` (TypedDict) 传递数据。这就像工作流执行过程中的「白板」：

```python
class WorkflowState(TypedDict):
    # 输入
    agent_id: int           # 哪个 Agent
    user_query: str         # 用户的问题

    # 意图识别输出
    intent: str             # "data_analysis" | "chitchat"

    # 知识召回输出
    recalled_knowledge: str  # 召回的相关知识文本
    recalled_business_terms: str  # 业务术语

    # Schema 输出
    schema: str             # 数据库表结构 (DDL 文本)
    schema_info: dict       # 结构化的 Schema

    # Planner 输出
    query_plan: dict        # 多步骤执行计划

    # SQL 流水线输出
    generated_sql: str      # 生成的 SQL
    sql_result: list        # SQL 执行结果

    # Python 流水线输出
    python_code: str        # 生成的 Python 代码
    python_output: str      # Python 执行输出

    # 报告输出
    report: str             # Markdown 报告
    html_report: str        # HTML 报告
    display_style: dict     # 图表配置

    # 人工反馈
    human_feedback_data: dict  # 等待审批的数据

    # 错误/重试
    error: str              # 错误信息
    sql_retry_count: int    # SQL 重试次数
```

### 4.4 前端如何驱动工作流？(SSE 流式交互)

前端使用 **EventSource (SSE)** 连接后端的 `/api/stream/search` 端点：

```
前端: GET /api/stream/search?agentId=1&query=销售额前10&...

后端 (SSE 流式响应):
  event: start       data: {"message": "开始处理查询"}
  event: intent      data: {"intent": "data_analysis"}
  event: knowledge   data: {"knowledge": "orders 表存储..."}
  event: plan        data: {"plan": {...}}
  event: sql         data: {"sql": "SELECT ..."}        ← textType: SQL
  event: sql_result  data: {"count": 10, "columns": [...]} ← textType: JSON
  event: python_code  data: {"code": "import matplotlib..."} ← textType: Python
  event: report      data: {"report": "# 分析报告..."}     ← textType: Markdown
  event: done        data: {"message": "查询完成"}

前端根据 event 类型和 textType 标记，选择不同的渲染组件：
  SQL      → 代码高亮 (<pre><code>)
  JSON     → 数据表格 (ResultSetDisplay)
  Markdown → Markdown 渲染 (MarkdownAgentContainer)
  Python   → 代码高亮
  HTML     → 直接渲染 (v-html)
```

### 4.5 人工反馈 (Human-in-the-Loop)

```
1. 用户输入问题 → 系统生成执行计划
2. 计划发送到前端展示 → 前端显示 [同意] [拒绝] [修改] 按钮
3. 用户点击 → 前端携带 humanFeedbackContent + threadId 再次请求
4. LangGraph 从暂停点恢复 → 继续执行或退回 Planner 重新规划
```

---

## 第 5 章：数据模型 — 数据库里有什么？

### 5.1 核心表关系

```
┌──────────┐      ┌─────────────────┐      ┌──────────────┐
│  Agent   │1───* │ AgentDatasource │*───1 │  Datasource  │
│  智能体   │      │   绑定关系       │      │   数据源      │
└────┬─────┘      └─────────────────┘      └──────┬───────┘
     │                                            │
     │1                                           │1
     ├─────────────*──────────────────────────────┤
     │              │              │              │
     ▼              ▼              ▼              ▼
┌─────────┐  ┌───────────┐  ┌───────────┐  ┌──────────────┐
│Knowledge│  │SemanticModel│ │LogicalRela│  │AgentDatasource│
│ 知识库   │  │  语义模型   │  │ 逻辑关系   │  │   Tables     │
└─────────┘  └───────────┘  └───────────┘  └──────────────┘

┌──────────┐      ┌──────────────┐      ┌──────────────┐
│  Agent   │1───* │ ChatSession  │1───* │ ChatMessage  │
│          │      │   会话        │      │   消息        │
└──────────┘      └──────────────┘      └──────────────┘

其他独立表:
┌─────────────────┐  ┌──────────────┐  ┌─────────────┐
│  ModelConfig     │  │ QueryPlan    │  │HumanFeedback│
│  模型配置 (LLM)  │  │ 查询计划记录  │  │ 人工反馈记录 │
└─────────────────┘  └──────────────┘  └─────────────┘
```

### 5.2 关键表详解

**Agent (智能体)** — 项目的核心实体：
| 字段 | 说明 |
|------|------|
| name | 名称，如「销售分析助手」 |
| status | draft → published → offline 生命周期 |
| prompt | 自定义 System Prompt |
| api_key / api_key_enabled | 外部调用鉴权 |

**Datasource (数据源)** — 要分析的数据库连接：
| 字段 | 说明 |
|------|------|
| type | mysql / postgresql / sqlite |
| host, port, database | 连接信息 |
| test_status | untested / success / failed |

**SemanticModel (语义模型)** — 业务语言到数据库字段的翻译：
```
用户说：「销售额」 → SemanticModel 翻译成 → orders.amount
用户说：「上个月」 → SemanticModel 翻译成 → WHERE created_at >= '2026-04-01'
```

**Knowledge (知识库)** — RAG 检索的数据源：
| 类型 | 说明 |
|------|------|
| DOCUMENT | 文档知识 (从文件上传) |
| QA | 问答对 |
| FAQ | 常见问题 |

---

## 第 6 章：API 全景 — 所有端点速查

### 6.1 端点汇总 (Python 版，13 个控制器)

| 控制器 | 前缀 | 端点数 | 核心功能 |
|--------|------|--------|---------|
| agent_controller | `/api/agent` | 12 | Agent CRUD + publish/offline + API Key (5) |
| agent_preset_question | `/api/agent` | 3 | 预设问题 CRUD |
| agent_datasource | `/api/agent` | 5 | 数据源绑定/解绑/激活 |
| agent_knowledge | `/api/agent/{id}/knowledge` | 6 | 知识库 CRUD + 检索 |
| semantic_model | `/api/agent/{id}/semantic-models` | 6 | 语义模型 CRUD |
| query_plan | `/api/agent/{id}/plans` | 4 | 查询计划 CRUD |
| datasource | `/api/datasource` | 9 | 数据源 CRUD + 测试 + 表结构 |
| model_config | `/api/model-config` | 7 | 模型 CRUD + 测试 + 切换 |
| chat | `/api` | 9 | 会话 CRUD + 消息 + 报告 |
| graph | `/api` | 1 | 同步查询 (POST /api/query) |
| streaming_graph | `/api` | 2 | SSE 流式查询 |
| schema | `/api/schema` | 5 | 数据库 DDL/表结构查询 |
| feedback | (无前缀) | 5 | 人工反馈 CRUD |

### 6.2 最重要的 5 个端点

| 端点 | 作用 | 调用时机 |
|------|------|---------|
| `POST /api/agent` | 创建智能体 | AgentCreate 页面 |
| `GET /api/stream/search` | **SSE 流式分析** | AgentRun 页发起对话 |
| `POST /api/agent/{id}/sessions` | 创建会话 | 开始新对话 |
| `POST /api/sessions/{id}/messages` | 保存消息 | 每次对话 |
| `GET /api/datasource/{id}/tables` | 获取表列表 | 配置数据源 |

### 6.3 Python vs Java 端点对齐状态

| 阶段 | 内容 | 状态 |
|------|------|------|
| 1 | URL 前缀统一 + ApiResponse 包装 | ✅ |
| 2 | Chat 会话 API (9 端点) | ✅ |
| 3 | Agent API Key + PresetQuestion (8 端点) | ✅ |
| 4 | LogicalRelation + Datasource Tables | ⏳ |
| 5 | Knowledge/BusinessKnowledge 对齐 | ⏳ |
| 6 | SemanticModel 批量操作 | ⏳ |
| 7 | ModelConfig 字段补全 + FileUpload | ⏳ |

---

## 第 7 章：推荐学习路径 (按顺序)

### 阶段 A: 理解概念 (1-2 天)

1. **跑起来**: 启动前后端，创建一个 Agent，绑定数据源，问一个问题，看到图表
2. **读前端路由**: `router/routes.js` — 理解 6 个页面
3. **读 AgentRun.vue**: 理解核心对话页面的组件构成
4. **读 WorkflowState**: `workflows/state.py` — 理解 50+ 个状态字段的含义

### 阶段 B: 跟一条完整请求 (2-3 天)

从 `AgentRun.vue` 的搜索框输入开始跟踪：

```
1. 前端: graph.ts streamSearch() → GET /api/stream/search (SSE)
2. 后端: streaming_graph_controller.py → stream_workflow_execution()
3. 构建初始 State → compiled_workflow.astream()
4. LangGraph 执行: intent_recognition → knowledge_recall → ... → report_generator
5. 每步 yield SSE event → 前端 onMessage() 解析 event
6. 前端根据 textType 渲染: SQL/JSON/Markdown/HTML
```

**重点理解 3 个文件**：
- `workflows/graph.py` — 图的拓扑结构
- `api/streaming_graph_controller.py` — SSE 事件的发送
- `services/graph.ts` — SSE 事件的接收和渲染

### 阶段 C: 深入配置流程 (2-3 天)

1. **AgentDetail.vue 的 7 个 Tab** — 每个 Tab 对应一个后端 API 模块
2. 依次理解: BaseSetting → DataSource → Knowledge → SemanticModel → BusinessKnowledge → Presets → API Key
3. 每个 Tab 的「编辑 → 保存 → API 调用 → 数据库写入」完整链路

### 阶段 D: 掌握工作流节点 (3-5 天)

逐个阅读 `workflows/nodes/` 下的 16 个节点，理解：
- 每个节点的**输入**是什么 (从 state 读取哪些字段)
- 每个节点的**输出**是什么 (写入 state 哪些字段)
- 每个节点的**路由逻辑**是什么 (什么条件下走哪个分支)

### 阶段 E: 完整串联 (2-3 天)

自己尝试：
1. 用前端创建一个 Agent → 配置数据源 → 添加知识 → 创建语义模型 → 开始对话
2. 在 `AgentRun.vue` 打断点，观察 SSE 事件的完整流程
3. 在 `streaming_graph_controller.py` 打日志，观察每个节点的执行
4. 理解 HumanFeedback 的 pause/resume 机制

### 阶段 F: 对比 Java 版本 (3-5 天)

1. 阅读 Java `workflow/node/` 目录 — 16 个 Java 节点
2. 对比 Java vs Python 同节点实现差异
3. 阅读 Java `GraphServiceImpl.java` — 流式执行逻辑
4. 阅读 Java `service/` 目录 — 业务服务层对比

---

## 第 8 章：关键文件速查表

### 想了解...就看这个

| 问题 | 前端看 | 后端看 |
|------|--------|--------|
| 有哪些页面？ | `router/routes.js` | — |
| API 怎么调？ | `services/*.ts` | `api/*.py` |
| 请求/响应格式？ | `services/common.ts` | `schemas/common.py` |
| 数据库有哪些表？ | — | `models/*.py` |
| 工作流怎么串起来？ | — | `workflows/graph.py` |
| 工作流状态有哪些？ | — | `workflows/state.py` |
| SQL 怎么生成的？ | — | `workflows/nodes/sql_generate.py` |
| Python 怎么执行的？ | — | `workflows/nodes/python_execute.py` |
| 报告怎么生成的？ | — | `workflows/nodes/report_generator.py` |
| SSE 怎么实现的？ | `services/graph.ts` | `api/streaming_graph_controller.py` |
| 人工审批怎么暂停/恢复？ | `components/run/HumanFeedback.vue` | `workflows/nodes/human_feedback_node.py` |
| 图表怎么渲染？ | `components/run/charts/*.ts` | — |
| 数据库配置在哪？ | — | `core/config.py` + `.env` |
| URL 前缀怎么定义？ | `services/*.ts` 中的 `API_BASE_URL` | `api/*.py` 中的 `router = APIRouter(prefix=...)` |

---

## 附录 A: 常用命令速查

```bash
# === Python 后端 ===
cd python-agent-v2
.venv\Scripts\activate                     # 激活虚拟环境
python -m app.main                          # 启动服务
uvicorn app.main:app --reload --port 8000   # 开发模式热重载

# === Java 后端 ===
cd DataAgent/data-agent-management
./mvnw spring-boot:run -Dspring-boot.run.profiles=h2  # H2 模式
./mvnw test -Dtest=AgentControllerTest                # 运行特定测试

# === 前端 ===
cd DataAgent/data-agent-frontend
npm run dev              # 启动 (http://localhost:3000)
npm run build            # 构建
npm run lint             # 代码检查
npm run type-check       # TypeScript 检查

# === 数据库 ===
mysql -u root -p -e "CREATE DATABASE dataagent CHARACTER SET utf8mb4;"
mysql -u root -p dataagent  # 连接数据库
```

## 附录 B: 概念对照表 (Java ↔ Python)

| Java 概念 | Python 对应 | 位置 |
|-----------|------------|------|
| `@RestController` | `APIRouter` | `api/*.py` |
| `@RequestMapping("/api/agent")` | `prefix="/api/agent"` | `api/*.py` |
| `@Entity` + `@Table` | `Base` + `__tablename__` | `models/*.py` |
| `AgentService` (Spring) | `AgentService` (Static) | `services/*.py` |
| `StateGraph` (Spring AI) | `StateGraph` (LangGraph) | `workflows/graph.py` |
| `Constant.java` (StateKey) | `StateKeys` class | `workflows/state.py` |
| `ApiResponse<T>` | `{success, message, data}` | `core/response_middleware.py` |
| `Flux<ServerSentEvent>` (SSE) | `StreamingResponse` (SSE) | `api/streaming_graph_controller.py` |
| `TextType` enum | `TEXT_TYPE_*` constants | `api/streaming_graph_controller.py` |
| `SseEmitter` | `yield` + SSE format | `api/streaming_graph_controller.py` |
| `EventSource` (前端) | `EventSource` (前端) | `services/graph.ts` |
| `Checkpoint` (LangGraph) | `checkpointer` | `workflows/graph.py` |
