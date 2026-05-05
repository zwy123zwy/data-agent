# 心跳检测
from fastapi import APIRouter

router = APIRouter(prefix="/echo", tags=["心跳检测"])


@router.get("/ok", summary="心跳检测")
async def ok():

    return "ok"
