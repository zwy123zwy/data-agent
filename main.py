"""
python-agent-v2 启动入口

用法:
    python main.py                  # 默认 8200 端口，热重载开启
    python main.py --port 8080      # 指定端口
    python main.py --no-reload      # 关闭热重载（生产模式）
"""

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="data-agent-server")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8200, help="监听端口")
    parser.add_argument("--no-reload", action="store_true", help="禁用热重载 (生产模式)")
    args = parser.parse_args()

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=not args.no_reload,
        log_level="info",
    )
