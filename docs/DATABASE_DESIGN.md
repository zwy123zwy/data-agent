# 数据库设计文档

## Phase 1 数据库表

Phase 1 只需要 3 张核心表，后续 Phase 逐步添加。

---

## 1. agent 表

**用途：** 存储智能体（Agent）的基本信息

### 表结构

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INT | PRIMARY KEY, AUTO_INCREMENT | 主键 |
| name | VARCHAR(100) | NOT NULL | Agent 名称 |
| description | TEXT | NULL | Agent 描述 |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'draft' | 状态：draft/published/offline |
| created_at | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新时间 |

### 索引

```sql
CREATE INDEX idx_agent_status ON agent(status);
CREATE INDEX idx_agent_created_at ON agent(created_at);
```

### SQLAlchemy 模型

```python
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class Agent(Base):
    __tablename__ = "agent"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # 关系
    datasources: Mapped[List["AgentDatasource"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan"
    )
```

### 示例数据

```sql
INSERT INTO agent (name, description, status) VALUES
('销售分析助手', '分析销售数据，生成销售报告', 'published'),
('用户行为分析', '分析用户行为数据', 'draft');
```

---

## 2. datasource 表

**用途：** 存储数据源连接信息

### 表结构

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INT | PRIMARY KEY, AUTO_INCREMENT | 主键 |
| name | VARCHAR(100) | NOT NULL | 数据源名称 |
| type | VARCHAR(20) | NOT NULL | 数据库类型：mysql/postgresql/sqlite |
| host | VARCHAR(255) | NULL | 主机地址（SQLite 不需要） |
| port | INT | NULL | 端口号 |
| database | VARCHAR(100) | NOT NULL | 数据库名 |
| username | VARCHAR(100) | NULL | 用户名 |
| password | VARCHAR(255) | NULL | 密码（加密存储） |
| connection_url | VARCHAR(500) | NULL | 完整连接字符串（SQLite 使用） |
| test_status | VARCHAR(20) | NOT NULL, DEFAULT 'untested' | 测试状态：untested/success/failed |
| created_at | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新时间 |

### 索引

```sql
CREATE INDEX idx_datasource_type ON datasource(type);
CREATE INDEX idx_datasource_test_status ON datasource(test_status);
```

### SQLAlchemy 模型

```python
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class Datasource(Base):
    __tablename__ = "datasource"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(20))
    host: Mapped[Optional[str]] = mapped_column(String(255))
    port: Mapped[Optional[int]] = mapped_column(Integer)
    database: Mapped[str] = mapped_column(String(100))
    username: Mapped[Optional[str]] = mapped_column(String(100))
    password: Mapped[Optional[str]] = mapped_column(String(255))
    connection_url: Mapped[Optional[str]] = mapped_column(String(500))
    test_status: Mapped[str] = mapped_column(String(20), default="untested")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # 关系
    agent_datasources: Mapped[List["AgentDatasource"]] = relationship(
        back_populates="datasource",
        cascade="all, delete-orphan"
    )
```

### 示例数据

```sql
-- MySQL 数据源
INSERT INTO datasource (name, type, host, port, database, username, password, test_status) VALUES
('生产数据库', 'mysql', 'localhost', 3306, 'sales_db', 'root', 'password', 'success');

-- SQLite 数据源
INSERT INTO datasource (name, type, database, connection_url, test_status) VALUES
('本地测试库', 'sqlite', 'test.db', 'sqlite:///./test.db', 'success');
```

---

## 3. agent_datasource 表

**用途：** Agent 和 Datasource 的多对多关联表

### 表结构

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INT | PRIMARY KEY, AUTO_INCREMENT | 主键 |
| agent_id | INT | NOT NULL, FOREIGN KEY | Agent ID |
| datasource_id | INT | NOT NULL, FOREIGN KEY | Datasource ID |
| is_active | BOOLEAN | NOT NULL, DEFAULT TRUE | 是否为当前激活的数据源 |
| created_at | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 创建时间 |

### 约束

```sql
ALTER TABLE agent_datasource 
ADD CONSTRAINT fk_agent_datasource_agent 
FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE;

ALTER TABLE agent_datasource 
ADD CONSTRAINT fk_agent_datasource_datasource 
FOREIGN KEY (datasource_id) REFERENCES datasource(id) ON DELETE CASCADE;

-- 唯一约束：一个 Agent 不能重复绑定同一个 Datasource
ALTER TABLE agent_datasource 
ADD CONSTRAINT uk_agent_datasource 
UNIQUE (agent_id, datasource_id);
```

### 索引

```sql
CREATE INDEX idx_agent_datasource_agent ON agent_datasource(agent_id);
CREATE INDEX idx_agent_datasource_datasource ON agent_datasource(datasource_id);
CREATE INDEX idx_agent_datasource_active ON agent_datasource(is_active);
```

### SQLAlchemy 模型

```python
from datetime import datetime
from sqlalchemy import ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class AgentDatasource(Base):
    __tablename__ = "agent_datasource"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agent.id"))
    datasource_id: Mapped[int] = mapped_column(ForeignKey("datasource.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    
    # 关系
    agent: Mapped["Agent"] = relationship(back_populates="datasources")
    datasource: Mapped["Datasource"] = relationship(back_populates="agent_datasources")
```

### 示例数据

```sql
-- Agent 1 绑定 Datasource 1，并设为激活
INSERT INTO agent_datasource (agent_id, datasource_id, is_active) VALUES
(1, 1, TRUE);

-- Agent 2 绑定 Datasource 2
INSERT INTO agent_datasource (agent_id, datasource_id, is_active) VALUES
(2, 2, TRUE);
```

---

## 完整建表 SQL

### MySQL 版本

```sql
-- 创建数据库
CREATE DATABASE IF NOT EXISTS dataagent 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE dataagent;

-- 1. agent 表
CREATE TABLE agent (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_agent_status (status),
    INDEX idx_agent_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. datasource 表
CREATE TABLE datasource (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(20) NOT NULL,
    host VARCHAR(255),
    port INT,
    database VARCHAR(100) NOT NULL,
    username VARCHAR(100),
    password VARCHAR(255),
    connection_url VARCHAR(500),
    test_status VARCHAR(20) NOT NULL DEFAULT 'untested',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_datasource_type (type),
    INDEX idx_datasource_test_status (test_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. agent_datasource 表
CREATE TABLE agent_datasource (
    id INT AUTO_INCREMENT PRIMARY KEY,
    agent_id INT NOT NULL,
    datasource_id INT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_datasource_agent 
        FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE,
    CONSTRAINT fk_agent_datasource_datasource 
        FOREIGN KEY (datasource_id) REFERENCES datasource(id) ON DELETE CASCADE,
    CONSTRAINT uk_agent_datasource UNIQUE (agent_id, datasource_id),
    INDEX idx_agent_datasource_agent (agent_id),
    INDEX idx_agent_datasource_datasource (datasource_id),
    INDEX idx_agent_datasource_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### SQLite 版本

```sql
-- 1. agent 表
CREATE TABLE agent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_agent_status ON agent(status);
CREATE INDEX idx_agent_created_at ON agent(created_at);

-- 2. datasource 表
CREATE TABLE datasource (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(20) NOT NULL,
    host VARCHAR(255),
    port INTEGER,
    database VARCHAR(100) NOT NULL,
    username VARCHAR(100),
    password VARCHAR(255),
    connection_url VARCHAR(500),
    test_status VARCHAR(20) NOT NULL DEFAULT 'untested',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_datasource_type ON datasource(type);
CREATE INDEX idx_datasource_test_status ON datasource(test_status);

-- 3. agent_datasource 表
CREATE TABLE agent_datasource (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id INTEGER NOT NULL,
    datasource_id INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE,
    FOREIGN KEY (datasource_id) REFERENCES datasource(id) ON DELETE CASCADE,
    UNIQUE (agent_id, datasource_id)
);

CREATE INDEX idx_agent_datasource_agent ON agent_datasource(agent_id);
CREATE INDEX idx_agent_datasource_datasource ON agent_datasource(datasource_id);
CREATE INDEX idx_agent_datasource_active ON agent_datasource(is_active);
```

---

## 后续 Phase 扩展表

### Phase 2 新增表

1. **business_knowledge** - 业务知识库
2. **semantic_model** - 语义模型
3. **agent_knowledge** - Agent 知识源

### Phase 3 新增表

4. **chat_session** - 聊天会话
5. **chat_message** - 聊天消息

### Phase 4 新增表

6. **user_prompt_config** - Prompt 配置
7. **model_config** - 模型配置

### Phase 5 新增表

8. **logical_relation** - 表关系
9. **agent_datasource_tables** - Agent 选择的表
10. **agent_preset_question** - 预设问题

---

## 数据库迁移策略

使用 Alembic 进行数据库版本管理：

```bash
# 初始化 Alembic
alembic init alembic

# 创建迁移
alembic revision --autogenerate -m "phase1: create agent, datasource, agent_datasource tables"

# 执行迁移
alembic upgrade head

# 回滚
alembic downgrade -1
```

---

## 与 Java 版本对齐

| Java 表名 | Python 表名 | Phase | 说明 |
|-----------|-------------|-------|------|
| agent | agent | 1 | ✅ 完全一致 |
| datasource | datasource | 1 | ✅ 完全一致 |
| agent_datasource | agent_datasource | 1 | ✅ 完全一致 |
| business_knowledge | business_knowledge | 2 | 待实现 |
| semantic_model | semantic_model | 2 | 待实现 |
| agent_knowledge | agent_knowledge | 2 | 待实现 |
| chat_session | chat_session | 3 | 待实现 |
| chat_message | chat_message | 3 | 待实现 |
| user_prompt_config | user_prompt_config | 4 | 待实现 |
| model_config | model_config | 4 | 待实现 |
| logical_relation | logical_relation | 5 | 待实现 |
| agent_datasource_tables | agent_datasource_tables | 5 | 待实现 |
| agent_preset_question | agent_preset_question | 5 | 待实现 |

---

## 数据库连接配置

### 异步连接池

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# 创建异步引擎
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600
)

# 创建异步 Session 工厂
async_session_maker = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 依赖注入
async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        yield session
```

---

## 测试数据

参见 `scripts/seed_data.py` 生成测试数据。
