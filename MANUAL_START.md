# 手动启动测试指南

## 步骤 1: 验证环境

打开 PowerShell 或 CMD，执行：

```bash
python --version
# 应该显示 Python 3.10 或更高版本

pip --version
# 应该显示 pip 版本
```

如果没有 Python，请先安装 Python 3.10+

---

## 步骤 2: 创建数据库

```bash
mysql -u root -p123456 -e "CREATE DATABASE IF NOT EXISTS dataagent CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

验证数据库是否创建成功：
```bash
mysql -u root -p123456 -e "SHOW DATABASES LIKE 'dataagent';"
```

---

## 步骤 3: 进入项目目录

```bash
cd C:\Users\Zhangwenye\Desktop\spring-data-agent\python-agent-v2
```

---

## 步骤 4: 安装依赖

```bash
pip install -r requirements.txt
```

如果速度慢，使用国内镜像：
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## 步骤 5: 初始化数据库表

```bash
python scripts/init_db.py
```

你应该看到：
```
🚀 开始初始化数据库...
✅ 数据库表创建成功！

已创建的表:
  - agent
```

---

## 步骤 6: 插入测试数据（可选）

```bash
python scripts/seed_data.py
```

你应该看到：
```
🌱 开始插入种子数据...
✅ 成功插入 3 个 Agent
  - 销售分析助手 (status: published)
  - 用户行为分析 (status: draft)
  - 财务数据分析 (status: draft)
```

---

## 步骤 7: 启动服务

```bash
python app/main.py
```

或使用 uvicorn：
```bash
uvicorn app.main:app --reload --port 8100
```

你应该看到：
```
INFO:     Uvicorn running on http://0.0.0.0:8100 (Press CTRL+C to quit)
INFO:     Started reloader process
✅ Database initialized
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

---

## 步骤 8: 验证服务

### 方式 1: 浏览器访问

打开浏览器访问：
- **API 文档**: http://localhost:8100/docs
- **健康检查**: http://localhost:8100/health

在 Swagger UI 中可以直接测试所有 API！

### 方式 2: 使用 curl 测试

打开**另一个终端窗口**，执行：

```bash
# 健康检查
curl http://localhost:8100/health

# 创建 Agent
curl -X POST http://localhost:8100/api/agents -H "Content-Type: application/json" -d "{\"name\": \"测试Agent\", \"description\": \"测试描述\"}"

# 列出所有 Agent
curl http://localhost:8100/api/agents

# 获取 Agent 详情
curl http://localhost:8100/api/agents/1

# 发布 Agent
curl -X POST http://localhost:8100/api/agents/1/publish

# 删除 Agent
curl -X DELETE http://localhost:8100/api/agents/1
```

### 方式 3: 运行自动化测试

打开**另一个终端窗口**，执行：

```bash
# 安装测试依赖
pip install requests

# 运行测试
cd C:\Users\Zhangwenye\Desktop\spring-data-agent\python-agent-v2
python tests/test_agent_api.py
```

你应该看到：
```
============================================================
开始测试 Agent API
============================================================

🔍 测试健康检查...
状态码: 200
响应: {'status': 'healthy'}

🔍 测试创建 Agent...
状态码: 201
响应: {
  "id": 1,
  "name": "测试Agent",
  "description": "这是一个测试Agent",
  "status": "draft",
  ...
}

🔍 测试列出所有 Agent...
...

============================================================
✅ 所有测试通过！
============================================================
```

---

## 常见问题

### 1. ModuleNotFoundError: No module named 'xxx'

**解决方案**：重新安装依赖
```bash
pip install -r requirements.txt
```

### 2. 数据库连接失败

**检查**：
- MySQL 服务是否启动
- 用户名密码是否正确（root/123456）
- 数据库 dataagent 是否已创建

### 3. 端口 8100 被占用

**解决方案**：修改 `.env` 文件中的端口
```env
PORT=8101
```

然后重启服务。

### 4. 导入错误

**解决方案**：确保从项目根目录运行命令
```bash
cd C:\Users\Zhangwenye\Desktop\spring-data-agent\python-agent-v2
python app/main.py
```

---

## 停止服务

在服务运行的终端窗口按 `Ctrl + C`

---

## 下一步

服务启动成功后，你可以：

1. ✅ 在 Swagger UI 中测试所有 API
2. ✅ 运行自动化测试脚本
3. ✅ 继续开发 Datasource 管理功能
4. ✅ 开始实现工作流节点

祝测试顺利！🎉
