#!/usr/bin/env python3
"""
DeckView CLI入口
支持指定目录启动文档服务器
"""
import argparse
import sys
from pathlib import Path


def main():
    """CLI主入口"""
    parser = argparse.ArgumentParser(
        prog="deckview",
        description="DeckView - Web文档查看器，支持PPT、PDF、Markdown在线预览",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  deckview /path/to/docs          # 启动服务，扫描指定目录
  deckview /path/to/docs -p 8080  # 指定端口
  deckview /path/to/docs --host 0.0.0.0  # 允许外部访问
  deckview --version              # 显示版本
        """
    )

    parser.add_argument(
        "directory",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="要扫描的文档目录（默认为当前目录）"
    )

    parser.add_argument(
        "-p", "--port",
        type=int,
        default=8000,
        help="服务端口（默认: 8000）"
    )

    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="监听地址（默认: 127.0.0.1，仅本地访问）"
    )

    parser.add_argument(
        "--no-watch",
        action="store_true",
        help="禁用文件变化监听"
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        help="开发模式：代码变化时自动重载"
    )

    parser.add_argument(
        "-v", "--version",
        action="version",
        version="%(prog)s 2.0.0"
    )

    args = parser.parse_args()

    # 验证目录存在
    content_dir = args.directory.resolve()
    if not content_dir.exists():
        print(f"错误: 目录不存在: {content_dir}", file=sys.stderr)
        sys.exit(1)

    if not content_dir.is_dir():
        print(f"错误: 路径不是目录: {content_dir}", file=sys.stderr)
        sys.exit(1)

    # 设置内容目录
    from deckview.core.config import set_content_dir, settings, ensure_directories
    set_content_dir(content_dir)
    ensure_directories()

    # 更新 host 和 port 到配置（供服务注册使用）
    import os
    settings.HOST = args.host
    settings.PORT = args.port
    # 同时设置环境变量，确保 --reload 模式下也能正确读取
    os.environ["DECKVIEW_HOST"] = args.host
    os.environ["DECKVIEW_PORT"] = str(args.port)

    # 设置是否启用文件监听
    os.environ["DECKVIEW_WATCH"] = "0" if args.no_watch else "1"

    # 打印启动信息
    print()
    print("=" * 50)
    print("  DeckView - Web文档查看器")
    print("=" * 50)
    print()
    print(f"  文档目录: {content_dir}")
    print(f"  访问地址: http://{args.host}:{args.port}")
    print(f"  文件监听: {'已禁用' if args.no_watch else '已启用'}")
    print()
    print("  按 Ctrl+C 停止服务")
    print()

    # 启动uvicorn
    import uvicorn
    uvicorn.run(
        "deckview.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()
