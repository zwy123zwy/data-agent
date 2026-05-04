"""FileUpload API — 对齐 Java FileUploadController"""
import logging
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import Response
from ..services.file_storage_service import FileStorageService
from ..schemas.upload import UploadResponse
from ..core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/upload", tags=["文件上传"])


@router.post("/avatar", summary="上传头像图片")
async def upload_avatar(file: UploadFile = File(...)):
    """上传头像图片 — POST /api/upload/avatar
    对齐 Java FileUploadController.uploadAvatar()"""
    # 验证文件类型
    content_type = file.content_type
    file_content = await file.read()
    file_size = len(file_content)

    error = FileStorageService.validate_image(content_type, file_size)
    if error:
        raise HTTPException(status_code=400, detail=error)

    try:
        original_filename = file.filename or "avatar.png"
        file_path = FileStorageService.store_file(file_content, original_filename, "avatars")
        file_url = FileStorageService.get_file_url(file_path)
        filename = file_path.rsplit("/", 1)[-1]
        return UploadResponse.ok("上传成功", file_url, filename)
    except Exception as e:
        logger.error("头像上传失败: %s", e)
        raise HTTPException(status_code=500, detail=f"上传失败: {e}")


@router.get("/{file_path:path}", summary="获取上传的文件")
async def get_file(file_path: str):
    """获取上传的文件 — GET /api/upload/** (catch-all)
    对齐 Java FileUploadController.getFile()

    URL 格式: /api/upload/{urlPrefix}/{relativePath}
    例如: /api/upload/uploads/avatars/abc.png → 相对路径 = avatars/abc.png
    """
    import mimetypes

    url_prefix = settings.file_storage.url_prefix.strip("/")  # "uploads"

    # file_path 是 /api/upload/ 之后的所有内容: "uploads/avatars/abc.png"
    # 剥离 urlPrefix 得到存储相对路径: "avatars/abc.png"
    prefix = f"{url_prefix}/"
    if not file_path.startswith(prefix):
        raise HTTPException(status_code=400, detail="Invalid request path")
    relative_path = file_path[len(prefix):]
    if not relative_path:
        raise HTTPException(status_code=400, detail="Invalid file path")

    # 安全检查 + 读取文件
    base = FileStorageService._get_base_path()
    full_path = (base / relative_path).resolve()
    try:
        FileStorageService._check_path_security(full_path)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")

    if not full_path.exists() or full_path.is_dir():
        raise HTTPException(status_code=404, detail="File not found")

    file_content = full_path.read_bytes()
    content_type, _ = mimetypes.guess_type(str(full_path))
    if not content_type:
        content_type = "application/octet-stream"

    return Response(content=file_content, media_type=content_type)
