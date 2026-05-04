"""
SemanticModel API — 对齐 Java SemanticModelController (10 个端点)
路由前缀: /api/semantic-model
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from ..core.database import get_db
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
    """列出语义模型 — 对齐 Java GET /api/semantic-model?keyword=&agentId="""
    if keyword and keyword.strip():
        result = await SemanticModelService.search_by_keyword(db, keyword)
    elif agentId is not None:
        result = await SemanticModelService.get_by_agent_id(db, agentId)
    else:
        result = await SemanticModelService.get_all(db)
    return {"success": True, "message": "success list semanticModel", "data": result}


@router.get("/{id}", summary="获取语义模型详情")
async def get_model(id: int, db: AsyncSession = Depends(get_db)):
    """获取语义模型详情 — 对齐 Java GET /api/semantic-model/{id}"""
    model = await SemanticModelService.get_semantic_model(db, id)
    if not model:
        return {"success": False, "message": "Semantic model not found"}
    return {"success": True, "message": "success retrieve semanticModel", "data": model}


@router.post("", summary="创建语义模型")
async def create_model(dto: SemanticModelCreate, db: AsyncSession = Depends(get_db)):
    """创建语义模型 — 对齐 Java POST /api/semantic-model"""
    model = await SemanticModelService.create_semantic_model(db, dto.agent_id, dto)
    return {"success": True, "message": "Semantic model created successfully", "data": True}


@router.put("/{id}", summary="更新语义模型")
async def update_model(id: int, model_data: SemanticModelUpdate, db: AsyncSession = Depends(get_db)):
    """更新语义模型 — 对齐 Java PUT /api/semantic-model/{id}"""
    existing = await SemanticModelService.get_semantic_model(db, id)
    if not existing:
        return {"success": False, "message": "Semantic model not found"}
    model = await SemanticModelService.update_semantic_model(db, id, model_data)
    return {"success": True, "message": "Semantic model updated successfully", "data": model}


@router.delete("/{id}", summary="删除语义模型")
async def delete_model(id: int, db: AsyncSession = Depends(get_db)):
    """删除语义模型 — 对齐 Java DELETE /api/semantic-model/{id}"""
    existing = await SemanticModelService.get_semantic_model(db, id)
    if not existing:
        return {"success": False, "message": "Semantic model not found"}
    await SemanticModelService.delete_semantic_model(db, id)
    return {"success": True, "message": "Semantic model deleted successfully", "data": True}


@router.delete("/batch", summary="批量删除语义模型")
async def batch_delete(ids: List[int], db: AsyncSession = Depends(get_db)):
    """批量删除 — 对齐 Java DELETE /api/semantic-model/batch"""
    await SemanticModelService.delete_batch(db, ids)
    return {"success": True, "message": "批量删除成功", "data": True}


@router.put("/enable", summary="批量启用语义模型")
async def enable_fields(ids: List[int], db: AsyncSession = Depends(get_db)):
    """批量启用 — 对齐 Java PUT /api/semantic-model/enable"""
    await SemanticModelService.enable_batch(db, ids)
    return {"success": True, "message": "Semantic models enabled successfully", "data": True}


@router.put("/disable", summary="批量禁用语义模型")
async def disable_fields(ids: List[int], db: AsyncSession = Depends(get_db)):
    """批量禁用 — 对齐 Java PUT /api/semantic-model/disable"""
    await SemanticModelService.disable_batch(db, ids)
    return {"success": True, "message": "Semantic models disabled successfully", "data": True}


@router.post("/batch-import", summary="批量导入语义模型 (JSON)")
async def batch_import(dto: SemanticModelBatchImportDTO, db: AsyncSession = Depends(get_db)):
    """批量导入语义模型 (JSON格式) — 对齐 Java POST /api/semantic-model/batch-import"""
    logger.info(f"开始批量导入语义模型: agentId={dto.agent_id}, 数量={len(dto.items)}")
    result = await SemanticModelService.batch_import(db, dto.agent_id, dto.items)
    logger.info(f"批量导入完成: 总数={result.total}, 成功={result.success_count}, 失败={result.fail_count}")
    return {"success": True, "message": "批量导入完成", "data": result.model_dump(by_alias=True)}


@router.get("/template/download", summary="下载 Excel 导入模板")
async def download_template():
    """下载 Excel 模板 — 对齐 Java GET /api/semantic-model/template/download

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
    """从 Excel 文件导入 — 对齐 Java POST /api/semantic-model/import/excel"""
    agent_id = int(agentId)
    filename = file.filename or "upload.xlsx"

    if not filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 或 .xls 格式")

    try:
        file_content = await file.read()
        result = await SemanticModelService.import_from_excel(db, file_content, filename, agent_id)
        return {"success": True, "message": "Excel导入完成", "data": result.model_dump(by_alias=True)}
    except ValueError as e:
        logger.error(f"Excel导入失败: {e}")
        return {"success": False, "message": f"Excel导入失败: {e}"}
    except Exception as e:
        logger.error(f"Excel导入失败: {e}")
        return {"success": False, "message": f"Excel导入失败: {e}"}
