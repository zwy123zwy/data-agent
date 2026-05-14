"""
python-agent-v2 启动入口

用法:
    python main.py                  # 默认 8100 端口
    python main.py --port 8080      # 指定端口
    python main.py --reload         # 开发模式热重载
"""

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="data-agent-server")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8200, help="监听端口")
    parser.add_argument("--reload", action="store_true", help="启用热重载 (开发模式)")
    args = parser.parse_args()

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
