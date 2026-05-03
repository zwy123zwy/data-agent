"""
全局异常处理器 — 统一错误响应格式

【在系统中的地位】
  将所有未捕获的异常统一转换为 {success: False, message, detail, path} 格式。
  确保前端始终能解析错误响应，不会因异常格式不一致而崩溃。

【模块连接】
  调用者:
    - main.py → register_exception_handlers(app) 在应用启动时注册
    - FastAPI 框架 → 发生异常时自动调用对应的 handler

  下游 (前端):
    - 前端统一通过 response.success 判断成功/失败
    - 失败时读取 response.message 显示错误提示

  三层异常处理:
    1. HTTPException     → 业务异常 (如 404, 400)，保留原始状态码
    2. RequestValidationError → Pydantic 校验失败 (422)，返回校验细节
    3. Exception         → 兜底，500 服务器内部错误

  Java 对应:
    exception_handlers.py ≈ Spring Boot @ControllerAdvice + @ExceptionHandler
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def register_exception_handlers(app: FastAPI):
    """注册全局异常处理器 — 在 main.py 的 lifespan 中被调用

    所有响应都使用 {success: False, message, detail, path} 格式，
    与 ApiResponse 中间件格式一致，确保前端错误处理逻辑统一。
    """

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """HTTP 异常 — 业务逻辑主动抛出的异常 (raise HTTPException(404, "Not Found"))"""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": str(exc.detail),
                "detail": None,
                "path": str(request.url.path),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """请求参数校验失败 — Pydantic 模型验证不通过时触发"""
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "message": "请求参数校验失败",
                "detail": exc.errors(),
                "path": str(request.url.path),
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        """通用异常兜底 — 捕获所有未处理的异常"""
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "服务器内部错误",
                "detail": str(exc),
                "path": str(request.url.path),
            },
        )

