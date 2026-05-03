"""
ApiResponse 响应包装中间件 — 对齐 Java ApiResponse<T> 模式

Java 格式: {success: bool, message: str, data: T}
Python 对齐: 对白名单路径自动包装为非流式 JSON 响应为此格式

白名单路径 (前端读取 response.data.data 的端点):
  - /api/model-config/*  (所有 ModelConfig 端点)

手动包装路径 (控制器显式返回 {success, ...}，中间件自动跳过):
  - /api/agent/{id}/api-key/*
  - /api/agent/{id}/preset-questions/*
  - /api/datasource/{id}/test
  - /api/datasource/types

裸数据路径 (前端读取 response.data 直接作为数据):
  - /api/agent/* (CRUD)
  - /api/datasource/* (CRUD)
  - 其他所有路径
"""
import json
from fastapi import Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware


# 需要自动包装 ApiResponse 的路径前缀白名单
_WRAP_PREFIXES = (
    "/api/model-config",
)


class ApiResponseMiddleware(BaseHTTPMiddleware):
    """对白名单路径自动包装 JSON 响应为 {success, message, data} 格式

    跳过规则:
    - 不在白名单的路径 → 原样返回 (裸数据)
    - SSE 流式响应 (text/event-stream)
    - 204 No Content
    - 已包含 success 字段的响应 (控制器手动包装)
    - 非 JSON 响应
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # 检查路径是否在白名单中
        path = request.url.path
        should_wrap = path.startswith(_WRAP_PREFIXES)

        if not should_wrap:
            return response

        # 跳过流式响应
        if isinstance(response, StreamingResponse):
            return response

        # 跳过 204 No Content
        if response.status_code == 204:
            return response

        # 跳过非 JSON 响应
        content_type = response.headers.get("content-type", "")
        if content_type and "application/json" not in content_type:
            return response

        # 读取响应体
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        if not body:
            return Response(status_code=response.status_code)

        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
            )

        # 不重复包装已包含 success 字段的响应
        if isinstance(data, dict) and "success" in data:
            return JSONResponse(
                content=data,
                status_code=response.status_code,
            )

        # 包装为 ApiResponse 格式
        wrapped = {"success": True, "message": "success", "data": data}
        return JSONResponse(
            content=wrapped,
            status_code=response.status_code,
        )
