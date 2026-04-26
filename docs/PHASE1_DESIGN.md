# Phase 1 技术方案设计

## 目标

实现核心 Text-to-SQL 能力的 MVP 版本，包含：
- 意图识别
- 数据库模式检索
- SQL 生成
- SQL 执行
- 简单文本报告

## 技术选型

### 1. Web 框架：FastAPI

**选择理由：**
- 高性能异步框架
- 自动生成 OpenAPI 文档
- 类型提示支持
- 与 Java Spring Boot 的 REST 风格对齐

**版本：** FastAPI 0.115+

### 2. ORM：SQLAlchemy 2.0

**选择理由：**
- Python 最成熟的 ORM
- 支持异步操作（async/await）
- 类型提示友好
- 对标 Java MyBatis 的灵活性

**版本：** SQLAlchemy 2.0+

**核心特性：**
- 使用 `DeclarativeBase` 作为基类
- 使用 `Mapped[T]` 类型注解
- 异步 Session 管理
- 关系映射（relationship）

### 3. 工作流引擎：LangGraph

**选择理由：**
- 与 Java StateGraph 概念一致
- 原生支持 LLM 工作流编排
- 支持条件路由和循环
- 状态管理清晰

**版本：** langgraph 0.2+

**核心概念：**
- `StateGraph` - 工作流图
- `Node` - 工作流节点（函数）
- `State` - 共享状态（TypedDict）
- `Edge` - 节点连接

### 4. 数据库：MySQL (开发可用 SQLite)

**选择理由：**
- 与 Java 版本保持一致
- 生产环境使用 MySQL
- 开发环境可用 SQLite 快速启动

**版本：** MySQL 8.0+ / SQLite 3.35+

### 5. LLM 客户端：OpenAI SDK

**选择理由：**
- 标准的 OpenAI 兼容接口
- 支持流式输出
- 易于切换不同模型（Qwen、Deepseek 等）

**版本：** openai 1.0+

### 6. 数据验证：Pydantic V2

**选择理由：**
- FastAPI 原生集成
- 强类型验证
- 自动生成 JSON Schema

**版本：** pydantic 2.0+

## 架构设计

### 分层架构

```
┌─────────────────────────────────────┐
│         API Layer (FastAPI)         │  路由、请求/响应处理
├─────────────────────────────────────┤
│      Service Layer (Business)       │  业务逻辑、工作流编排
├─────────────────────────────────────┤
│     Workflow Layer (LangGraph)      │  工作流节点、状态管理
├─────────────────────────────────────┤
│       Data Layer (SQLAlchemy)       │  数据访问、ORM 映射
├─────────────────────────────────────┤
│      Database (MySQL/SQLite)        │  数据持久化
└─────────────────────────────────────┘
```

### 工作流设计

Phase 1 工作流节点：

```mermaid
graph LR
    Start([开始]) --> Intent[IntentRecognitionNode]
    Intent --> NeedAnalysis{需要分析?}
    NeedAnalysis -->|否| End([结束])
    NeedAnalysis -->|是| Schema[SchemaRecallNode]
    Schema --> SqlGen[SqlGenerateNode]
    SqlGen --> SqlExec[SqlExecuteNode]
    SqlExec --> Success{执行成功?}
    Success -->|否| SqlGen
    Success -->|是| Report[SimpleReportNode]
    Report --> End
```

**节点说明：**

1. **IntentRecognitionNode**
   - 输入：用户问题
   - 输出：意图分类（chitchat / data_analysis）
   - LLM：使用 Chat 模型判断

2. **SchemaRecallNode**
   - 输入：Agent ID
   - 输出：数据库表结构（表名、字段、类型、注释）
   - 数据源：从 `datasource` 表读取连接信息，动态查询 schema

3. **SqlGenerateNode**
   - 输入：用户问题 + 数据库 schema
   - 输出：SQL 语句
   - LLM：使用 Chat 模型生成 SQL
   - 重试：最多 3 次（Phase 1 简化）

4. **SqlExecuteNode**
   - 输入：SQL 语句 + 数据源连接
   - 输出：查询结果（JSON 格式）
   - 执行：使用 SQLAlchemy 动态执行

5. **SimpleReportNode**
   - 输入：用户问题 + SQL + 查询结果
   - 输出：简单文本报告
   - LLM：使用 Chat 模型生成自然语言描述

### 状态定义

```python
from typing import TypedDict, Optional, List, Dict, Any

class WorkflowState(TypedDict):
    """工作流状态"""
    # 输入
    agent_id: int
    user_query: str
    
    # 意图识别
    intent: Optional[str]  # "chitchat" | "data_analysis"
    
    # 数据库 schema
    schema_info: Optional[Dict[str, Any]]
    
    # SQL 生成
    generated_sql: Optional[str]
    sql_retry_count: int
    
    # SQL 执行
    sql_result: Optional[List[Dict[str, Any]]]
    sql_error: Optional[str]
    
    # 报告
    report: Optional[str]
```

## 数据模型设计

### Phase 1 核心表

Phase 1 只需要 3 张表：

#### 1. agent 表

```python
class Agent(Base):
    __tablename__ = "agent"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft, published, offline
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    datasources: Mapped[List["AgentDatasource"]] = relationship(back_populates="agent")
```

#### 2. datasource 表

```python
class Datasource(Base):
    __tablename__ = "datasource"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(20))  # mysql, postgresql, sqlite
    host: Mapped[Optional[str]] = mapped_column(String(255))
    port: Mapped[Optional[int]]
    database: Mapped[str] = mapped_column(String(100))
    username: Mapped[Optional[str]] = mapped_column(String(100))
    password: Mapped[Optional[str]] = mapped_column(String(255))
    connection_url: Mapped[Optional[str]] = mapped_column(String(500))  # SQLite 使用
    test_status: Mapped[str] = mapped_column(String(20), default="untested")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    agent_datasources: Mapped[List["AgentDatasource"]] = relationship(back_populates="datasource")
```

#### 3. agent_datasource 表（关联表）

```python
class AgentDatasource(Base):
    __tablename__ = "agent_datasource"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agent.id"))
    datasource_id: Mapped[int] = mapped_column(ForeignKey("datasource.id"))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    
    # 关系
    agent: Mapped["Agent"] = relationship(back_populates="datasources")
    datasource: Mapped["Datasource"] = relationship(back_populates="agent_datasources")
```

### Pydantic Schemas

#### 请求/响应模型

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# Agent
class AgentCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None

class AgentResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}

# Datasource
class DatasourceCreate(BaseModel):
    name: str = Field(..., max_length=100)
    type: str = Field(..., pattern="^(mysql|postgresql|sqlite)$")
    host: Optional[str] = None
    port: Optional[int] = None
    database: str
    username: Optional[str] = None
    password: Optional[str] = None
    connection_url: Optional[str] = None

class DatasourceResponse(BaseModel):
    id: int
    name: str
    type: str
    database: str
    test_status: str
    created_at: datetime
    
    model_config = {"from_attributes": True}

# Query
class QueryRequest(BaseModel):
    agent_id: int
    query: str = Field(..., min_length=1)

class QueryResponse(BaseModel):
    intent: str
    sql: Optional[str] = None
    result: Optional[List[Dict[str, Any]]] = None
    report: Optional[str] = None
    error: Optional[str] = None
```

## API 设计

### Phase 1 API 端点

#### 1. Agent 管理

```
POST   /api/agents              创建 Agent
GET    /api/agents              列出所有 Agent
GET    /api/agents/{id}         获取 Agent 详情
PUT    /api/agents/{id}         更新 Agent
DELETE /api/agents/{id}         删除 Agent
```

#### 2. Datasource 管理

```
POST   /api/datasources         创建数据源
GET    /api/datasources         列出所有数据源
GET    /api/datasources/{id}    获取数据源详情
POST   /api/datasources/{id}/test  测试连接
```

#### 3. Agent-Datasource 关联

```
POST   /api/agents/{agent_id}/datasources/{datasource_id}  绑定数据源
DELETE /api/agents/{agent_id}/datasources/{datasource_id}  解绑数据源
GET    /api/agents/{agent_id}/datasources                  列出 Agent 的数据源
```

#### 4. 查询执行

```
POST   /api/query               执行查询（核心接口）
```

**请求示例：**
```json
{
  "agent_id": 1,
  "query": "查询销售额最高的前10个产品"
}
```

**响应示例：**
```json
{
  "intent": "data_analysis",
  "sql": "SELECT product_name, SUM(amount) as total_sales FROM sales GROUP BY product_name ORDER BY total_sales DESC LIMIT 10",
  "result": [
    {"product_name": "产品A", "total_sales": 10000},
    {"product_name": "产品B", "total_sales": 8000}
  ],
  "report": "根据查询结果，销售额最高的产品是产品A，总销售额为10000元..."
}
```

## 配置管理

### 环境变量（.env）

```env
# 应用配置
APP_NAME=Python Agent V2
APP_VERSION=0.1.0
DEBUG=true

# 数据库配置
DATABASE_URL=mysql+aiomysql://root:password@localhost:3306/dataagent
# 或 SQLite: sqlite+aiosqlite:///./dataagent.db

# LLM 配置
OPENAI_API_KEY=your-api-key
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_MODEL=gpt-4
OPENAI_TEMPERATURE=0.0

# 服务配置
HOST=0.0.0.0
PORT=8100

# 日志配置
LOG_LEVEL=INFO
```

### 配置类（config.py）

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 应用
    app_name: str = "Python Agent V2"
    debug: bool = False
    
    # 数据库
    database_url: str
    
    # LLM
    openai_api_key: str
    openai_api_base: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4"
    openai_temperature: float = 0.0
    
    # 服务
    host: str = "0.0.0.0"
    port: int = 8100
    
    # 日志
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"

settings = Settings()
```

## 项目结构

```
python-agent-v2/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 应用入口
│   │
│   ├── api/                       # API 路由
│   │   ├── __init__.py
│   │   ├── agents.py              # Agent 管理接口
│   │   ├── datasources.py         # 数据源管理接口
│   │   └── query.py               # 查询执行接口
│   │
│   ├── core/                      # 核心配置
│   │   ├── __init__.py
│   │   ├── config.py              # 配置管理
│   │   ├── database.py            # 数据库连接
│   │   └── llm.py                 # LLM 客户端
│   │
│   ├── models/                    # SQLAlchemy 模型
│   │   ├── __init__.py
│   │   ├── base.py                # Base 类
│   │   ├── agent.py               # Agent 模型
│   │   ├── datasource.py          # Datasource 模型
│   │   └── agent_datasource.py    # 关联模型
│   │
│   ├── schemas/                   # Pydantic 模型
│   │   ├── __init__.py
│   │   ├── agent.py               # Agent schemas
│   │   ├── datasource.py          # Datasource schemas
│   │   └── query.py               # Query schemas
│   │
│   ├── services/                  # 业务逻辑
│   │   ├── __init__.py
│   │   ├── agent_service.py       # Agent 服务
│   │   ├── datasource_service.py  # 数据源服务
│   │   └── query_service.py       # 查询服务
│   │
│   └── workflows/                 # 工作流
│       ├── __init__.py
│       ├── state.py               # 状态定义
│       ├── graph.py               # 工作流图
│       └── nodes/                 # 工作流节点
│           ├── __init__.py
│           ├── intent_recognition.py
│           ├── schema_recall.py
│           ├── sql_generate.py
│           ├── sql_execute.py
│           └── simple_report.py
│
├── scripts/                       # 脚本工具
│   ├── init_db.py                 # 初始化数据库
│   └── seed_data.py               # 种子数据
│
├── tests/                         # 测试
│   ├── __init__.py
│   ├── test_api.py
│   └── test_workflows.py
│
├── docs/                          # 文档
│   ├── PHASE1_DESIGN.md           # 本文件
│   ├── DATABASE_DESIGN.md         # 数据库设计
│   └── API_DESIGN.md              # API 设计
│
├── .env.example                   # 环境变量示例
├── .gitignore
├── requirements.txt               # 依赖
└── README.md
```

## 依赖清单

```txt
# Web 框架
fastapi==0.115.0
uvicorn[standard]==0.30.0

# 数据库
sqlalchemy[asyncio]==2.0.35
aiomysql==0.2.0
aiosqlite==0.20.0

# 数据验证
pydantic==2.9.0
pydantic-settings==2.5.0

# LLM
openai==1.51.0
langgraph==0.2.45
langchain-core==0.3.15

# 工具
python-dotenv==1.0.1
python-multipart==0.0.12

# 开发工具
pytest==8.3.0
pytest-asyncio==0.24.0
httpx==0.27.0
```

## 开发计划

### Day 1: 基础框架搭建
- [x] 创建项目结构
- [ ] 配置管理（config.py）
- [ ] 数据库连接（database.py）
- [ ] ORM 模型定义
- [ ] 初始化脚本

### Day 2: API 开发
- [ ] Agent 管理 API
- [ ] Datasource 管理 API
- [ ] 基础测试

### Day 3: 工作流实现
- [ ] 状态定义
- [ ] 5个工作流节点实现
- [ ] LangGraph 编排
- [ ] 查询 API 集成
- [ ] 端到端测试

## 与后续 Phase 对齐

### 数据库表设计对齐
- Phase 1 的 3 张表是 Java 版本的子集
- 后续 Phase 直接添加新表，不需要修改现有表

### 工作流节点对齐
- Phase 1 的 5 个节点是 Java 版本 16 个节点的核心子集
- 后续 Phase 添加新节点，不影响现有节点

### API 设计对齐
- Phase 1 的 API 路径与 Java 版本保持一致（`/api/agents`, `/api/datasources`）
- 后续 Phase 扩展新接口

### 配置对齐
- 使用环境变量，与 Java 的 `application.yml` 概念对应
- 配置项命名尽量保持一致

## 下一步

完成 Phase 1 后，将具备：
1. ✅ 完整的 Agent 和 Datasource 管理
2. ✅ 核心 Text-to-SQL 能力
3. ✅ 可扩展的工作流架构
4. ✅ 清晰的分层设计

为 Phase 2 的 RAG 检索和计划生成打下坚实基础。
