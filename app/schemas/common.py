from typing import Any, Optional
from pydantic import BaseModel, Field


class SuccessResponse(BaseModel):
    """统一成功响应"""

    success: bool = Field(True, description="是否成功")
    message: str = Field("success", description="成功消息")
    data: Optional[Any] = Field(None, description="响应数据")


class ErrorResponse(BaseModel):
    """统一错误响应"""

    success: bool = Field(False, description="是否成功")
    message: str = Field(..., description="错误消息")
    detail: Optional[Any] = Field(None, description="错误详情")

