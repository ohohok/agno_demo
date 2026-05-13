"""
Agno AI Chat Service — 主入口
  python main.py          启动 API 服务（默认）
  python main.py --chat   启动交互式命令行聊天
"""
import argparse


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agno AI Chat Service")
    parser.add_argument("--chat", action="store_true", help="启动交互式命令行聊天模式")
    args = parser.parse_args()

    if args.chat:
        from app.cli import interactive_chat
        interactive_chat()
    else:
        from app.api import serve
        serve()
