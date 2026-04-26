# 快速启动指南

## 解决 IDE 导入问题

如果你使用 PyCharm 或 VS Code，需要将项目根目录标记为源代码根目录：

### PyCharm
1. 右键点击 `python-agent-v2` 目录
2. 选择 `Mark Directory as` → `Sources Root`

### VS Code
1. 已自动配置 `.vscode/settings.json`
2. 重启 VS Code 即可

---

## 1. 创建数据库

首先在 MySQL 中创建数据库：

```bash
mysql -u root -p123456 -e "CREATE DATABASE IF NOT EXISTS dataagent CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

## 2. 安装依赖

```bash
cd python-agent-v2
pip install -r requirements.txt
```

## 3. 初始化数据库表

**方式一：使用脚本**
```bash
# 从项目根目录运行
python scripts/init_db.py
```

**方式二：使用 Python 模块方式**
```bash
# 从项目根目录运行
python -m scripts.init_db
```

## 4. 插入测试数据（可选）

```bash
python scripts/seed_data.py
```

## 5. 启动服务

**方式一：直接运行**
```bash
python app/main.py
```

**方式二：使用 uvicorn**
```bash
uvicorn app.main:app --reload --port 8100
```

**方式三：从项目根目录运行**
```bash
python -m uvicorn app.main:app --reload --port 8100
```

## 6. 访问 API 文档

打开浏览器访问：http://localhost:8100/docs

---

## 测试 API

### 创建 Agent

```bash
curl -X POST "http://localhost:8100/api/agents" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试Agent",
    "description": "这是一个测试Agent"
  }'
```

### 列出所有 Agent

```bash
curl "http://localhost:8100/api/agents"
```

### 获取 Agent 详情

```bash
curl "http://localhost:8100/api/agents/1"
```

### 更新 Agent

```bash
curl -X PUT "http://localhost:8100/api/agents/1" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "更新后的Agent",
    "status": "published"
  }'
```

### 发布 Agent

```bash
curl -X POST "http://localhost:8100/api/agents/1/publish"
```

### 下线 Agent

```bash
curl -X POST "http://localhost:8100/api/agents/1/offline"
```

### 删除 Agent

```bash
curl -X DELETE "http://localhost:8100/api/agents/1"
```

---

## 常见问题

### 1. 导入错误：ModuleNotFoundError: No module named 'app'

**解决方案：**
- 确保从 `python-agent-v2` 目录运行命令
- 使用 `python -m` 方式运行脚本
- 在 IDE 中将项目根目录标记为源代码根目录

### 2. 数据库连接失败

**检查：**
- MySQL 服务是否启动
- 用户名密码是否正确（root/123456）
- 数据库 `dataagent` 是否已创建

### 3. 端口被占用

修改 `.env` 文件中的 `PORT` 配置：
```env
PORT=8101
```

### 4. 依赖安装失败

使用国内镜像：
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## 开发建议

### 推荐的项目打开方式

1. **PyCharm**: 直接打开 `python-agent-v2` 目录
2. **VS Code**: 打开 `python-agent-v2` 目录，会自动加载 `.vscode/settings.json`

### 推荐的运行方式

```bash
# 进入项目目录
cd python-agent-v2

# 启动服务（自动重载）
uvicorn app.main:app --reload --port 8100
```

### 查看日志

服务启动后会显示：
```
INFO:     Uvicorn running on http://0.0.0.0:8100 (Press CTRL+C to quit)
INFO:     Started reloader process
✅ Database initialized
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```
