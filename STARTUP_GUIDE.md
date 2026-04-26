# Python Agent V2 - 启动指南

## 问题诊断

如果遇到 "无法找到 app 目录下的模块" 错误，请按以下步骤检查：

### 1. 检查目录结构

```bash
python-agent-v2/
├── app/
│   ├── __init__.py          # 必须存在
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py      # 必须存在且导出所有控制器
│   │   ├── agent_controller.py
│   │   └── ...
│   ├── core/
│   │   ├── __init__.py      # 必须存在
│   │   └── ...
│   ├── models/
│   │   ├── __init__.py      # 必须存在且导出所有模型
│   │   └── ...
│   └── ...
├── run.py                    # 启动脚本
└── requirements.txt
```

### 2. 确保所有 __init__.py 文件存在

```bash
# 检查是否存在
ls app/__init__.py
ls app/api/__init__.py
ls app/core/__init__.py
ls app/models/__init__.py
ls app/schemas/__init__.py
ls app/services/__init__.py
ls app/workflows/__init__.py
ls app/workflows/nodes/__init__.py
```

### 3. 启动方式

**推荐方式 1: 使用 run.py**
```bash
cd python-agent-v2
python run.py
```

**推荐方式 2: 使用 uvicorn 模块方式**
```bash
cd python-agent-v2
python -m uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload
```

**不推荐: 直接运行 main.py**
```bash
# 这种方式可能导致模块导入问题
python app/main.py  # ❌ 不推荐
```

### 4. 环境变量配置

确保 `.env` 文件存在且配置正确：

```bash
# 复制示例配置
cp .env.example .env

# 编辑配置
vim .env
```

必需配置：
- `DATABASE_URL` - 数据库连接
- `OPENAI_API_KEY` - OpenAI API Key（如果使用）

### 5. 安装依赖

```bash
pip install -r requirements.txt
```

### 6. 初始化数据库

```bash
# 创建数据库
mysql -u root -p -e "CREATE DATABASE dataagent CHARACTER SET utf8mb4"

# 数据库表会在首次启动时自动创建
```

### 7. 测试导入

```bash
# 测试是否能正确导入
python -c "from app.main import app; print('Import successful')"
```

### 8. 常见错误

#### 错误 1: ModuleNotFoundError: No module named 'app'
**原因**: Python 找不到 app 模块
**解决**: 
- 确保在项目根目录运行
- 使用 `python run.py` 或 `python -m uvicorn app.main:app`

#### 错误 2: ImportError: cannot import name 'xxx' from 'app.api'
**原因**: app/api/__init__.py 没有导出控制器
**解决**: 
- 检查 `app/api/__init__.py` 文件内容
- 确保所有控制器都被导出

#### 错误 3: ModuleNotFoundError: No module named 'xxx'
**原因**: 缺少依赖包
**解决**: 
```bash
pip install -r requirements.txt
```

### 9. 验证启动

启动成功后，访问：
- API 文档: http://localhost:8100/docs
- 健康检查: http://localhost:8100/health

应该看到：
```json
{"status": "healthy"}
```

### 10. 调试模式

如果仍有问题，使用调试模式：

```bash
# 启用详细日志
python -m uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload --log-level debug
```

---

## 快速启动（推荐）

```bash
# 1. 进入项目目录
cd python-agent-v2

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境
cp .env.example .env
# 编辑 .env 文件

# 4. 启动服务
python run.py

# 5. 访问文档
# http://localhost:8100/docs
```

---

## 生产环境启动

```bash
# 使用 gunicorn + uvicorn workers
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8100 \
  --timeout 300
```

---

## Docker 启动（可选）

```bash
# 构建镜像
docker build -t python-agent-v2 .

# 运行容器
docker run -d \
  -p 8100:8100 \
  -v $(pwd)/.env:/app/.env \
  --name python-agent-v2 \
  python-agent-v2
```

---

## 故障排查清单

- [ ] 确认在项目根目录 `python-agent-v2/`
- [ ] 确认所有 `__init__.py` 文件存在
- [ ] 确认 `app/api/__init__.py` 导出了所有控制器
- [ ] 确认 `app/models/__init__.py` 导出了所有模型
- [ ] 确认依赖已安装 `pip list | grep fastapi`
- [ ] 确认 `.env` 文件存在且配置正确
- [ ] 确认数据库已创建
- [ ] 使用推荐的启动方式 `python run.py`

---

## 获取帮助

如果问题仍未解决，请提供以下信息：
1. 完整的错误信息
2. Python 版本 `python --version`
3. 启动命令
4. 当前工作目录 `pwd`
5. 目录结构 `ls -la app/`
