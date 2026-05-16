"""
语义模型管理接口
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from ..core.database import get_db
from ..schemas.common import ApiResponse
from ..services.semantic_model_service import SemanticModelService
from ..schemas.semantic_model import (
    SemanticModelCreate, SemanticModelUpdate, SemanticModelResponse,
    SemanticModelImportItem, SemanticModelBatchImportDTO, BatchImportResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/semantic-model", tags=["SemanticModel"])


@router.get("", summary="列出语义模型")
async def list_models(
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    agentId: Optional[int] = Query(None, description="Agent ID 过滤"),
    db: AsyncSession = Depends(get_db),
):

    if keyword and keyword.strip():
        result = await SemanticModelService.search_by_keyword(db, keyword)
    elif agentId is not None:
        result = await SemanticModelService.get_by_agent_id(db, agentId)
    else:
        result = await SemanticModelService.get_all(db)
    data = [SemanticModelResponse.model_validate(m).model_dump(by_alias=True) for m in result]
    return ApiResponse.ok(data=data, message="success")


@router.get("/{id}", summary="获取语义模型详情")
async def get_model(id: int, db: AsyncSession = Depends(get_db)):

    model = await SemanticModelService.get_semantic_model(db, id)
    if not model:
        return ApiResponse.fail(message="Semantic model not found")
    data = SemanticModelResponse.model_validate(model).model_dump(by_alias=True)
    return ApiResponse.ok(data=data, message="success")


@router.post("", summary="创建语义模型")
async def create_model(dto: SemanticModelCreate, db: AsyncSession = Depends(get_db)):
    
    model = await SemanticModelService.create_semantic_model(db, dto.agent_id, dto)
    return ApiResponse.ok(message="Semantic model created successfully")


@router.put("/{id}", summary="更新语义模型")
async def update_model(id: int, model_data: SemanticModelUpdate, db: AsyncSession = Depends(get_db)):
    
    existing = await SemanticModelService.get_semantic_model(db, id)
    if not existing:
        return ApiResponse.fail(message="Semantic model not found")
    model = await SemanticModelService.update_semantic_model(db, id, model_data)
    data = SemanticModelResponse.model_validate(model).model_dump(by_alias=True)
    return ApiResponse.ok(data=data, message="Semantic model updated successfully")


@router.delete("/{id}", summary="删除语义模型")
async def delete_model(id: int, db: AsyncSession = Depends(get_db)):
    
    existing = await SemanticModelService.get_semantic_model(db, id)
    if not existing:
        return ApiResponse.fail(message="Semantic model not found")
    await SemanticModelService.delete_semantic_model(db, id)
    return ApiResponse.ok(message="Semantic model deleted successfully")


@router.delete("/batch", summary="批量删除语义模型")
async def batch_delete(ids: List[int], db: AsyncSession = Depends(get_db)):
    
    await SemanticModelService.delete_batch(db, ids)
    return ApiResponse.ok(message="批量删除成功")


@router.put("/enable", summary="批量启用语义模型")
async def enable_fields(ids: List[int], db: AsyncSession = Depends(get_db)):
    
    await SemanticModelService.enable_batch(db, ids)
    return ApiResponse.ok(message="Semantic models enabled successfully")


@router.put("/disable", summary="批量禁用语义模型")
async def disable_fields(ids: List[int], db: AsyncSession = Depends(get_db)):
    
    await SemanticModelService.disable_batch(db, ids)
    return ApiResponse.ok(message="Semantic models disabled successfully")


@router.post("/batch-import", summary="批量导入语义模型 (JSON)")
async def batch_import(dto: SemanticModelBatchImportDTO, db: AsyncSession = Depends(get_db)):
    
    logger.info(f"开始批量导入语义模型: agentId={dto.agent_id}, 数量={len(dto.items)}")
    result = await SemanticModelService.batch_import(db, dto.agent_id, dto.items)
    logger.info(f"批量导入完成: 总数={result.total}, 成功={result.success_count}, 失败={result.fail_count}")
    return ApiResponse.ok(data=result.model_dump(by_alias=True), message="批量导入完成")


@router.get("/template/download", summary="下载 Excel 导入模板")
async def download_template():
    """
    返回一个简单的 Excel 模板文件，包含表头行:
      表名* | 字段名* | 业务名称* | 数据类型* | 同义词 | 业务描述 | 字段注释 | 创建时间
    """
    try:
        import openpyxl
        from io import BytesIO

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "语义模型导入模板"
        headers = ["表名*", "字段名*", "业务名称*", "数据类型*", "同义词", "业务描述", "字段注释", "创建时间"]
        ws.append(headers)

        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        wb.close()

        return Response(
            content=buf.getvalue(),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": "attachment; filename=semantic_model_template.xlsx",
            },
        )
    except ImportError:
        raise HTTPException(status_code=500, detail="需要安装 openpyxl: pip install openpyxl")


@router.post("/import/excel", summary="从 Excel 导入语义模型")
async def import_excel(
    file: UploadFile = File(...),
    agentId: str = Form(..., description="Agent ID"),
    db: AsyncSession = Depends(get_db),
):
    
    agent_id = int(agentId)
    filename = file.filename or "upload.xlsx"

    if not filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 或 .xls 格式")

    try:
        file_content = await file.read()
        result = await SemanticModelService.import_from_excel(db, file_content, filename, agent_id)
        return ApiResponse.ok(data=result.model_dump(by_alias=True), message="Excel导入完成")
    except ValueError as e:
        logger.error(f"Excel导入失败: {e}")
        return ApiResponse.fail(message=f"Excel导入失败: {e}")
    except Exception as e:
        logger.error(f"Excel导入失败: {e}")
        return ApiResponse.fail(message=f"Excel导入失败: {e}")
