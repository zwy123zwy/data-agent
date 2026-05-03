"""
ApiResponse 响应包装中间件 — 对齐 Java ApiResponse<T> 模式

Java 格式: {success: bool, message: str, data: T}
Python 对齐: 所有非流式 JSON 响应自动包装为此格式
"""
import json
from fastapi import Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware


class ApiResponseMiddleware(BaseHTTPMiddleware):
    """自动包装 JSON 响应为 {success, message, data} 格式

    跳过规则:
    - SSE 流式响应 (text/event-stream)
    - 204 No Content
    - 已包含 success 字段的响应 (异常处理器/手动包装)
    - 非 JSON 响应
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

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
