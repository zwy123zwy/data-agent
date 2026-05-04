"""FileStorageService — 对齐 Java FileStorageService + LocalFileStorageServiceImpl"""
import os
import uuid
import logging
from pathlib import Path
from typing import Optional
from ..core.config import settings

logger = logging.getLogger(__name__)

# 允许的图片 MIME 类型
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml"}


class FileStorageService:
    """本地文件存储服务 — 对齐 Java LocalFileStorageServiceImpl"""

    @staticmethod
    def _get_base_path() -> Path:
        return Path(settings.file_storage.path).resolve()

    @staticmethod
    def _check_path_security(file_path: Path):
        """检查路径安全性，防止目录遍历攻击 — 对齐 Java checkPathSecurity()"""
        base = FileStorageService._get_base_path()
        resolved = file_path.resolve()
        if not str(resolved).startswith(str(base)):
            raise PermissionError("Invalid file path")

    @staticmethod
    def _build_storage_path(sub_path: str, filename: str) -> str:
        """构建存储路径 — 对齐 Java buildStoragePath()"""
        parts = []
        prefix = settings.file_storage.path_prefix
        if prefix:
            parts.append(prefix)
        if sub_path:
            parts.append(sub_path)
        parts.append(filename)
        return "/".join(parts)

    @staticmethod
    def store_file(file_content: bytes, original_filename: str, sub_path: str) -> str:
        """存储文件 — 对齐 Java storeFile(MultipartFile)"""
        # 生成 UUID 文件名
        _, ext = os.path.splitext(original_filename)
        filename = f"{uuid.uuid4()}{ext}"

        storage_path = FileStorageService._build_storage_path(sub_path, filename)
        base = FileStorageService._get_base_path()
        full_path = base / storage_path

        # 安全检查
        FileStorageService._check_path_security(full_path)

        # 创建目录
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # 写入文件
        full_path.write_bytes(file_content)
        logger.info("文件存储成功: %s", storage_path)
        return storage_path

    @staticmethod
    def delete_file(file_path: str) -> bool:
        """删除文件 — 对齐 Java deleteFile()"""
        try:
            base = FileStorageService._get_base_path()
            full_path = base / file_path
            FileStorageService._check_path_security(full_path)
            if full_path.exists():
                full_path.unlink()
                logger.info("成功删除文件: %s", file_path)
            else:
                logger.info("文件不存在，跳过删除: %s", file_path)
            return True
        except Exception as e:
            logger.error("删除文件失败: %s, %s", file_path, e)
            return False

    @staticmethod
    def get_file_url(file_path: str) -> str:
        """获取文件访问 URL — 对齐 Java getFileUrl()"""
        base = FileStorageService._get_base_path()
        FileStorageService._check_path_security(base / file_path)
        return f"{settings.file_storage.url_prefix}/{file_path}"

    @staticmethod
    def read_file(file_path: str) -> Optional[bytes]:
        """读取文件内容"""
        base = FileStorageService._get_base_path()
        full_path = base / file_path
        FileStorageService._check_path_security(full_path)
        if not full_path.exists() or not full_path.is_file():
            return None
        return full_path.read_bytes()

    @staticmethod
    def validate_image(content_type: Optional[str], file_size: int) -> Optional[str]:
        """验证图片文件 — 对齐 Java uploadAvatar 验证逻辑
        返回 None 表示通过，否则返回错误消息
        """
        if not content_type or content_type not in ALLOWED_IMAGE_TYPES:
            return "只支持图片文件（JPEG/PNG/GIF/WebP/SVG）"

        max_size = settings.file_storage.image_size
        if file_size > max_size:
            max_mb = max_size / (1024 * 1024)
            return f"图片大小超过最大限制（{max_mb:.0f}MB）"

        return None
