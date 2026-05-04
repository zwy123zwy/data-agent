"""EchoController — 对齐 Java EchoController"""
from fastapi import APIRouter

router = APIRouter(prefix="/echo", tags=["心跳检测"])


@router.get("/ok", summary="心跳检测")
async def ok():
    """心跳检测 — 对齐 Java GET /echo/ok"""
    return "ok"
