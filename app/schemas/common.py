
from typing import Any, Optional
from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    """统一 API 响应 """

    success: bool = Field(..., description="请求是否成功")
    message: str = Field(default="success", description="响应消息")
    data: Any = Field(default=None, description="响应数据")

    @staticmethod
    def ok(data: Any = None, *, message: str = "success") -> "ApiResponse":
        """成功响应 """
        return ApiResponse(success=True, message=message, data=data)

    @staticmethod
    def fail(message: str, data: Any = None) -> "ApiResponse":
        """失败响应"""
        return ApiResponse(success=False, message=message, data=data)
