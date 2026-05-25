# [阶段4] 会话附件引用（M3 实现存储；M4 契约先行）

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FileRef(BaseModel):
    """[阶段4] 线程级上传文件元数据，由 context/builder 在 M3 装配。"""

    file_id: str
    thread_id: str
    original_name: str
    mime_type: str = "application/octet-stream"
    size_bytes: int = 0
    storage_key: str = ""
    uploaded_at: str | None = None

    model_config = ConfigDict(extra="forbid")
