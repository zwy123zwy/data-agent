"""UploadResponse schema — 对齐 Java UploadResponse VO"""
from pydantic import BaseModel, Field
from typing import Optional


class UploadResponse(BaseModel):
    """通用上传响应 — 对齐 Java UploadResponse"""
    success: bool = True
    message: str = "上传成功"
    url: Optional[str] = None
    filename: Optional[str] = None

    @staticmethod
    def ok(message: str, url: str, filename: str) -> "UploadResponse":
        return UploadResponse(success=True, message=message, url=url, filename=filename)

    @staticmethod
    def error(message: str) -> "UploadResponse":
        return UploadResponse(success=False, message=message)
