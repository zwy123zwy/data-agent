# Agent-Datasource 关联功能更新

## 🎉 新增功能

### 1. AgentDatasource 模型
- ✅ `app/models/agent_datasource.py` - 关联表 ORM 模型
  - agent_id, datasource_id（外键，级联删除）
  - is_active（激活状态）
  - 唯一约束：一个 Agent 不能重复绑定同一个 Datasource

### 2. Agent-Datasource API（5个接口）
- ✅ `POST /api/agents/{agent_id}/datasources/{datasource_id}` - 绑定数据源
- ✅ `DELETE /api/agents/{agent_id}/datasources/{datasource_id}` - 解绑数据源
- ✅ `GET /api/agents/{agent_id}/datasources` - 列出 Agent 的所有数据源
- ✅ `GET /api/agents/{agent_id}/datasources/active` - 获取激活的数据源
- ✅ `POST /api/agents/{agent_id}/datasources/{datasource_id}/activate` - 激活数据源

### 3. 核心功能
- ✅ 自动激活管理（激活一个数据源时，自动将其他数据源设为非激活）
- ✅ 数据源详情联查（返回数据源完整信息）
- ✅ 验证 Agent 和 Datasource 是否存在
- ✅ 防止重复绑定

---

## 🚀 如何测试

### 1. 重新初始化数据库

```bash
cd C:\Users\Zhangwenye\Desktop\spring-data-agent\python-agent-v2

# 重新创建表（会创建 agent_datasource 表）
python scripts/init_db.py
```

你应该看到：
```
🚀 开始初始化数据库...
✅ 数据库表创建成功！

已创建的表:
  - agent
  - datasource
  - agent_datasource  ← 新增
```

### 2. 插入测试数据

```bash
# 插入 Agent 测试数据
python scripts/seed_data.py

# 插入 Datasource 测试数据
python scripts/seed_datasources.py

# 插入 Agent-Datasource 关联测试数据
python scripts/seed_agent_datasources.py
```

### 3. 启动服务

```bash
python app/main.py
```

### 4. 访问 API 文档

打开浏览器：http://localhost:8100/docs

你会看到新增的 **Agent-Datasource关联** 分组，包含 5 个接口！

---

## 📝 API 使用示例

### 1. 绑定数据源到 Agent

```bash
curl -X POST "http://localhost:8100/api/agents/1/datasources/1" \
  -H "Content-Type: application/json" \
  -d '{"is_active": true}'
```

响应：
```json
{
  "id": 1,
  "agent_id": 1,
  "datasource_id": 1,
  "is_active": true,
  "created_at": "2024-04-26T10:00:00"
}
```

### 2. 列出 Agent 的所有数据源

```bash
curl "http://localhost:8100/api/agents/1/datasources"
```

响应：
```json
{
  "total": 1,
  "items": [
    {
      "id": 1,
      "agent_id": 1,
      "datasource_id": 1,
      "is_active": true,
      "created_at": "2024-04-26T10:00:00",
      "datasource": {
        "id": 1,
        "name": "本地MySQL数据库",
        "type": "mysql",
        "database": "dataagent",
        "test_status": "success"
      }
    }
  ]
}
```

### 3. 获取激活的数据源

```bash
curl "http://localhost:8100/api/agents/1/datasources/active"
```

响应：
```json
{
  "id": 1,
  "name": "本地MySQL数据库",
  "type": "mysql",
  "host": "localhost",
  "port": 3306,
  "database": "dataagent",
  "test_status": "success",
  "created_at": "2024-04-26T10:00:00",
  "updated_at": "2024-04-26T10:00:00"
}
```

### 4. 激活另一个数据源

```bash
curl -X POST "http://localhost:8100/api/agents/1/datasources/2/activate"
```

这会自动将数据源 1 设为非激活，数据源 2 设为激活。

### 5. 解绑数据源

```bash
curl -X DELETE "http://localhost:8100/api/agents/1/datasources/1"
```

---

## 🎯 Phase 1 进度

1. ✅ **Agent 管理 API** - 8个接口（已完成）
2. ✅ **Datasource 管理 API** - 6个接口（已完成）
3. ✅ **Agent-Datasource 关联 API** - 5个接口（已完成）
4. ⏳ **查询执行 API（核心工作流）** - 最后一步！

---

## 📊 数据库表结构

现在数据库包含 3 张表：

### agent 表
- id, name, description, status
- avatar, tags, api_key, api_key_enabled
- created_at, updated_at

### datasource 表
- id, name, type
- host, port, database, username, password, connection_url
- test_status
- created_at, updated_at

### agent_datasource 表（关联表）
- id, agent_id, datasource_id
- is_active
- created_at
- 外键约束：CASCADE DELETE

---

## 🔍 特性亮点

1. **自动激活管理** - 激活一个数据源时，自动将其他数据源设为非激活
2. **级联删除** - 删除 Agent 或 Datasource 时，自动删除关联记录
3. **防重复绑定** - 同一个 Agent 不能重复绑定同一个 Datasource
4. **详情联查** - 返回数据源完整信息，无需二次查询
5. **完全对齐 Java 版本** - 表结构和 API 路径一致

---

## 🎯 下一步

现在可以开始实现 **Phase 1 的最后一个功能**：

### 查询执行 API（核心工作流）

包含 5 个工作流节点：
1. **IntentRecognitionNode** - 意图识别
2. **SchemaRecallNode** - 数据库模式检索
3. **SqlGenerateNode** - SQL 生成
4. **SqlExecuteNode** - SQL 执行
5. **SimpleReportNode** - 简单文本报告

完成后，Phase 1 就全部完成了！🎉
