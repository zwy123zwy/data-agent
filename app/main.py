# 在 main.py 开头添加
if __name__ == "__main__" and __package__ is None:
    # 当直接运行且没有包信息时，设置包信息
    import sys
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    sys.path.insert(0, parent_dir)
    __package__ = "app"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .core.config import settings
from .core.database import init_db
from .core.exception_handlers import register_exception_handlers
from .core.response_middleware import ApiResponseMiddleware
from .api import (
    agent_controller,
    datasource_controller,
    agent_datasource_controller,
    agent_knowledge_controller,
    semantic_model_controller,
    query_plan_controller,
    schema_controller,
    graph_controller,
    streaming_graph_controller,
    model_config_controller,
    feedback_controller,
    chat_controller,
    agent_preset_question_controller,
)



@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化数据库
    await init_db()
    print("✅ Database initialized")
    yield
    # 关闭时清理资源
    print("👋 Shutting down...")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="基于 Java DataAgent 的 Python 渐进式复现实现",
    lifespan=lifespan
)

register_exception_handlers(app)

# ApiResponse 包装中间件 — 对齐 Java ApiResponse<T>
app.add_middleware(ApiResponseMiddleware)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False  # 禁用热重载
    )
