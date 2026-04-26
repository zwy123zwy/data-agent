# Phase 5: 完整 API 与管理 - 技术设计

## 目标

在 Phase 4 的基础上，完善系统的管理功能，提供完整的企业级能力。

## 核心功能

### 1. Prompt 配置管理
- 自定义 Prompt 模板
- Prompt 版本管理
- Prompt 变量替换
- Prompt 优化建议

### 2. 聊天会话管理
- 多轮对话支持
- 会话历史记录
- 会话上下文管理
- 会话导出

### 3. 预设问题管理
- 常见问题配置
- 问题分类
- 快速查询入口

### 4. 文件管理
- 文件上传
- 文件解析（Excel/CSV）
- 文件存储
- 文件查询

### 5. 报告导出
- PDF 导出
- Excel 导出
- 图表导出
- 批量导出

---

## 数据库设计

### 1. prompt_config 表

```sql
CREATE TABLE prompt_config (
    id INT PRIMARY KEY AUTO_INCREMENT,
    agent_id INT NOT NULL COMMENT 'Agent ID',
    name VARCHAR(100) NOT NULL COMMENT 'Prompt 名称',
    type VARCHAR(50) NOT NULL COMMENT 'Prompt 类型: system, user, sql_generation, python_generation',
    template TEXT NOT NULL COMMENT 'Prompt 模板',
    variables JSON COMMENT '变量定义',
    version INT DEFAULT 1 COMMENT '版本号',
    enabled BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    metadata JSON COMMENT '元数据',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_agent_id (agent_id),
    INDEX idx_type (type),
    INDEX idx_enabled (enabled),
    FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE
) COMMENT='Prompt 配置';
```

### 2. conversation 表

```sql
CREATE TABLE conversation (
    id INT PRIMARY KEY AUTO_INCREMENT,
    agent_id INT NOT NULL COMMENT 'Agent ID',
    title VARCHAR(200) COMMENT '会话标题',
    status VARCHAR(50) NOT NULL DEFAULT 'active' COMMENT '状态: active, archived',
    metadata JSON COMMENT '元数据',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_agent_id (agent_id),
    INDEX idx_status (status),
    FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE
) COMMENT='会话';
```

### 3. conversation_message 表

```sql
CREATE TABLE conversation_message (
    id INT PRIMARY KEY AUTO_INCREMENT,
    conversation_id INT NOT NULL COMMENT '会话ID',
    role VARCHAR(50) NOT NULL COMMENT '角色: user, assistant, system',
    content TEXT NOT NULL COMMENT '消息内容',
    query_result JSON COMMENT '查询结果（如果是查询消息）',
    metadata JSON COMMENT '元数据',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_conversation_id (conversation_id),
    INDEX idx_role (role),
    FOREIGN KEY (conversation_id) REFERENCES conversation(id) ON DELETE CASCADE
) COMMENT='会话消息';
```

### 4. preset_question 表

```sql
CREATE TABLE preset_question (
    id INT PRIMARY KEY AUTO_INCREMENT,
    agent_id INT NOT NULL COMMENT 'Agent ID',
    category VARCHAR(100) COMMENT '分类',
    question TEXT NOT NULL COMMENT '问题',
    description TEXT COMMENT '描述',
    sort_order INT DEFAULT 0 COMMENT '排序',
    enabled BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    metadata JSON COMMENT '元数据',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_agent_id (agent_id),
    INDEX idx_category (category),
    INDEX idx_enabled (enabled),
    FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE
) COMMENT='预设问题';
```

### 5. uploaded_file 表

```sql
CREATE TABLE uploaded_file (
    id INT PRIMARY KEY AUTO_INCREMENT,
    agent_id INT NOT NULL COMMENT 'Agent ID',
    filename VARCHAR(255) NOT NULL COMMENT '文件名',
    file_type VARCHAR(50) NOT NULL COMMENT '文件类型: excel, csv, pdf',
    file_path VARCHAR(500) NOT NULL COMMENT '文件路径',
    file_size BIGINT COMMENT '文件大小（字节）',
    status VARCHAR(50) NOT NULL DEFAULT 'uploaded' COMMENT '状态: uploaded, processing, processed, error',
    metadata JSON COMMENT '元数据',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_agent_id (agent_id),
    INDEX idx_status (status),
    FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE
) COMMENT='上传文件';
```

---

## API 设计

### Prompt 配置 API

```python
# 创建 Prompt 配置
POST /api/agents/{agent_id}/prompts
{
    "name": "SQL 生成 Prompt",
    "type": "sql_generation",
    "template": "根据以下 Schema 生成 SQL:\n{schema}\n\n用户查询: {query}",
    "variables": ["schema", "query"]
}

# 列出 Prompt 配置
GET /api/agents/{agent_id}/prompts?type=sql_generation

# 获取 Prompt 详情
GET /api/agents/{agent_id}/prompts/{id}

# 更新 Prompt 配置
PUT /api/agents/{agent_id}/prompts/{id}

# 删除 Prompt 配置
DELETE /api/agents/{agent_id}/prompts/{id}

# 测试 Prompt
POST /api/agents/{agent_id}/prompts/{id}/test
{
    "variables": {
        "schema": "CREATE TABLE users...",
        "query": "查询所有用户"
    }
}
```

### 会话管理 API

```python
# 创建会话
POST /api/agents/{agent_id}/conversations
{
    "title": "销售数据分析"
}

# 列出会话
GET /api/agents/{agent_id}/conversations?status=active

# 获取会话详情
GET /api/conversations/{id}

# 更新会话
PUT /api/conversations/{id}

# 删除会话
DELETE /api/conversations/{id}

# 发送消息
POST /api/conversations/{id}/messages
{
    "content": "查询最近一周的销售额"
}

# 获取消息历史
GET /api/conversations/{id}/messages

# 导出会话
GET /api/conversations/{id}/export?format=json
```

### 预设问题 API

```python
# 创建预设问题
POST /api/agents/{agent_id}/preset-questions
{
    "category": "销售分析",
    "question": "最近一周的销售额是多少",
    "description": "查询最近7天的总销售额"
}

# 列出预设问题
GET /api/agents/{agent_id}/preset-questions?category=销售分析

# 获取预设问题详情
GET /api/agents/{agent_id}/preset-questions/{id}

# 更新预设问题
PUT /api/agents/{agent_id}/preset-questions/{id}

# 删除预设问题
DELETE /api/agents/{agent_id}/preset-questions/{id}

# 执行预设问题
POST /api/agents/{agent_id}/preset-questions/{id}/execute
```

### 文件管理 API

```python
# 上传文件
POST /api/agents/{agent_id}/files
Content-Type: multipart/form-data
file: <file>

# 列出文件
GET /api/agents/{agent_id}/files?file_type=excel

# 获取文件详情
GET /api/files/{id}

# 下载文件
GET /api/files/{id}/download

# 删除文件
DELETE /api/files/{id}

# 解析文件（Excel/CSV）
POST /api/files/{id}/parse
```

### 报告导出 API

```python
# 导出报告为 PDF
POST /api/reports/export/pdf
{
    "workflow_id": "xxx",
    "include_charts": true
}

# 导出报告为 Excel
POST /api/reports/export/excel
{
    "workflow_id": "xxx",
    "include_data": true
}

# 批量导出
POST /api/reports/export/batch
{
    "workflow_ids": ["xxx", "yyy"],
    "format": "pdf"
}
```

---

## 实现步骤

### Step 1: Prompt 配置管理 (1天)
- [ ] 创建 PromptConfig 模型和 Schema
- [ ] 实现 PromptService
- [ ] 实现 Prompt API
- [ ] Prompt 变量替换

### Step 2: 会话管理 (2天)
- [ ] 创建 Conversation 和 Message 模型
- [ ] 实现 ConversationService
- [ ] 实现会话 API
- [ ] 多轮对话支持

### Step 3: 预设问题管理 (1天)
- [ ] 创建 PresetQuestion 模型和 Schema
- [ ] 实现 PresetQuestionService
- [ ] 实现预设问题 API

### Step 4: 文件管理 (1天)
- [ ] 创建 UploadedFile 模型和 Schema
- [ ] 实现文件上传
- [ ] 实现 Excel/CSV 解析
- [ ] 文件存储管理

### Step 5: 报告导出 (1天)
- [ ] PDF 导出功能
- [ ] Excel 导出功能
- [ ] 批量导出

### Step 6: 测试与文档 (1天)
- [ ] 端到端测试
- [ ] API 文档完善
- [ ] 用户手册

---

## 依赖更新

```txt
# 文件处理
openpyxl==3.1.2  # Excel 读写
pandas==2.1.4  # 已有

# PDF 生成
reportlab==4.0.7
weasyprint==60.1  # HTML to PDF

# 文件上传
python-multipart==0.0.12  # 已有
```

---

## 成功标准

- ✅ Prompt 配置管理完整
- ✅ 支持多轮对话
- ✅ 预设问题功能完整
- ✅ 文件上传和解析正常
- ✅ 报告导出功能完整
- ✅ 所有 API 有完整文档

---

## 下一步

完成 Phase 5 后，项目基本功能全部完成，进入优化和部署阶段。
