# ============================================================================
# 从 0 理解本项目：app/main.py 定义 FastAPI 应用，启动入口为项目根目录的 main.py
# ============================================================================
#
# 【项目架构概览 — 请求在系统中的流转路径】
#
#  HTTP 请求 (前端/浏览器)
#       │
#       ▼
#  FastAPI app (当前文件)  ←── 注册了 13 个 Controller + 全局中间件
#       │
#       ├── middleware ──►  CORS (跨域)  ──►  ApiResponseMiddleware (响应包装)
#       │
#       ├── routers ────►  13 个 API 控制器 (/api/agent, /api/datasource, ...)
#       │                        │
#       │                        ├─► Service 层 (业务逻辑)
#       │                        │      ├─► BaseService (通用 CRUD)
#       │                        │      ├─► AgentService, DatasourceService, ...
#       │                        │      └─► ModelRegistry (LLM 模型管理)
#       │                        │
#       │                        ├─► ORM Model 层 (SQLAlchemy)
#       │                        │      └─► MySQL 数据库 (dataagent)
#       │                        │
#       │                        └─► Workflow 层 (LangGraph)
#       │                               ├─► StateGraph (17 节点流水线)
#       │                               └─► SSE 流式输出 (text/event-stream)
#       │
#       └── exception_handlers ──► 统一错误处理 (ApiResponse 格式)
#
# 【核心 URL 路径】 (前端 Vite :3000 → proxy → 本后端 :8100)
#   GET  /api/stream/search       → 流式查询 (SSE) ← 前端核心调用
#   GET  /api/agent/list          → Agent 管理
#   POST /api/model-config/add    → LLM 模型配置
#   GET  /api/datasource/types    → 数据源类型列表
#   ...
#
# ============================================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .core.config import settings
from .core.database import init_db
from .core.exception_handlers import register_exception_handlers
from .core.response_middleware import ApiResponseMiddleware
from .api import (
    agent_controller,                    # Agent CRUD + API Key
    datasource_controller,               # 数据源 CRUD + 测试连接
    agent_datasource_controller,         # Agent-数据源关联
    agent_knowledge_controller,          # 知识库 (RAG 向量检索)
    semantic_model_controller,           # 语义模型 (字段别名)
    query_plan_controller,               # 查询计划
    schema_controller,                   # 数据库 Schema 发现
    graph_controller,                    # 同步查询 (POST /api/query)
    streaming_graph_controller,          # ★ 流式查询 SSE (GET /api/stream/search)
    model_config_controller,             # LLM 模型配置
    feedback_controller,                 # 人工反馈
    chat_controller,                     # 会话历史 (ChatSession/ChatMessage)
    agent_preset_question_controller,    # Agent 预设问题
    prompt_config_controller,            # Prompt 自定义配置
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理

    启动流程:
      1. init_db() → 连接 MySQL，自动创建缺失的数据表
      2. 注册全局异常处理器
      3. 注册中间件 (CORS → ApiResponse 包装)
      4. 注册 13 个 Controller 路由
      5. 开始接受 HTTP 请求
    """
    await init_db()
    print("[OK] Database initialized")
    yield
    print("[Bye] Shutting down...")


# ===== 创建 FastAPI 应用 =====
# FastAPI 是 Python 版 Spring Boot 的等价物
# 它自动生成 OpenAPI 文档: http://localhost:8100/docs
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="基于 Java DataAgent 的 Python 渐进式复现实现",
    lifespan=lifespan
)

# ===== 1. 全局异常处理器 =====
# 将所有异常统一转换为 {success: False, message: ..., detail: ..., path: ...}
# 这样前端可以统一处理所有错误
register_exception_handlers(app)

# ===== 2. ApiResponse 响应包装中间件 =====
# ★ 关键设计: 不是全局包装！只对白名单路径 (/api/model-config/*) 自动包装
#   为什么? 因为前端对不同接口的响应格式有不同的期望:
#     - ModelConfig:  前端读 response.data.data (需要 ApiResponse 包装)
#     - Agent/Datasource CRUD: 前端读 response.data 直接作为数据 (不需要包装)
#     - API Key/PresetQuestion: 控制器手动返回 {success: True, ...} (中间件跳过)
#  详见: app/core/response_middleware.py
app.add_middleware(ApiResponseMiddleware)

# ===== 3. CORS 跨域中间件 =====
# 允许前端 (Vite :3000) 跨域调用本后端 (:8100)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== 4. 注册 13 个 API 控制器 =====
# 每个 controller 是一个 APIRouter，有自己的 prefix 和 tags
# ★ 路由匹配规则: FastAPI 按注册顺序匹配，静态路径优先于路径参数
# ★ URL 前缀已对齐 Java 后端 (单数形式): /api/agent, /api/datasource, /api/model-config
app.include_router(agent_controller.router)
app.include_router(datasource_controller.router)
app.include_router(agent_datasource_controller.router)
app.include_router(agent_knowledge_controller.router)
app.include_router(semantic_model_controller.router)
app.include_router(query_plan_controller.router)
app.include_router(schema_controller.router)
app.include_router(graph_controller.router)
app.include_router(streaming_graph_controller.router)
app.include_router(model_config_controller.router)
app.include_router(feedback_controller.router)
app.include_router(chat_controller.router)
app.include_router(agent_preset_question_controller.router)
app.include_router(prompt_config_controller.router)


@app.get("/", tags=["健康检查"])
async def root():
    """根路径 - 健康检查"""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "status": "running"
    }


@app.get("/health", tags=["健康检查"])
async def health():
    """健康检查接口"""
    return {"status": "healthy"}
