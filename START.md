# 启动服务脚本

## Windows (PowerShell)

```powershell
# 1. 创建数据库
mysql -u root -p123456 -e "CREATE DATABASE IF NOT EXISTS dataagent CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 2. 进入项目目录
cd python-agent-v2

# 3. 安装依赖
pip install -r requirements.txt

# 4. 初始化数据库
python scripts/init_db.py

# 5. 插入测试数据（可选）
python scripts/seed_data.py

# 6. 启动服务
python app/main.py
```

## 验证服务

打开浏览器访问：
- API 文档: http://localhost:8100/docs
- 健康检查: http://localhost:8100/health

## 运行测试

在另一个终端窗口运行：

```bash
# 安装测试依赖
pip install requests

# 运行测试
python tests/test_agent_api.py
```

## 常用命令

```bash
# 查看所有 Agent
curl http://localhost:8100/api/agents

# 创建 Agent
curl -X POST http://localhost:8100/api/agents \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"测试Agent\", \"description\": \"测试\"}"

# 获取 Agent 详情
curl http://localhost:8100/api/agents/1

# 发布 Agent
curl -X POST http://localhost:8100/api/agents/1/publish

# 删除 Agent
curl -X DELETE http://localhost:8100/api/agents/1
```

## 停止服务

按 `Ctrl + C` 停止服务
