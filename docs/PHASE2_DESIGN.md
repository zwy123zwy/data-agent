# Phase 2: 增强检索与计划 - 技术设计

## 目标

在 Phase 1 的基础上，增强系统的智能性和复杂查询处理能力。

## 核心功能

### 1. RAG 知识库管理
- Agent 知识库（业务知识、术语解释、查询示例）
- 向量化存储和检索
- 知识库 CRUD API

### 2. 查询改写与增强
- 基于知识库的查询改写
- 业务术语映射
- 历史查询参考

### 3. 多步骤计划生成
- 复杂查询分解为多个子任务
- 任务依赖关系管理
- 计划编排执行

### 4. 语义模型（Semantic Model）
- 表/字段的业务语义映射
- 常用查询模板
- 业务规则定义

---

## 技术选型

### 向量数据库
**选择**: **Chroma** (轻量级，易于集成)

**备选**:
- Milvus (生产级，性能强)
- Qdrant (Rust 实现，高性能)
- Weaviate (GraphQL API)

**理由**:
- Chroma 无需额外服务，可嵌入式运行
- 支持持久化存储
- Python 原生支持
- 适合 MVP 快速验证

### Embedding 模型
**选择**: **OpenAI text-embedding-3-small**

**备选**:
- text-embedding-3-large (更高精度)
- 本地模型 (sentence-transformers)

---

## 数据库设计

### 1. knowledge 表（知识库）

```sql
CREATE TABLE knowledge (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    agent_id BIGINT NOT NULL COMMENT 'Agent ID',
    title VARCHAR(200) NOT NULL COMMENT '知识标题',
    content TEXT NOT NULL COMMENT '知识内容',
    type VARCHAR(50) NOT NULL COMMENT '知识类型: business_term, query_example, business_rule',
    embedding_id VARCHAR(100) COMMENT '向量ID（Chroma）',
    metadata JSON COMMENT '元数据',
    enabled BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_agent_id (agent_id),
    INDEX idx_type (type),
    INDEX idx_enabled (enabled),
    FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE
) COMMENT='Agent 知识库';
```

### 2. semantic_model 表（语义模型）

```sql
CREATE TABLE semantic_model (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    agent_id BIGINT NOT NULL COMMENT 'Agent ID',
    datasource_id BIGINT NOT NULL COMMENT '数据源ID',
    table_name VARCHAR(100) NOT NULL COMMENT '表名',
    column_name VARCHAR(100) COMMENT '字段名（NULL表示表级别）',
    business_name VARCHAR(200) NOT NULL COMMENT '业务名称',
    description TEXT COMMENT '业务描述',
    synonyms JSON COMMENT '同义词列表',
    sample_values JSON COMMENT '示例值',
    metadata JSON COMMENT '元数据',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_agent_id (agent_id),
    INDEX idx_datasource_id (datasource_id),
    INDEX idx_table_name (table_name),
    FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE,
    FOREIGN KEY (datasource_id) REFERENCES datasource(id) ON DELETE CASCADE
) COMMENT='语义模型（业务术语映射）';
```

### 3. query_plan 表（查询计划）

```sql
CREATE TABLE query_plan (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    agent_id BIGINT NOT NULL COMMENT 'Agent ID',
    user_query TEXT NOT NULL COMMENT '用户原始查询',
    plan_json JSON NOT NULL COMMENT '计划JSON（步骤列表）',
    status VARCHAR(50) NOT NULL COMMENT '状态: pending, running, completed, failed',
    result JSON COMMENT '执行结果',
    error TEXT COMMENT '错误信息',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_agent_id (agent_id),
    INDEX idx_status (status),
    FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE
) COMMENT='查询计划（多步骤任务）';
```

---

## 工作流节点扩展

### 新增节点

#### 1. KnowledgeRecallNode（知识召回）
- 从向量数据库检索相关知识
- 输入：用户查询
- 输出：相关知识列表

#### 2. QueryRewriteNode（查询改写）
- 基于知识库改写用户查询
- 业务术语 → 技术术语
- 输入：原始查询 + 知识
- 输出：改写后的查询

#### 3. PlannerNode（计划生成）
- 分解复杂查询为多个子任务
- 输入：改写后的查询 + Schema
- 输出：执行计划（步骤列表）

#### 4. PlanExecutorNode（计划执行）
- 按顺序执行计划中的每个步骤
- 支持步骤间数据传递
- 输入：执行计划
- 输出：最终结果

### 工作流路由

```
用户查询
  ↓
意图识别 → 闲聊？→ 直接回复
  ↓ 数据分析
知识召回（RAG）
  ↓
查询改写
  ↓
Schema 召回
  ↓
计划生成 → 简单查询？→ SQL生成 → SQL执行 → 报告生成
  ↓ 复杂查询
计划执行（多步骤）
  ↓
报告生成
```

---

## API 设计

### 1. 知识库管理 API

```python
# 创建知识
POST /api/agents/{agent_id}/knowledge
{
    "title": "销售额定义",
    "content": "销售额 = 订单金额 - 退款金额",
    "type": "business_term"
}

# 列出知识
GET /api/agents/{agent_id}/knowledge?type=business_term&page=1&size=20

# 获取知识详情
GET /api/agents/{agent_id}/knowledge/{knowledge_id}

# 更新知识
PUT /api/agents/{agent_id}/knowledge/{knowledge_id}

# 删除知识
DELETE /api/agents/{agent_id}/knowledge/{knowledge_id}

# 搜索知识（向量检索）
POST /api/agents/{agent_id}/knowledge/search
{
    "query": "什么是销售额",
    "top_k": 5
}
```

### 2. 语义模型 API

```python
# 创建语义映射
POST /api/agents/{agent_id}/semantic-models
{
    "datasource_id": 1,
    "table_name": "orders",
    "column_name": "total_amount",
    "business_name": "订单金额",
    "description": "订单的总金额，包含所有商品价格",
    "synonyms": ["销售额", "成交金额", "订单总价"]
}

# 列出语义模型
GET /api/agents/{agent_id}/semantic-models?datasource_id=1

# 更新语义模型
PUT /api/agents/{agent_id}/semantic-models/{model_id}

# 删除语义模型
DELETE /api/agents/{agent_id}/semantic-models/{model_id}

# 搜索语义模型
GET /api/agents/{agent_id}/semantic-models/search?q=销售额
```

### 3. 查询计划 API

```python
# 生成查询计划（不执行）
POST /api/agents/{agent_id}/plans/generate
{
    "query": "对比最近3个月每个地区的销售额，并找出增长最快的地区"
}

# 响应
{
    "plan": {
        "steps": [
            {
                "id": 1,
                "type": "sql_query",
                "description": "查询最近3个月每个地区的销售额",
                "sql": "SELECT region, MONTH(order_date) as month, SUM(amount) as sales FROM orders WHERE order_date >= DATE_SUB(NOW(), INTERVAL 3 MONTH) GROUP BY region, month"
            },
            {
                "id": 2,
                "type": "python_analysis",
                "description": "计算每个地区的增长率",
                "depends_on": [1],
                "code": "# Python 代码..."
            },
            {
                "id": 3,
                "type": "report",
                "description": "生成对比报告",
                "depends_on": [2]
            }
        ]
    }
}

# 执行查询计划
POST /api/agents/{agent_id}/plans/execute
{
    "query": "对比最近3个月每个地区的销售额"
}

# 获取计划执行状态
GET /api/plans/{plan_id}

# 列出历史计划
GET /api/agents/{agent_id}/plans?status=completed&page=1&size=20
```

---

## 实现步骤

### Step 1: 向量数据库集成（1天）
- [ ] 安装 Chroma
- [ ] 创建 VectorStore 服务
- [ ] 实现 Embedding 生成
- [ ] 测试向量检索

### Step 2: 知识库管理（1天）
- [ ] 创建 Knowledge 模型和 Schema
- [ ] 实现 KnowledgeService
- [ ] 实现知识库 CRUD API
- [ ] 实现向量检索 API

### Step 3: 语义模型（1天）
- [ ] 创建 SemanticModel 模型和 Schema
- [ ] 实现 SemanticModelService
- [ ] 实现语义模型 CRUD API
- [ ] 实现业务术语映射

### Step 4: 查询改写（1天）
- [ ] 实现 KnowledgeRecallNode
- [ ] 实现 QueryRewriteNode
- [ ] 集成到工作流

### Step 5: 计划生成与执行（2天）
- [ ] 创建 QueryPlan 模型和 Schema
- [ ] 实现 PlannerNode
- [ ] 实现 PlanExecutorNode
- [ ] 实现计划 API
- [ ] 测试复杂查询

---

## 依赖更新

```txt
# 向量数据库
chromadb==0.4.22

# Embedding
openai>=1.0.0  # 已有

# 可选：本地 Embedding 模型
sentence-transformers==2.3.1  # 可选
```

---

## 测试用例

### 知识库测试
```python
# 1. 添加业务术语
POST /api/agents/1/knowledge
{
    "title": "GMV",
    "content": "GMV（Gross Merchandise Volume）是指网站成交金额，包括付款和未付款的订单",
    "type": "business_term"
}

# 2. 查询改写测试
用户输入: "最近一周的GMV是多少"
改写后: "最近一周的订单总金额是多少"
```

### 语义模型测试
```python
# 1. 添加语义映射
POST /api/agents/1/semantic-models
{
    "table_name": "orders",
    "column_name": "total_amount",
    "business_name": "订单金额",
    "synonyms": ["GMV", "成交额", "销售额"]
}

# 2. SQL 生成测试
用户输入: "查询GMV"
生成SQL: "SELECT SUM(total_amount) FROM orders"
```

### 计划生成测试
```python
# 复杂查询
用户输入: "对比最近3个月每个地区的销售额，并找出增长最快的地区"

生成计划:
Step 1: SQL查询 - 获取每个地区每月销售额
Step 2: Python分析 - 计算增长率
Step 3: 报告生成 - 生成对比图表
```

---

## 成功标准

- ✅ 知识库 CRUD 功能完整
- ✅ 向量检索准确率 > 80%
- ✅ 查询改写能正确映射业务术语
- ✅ 计划生成能分解复杂查询
- ✅ 多步骤计划能正确执行
- ✅ 所有 API 有完整文档和测试

---

## 风险与挑战

1. **向量检索质量** - 需要调优 Embedding 模型和检索参数
2. **计划生成准确性** - 需要精心设计 Prompt
3. **步骤依赖管理** - 需要处理步骤间的数据传递
4. **性能问题** - 向量检索可能较慢，需要优化

---

## 下一步

完成 Phase 2 后，进入 Phase 3：Python 分析与报告生成。
