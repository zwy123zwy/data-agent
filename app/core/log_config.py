"""
日志系统初始化 — 在 FastAPI app 创建前调用，确保 reload 子进程不被 uvicorn 覆盖

用法: 在 app/main.py 最顶部 (FastAPI() 之前) 调用 setup_logging()
"""
import logging
import logging.handlers
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

DETAIL_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
SIMPLE_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"


def setup_logging() -> None:
    # 根日志记录器
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # 清除已有 handler，防止重复 (reload 模式下模块重新 import 会重新执行)
    if root.handlers:
        root.handlers.clear()

    # ---- 控制台 handler ----
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    console.setFormatter(logging.Formatter(SIMPLE_FORMAT))
    root.addHandler(console)

    # ---- 按天轮转文件 handler ----
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=LOG_DIR / "app.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(DETAIL_FORMAT))
    root.addHandler(file_handler)

    # ---- 错误日志单独文件 ----
    error_handler = logging.handlers.RotatingFileHandler(
        filename=LOG_DIR / "error.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(DETAIL_FORMAT))
    root.addHandler(error_handler)

    # 控制第三方库日志噪音 + 防重复
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    sa = logging.getLogger("sqlalchemy.engine")
    sa.setLevel(logging.WARNING)
    sa.propagate = False  # 禁止传播到 root，避免重复输出

    logging.getLogger(__name__).info("日志系统初始化完成")
