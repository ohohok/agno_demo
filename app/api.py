"""API 服务入口 — AgentOS + 自定义路由 + 静态文件"""
import logging
from pathlib import Path

from starlette.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from agno.os import AgentOS

from core.config import (
    CORS_ALLOW_ORIGINS,
    CORS_ALLOW_ORIGIN_REGEX,
    CORS_ALLOW_CREDENTIALS,
    APP_HOST,
    APP_PORT,
)
from core.knowledge import knowledge
from app.agent import create_agent
from api.routes import register_chat_routes, register_stt_routes

# 性能日志
perf_logger = logging.getLogger("perf")
_perf_handler = logging.StreamHandler()
_perf_handler.setFormatter(logging.Formatter("[PERF] %(message)s"))
perf_logger.addHandler(_perf_handler)
perf_logger.setLevel(logging.INFO)
perf_logger.propagate = False

# Agent + FastAPI 应用
agent = create_agent()

agent_os = AgentOS(agents=[agent], knowledge=[knowledge])
app = agent_os.get_app()

# 覆盖 AgentOS 的 CORS 配置，允许所有本地来源（开发用）
app.user_middleware = [m for m in app.user_middleware if m.cls != CORSMiddleware]
app.middleware_stack = None

cors_allow_credentials = CORS_ALLOW_CREDENTIALS
cors_allow_origins = CORS_ALLOW_ORIGINS
cors_allow_origin_regex = CORS_ALLOW_ORIGIN_REGEX

# CORS 规范：allow_credentials=true 时不能与 allow_origins=["*"] 同时使用
if cors_allow_credentials and cors_allow_origins == ["*"]:
    cors_allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins,
    allow_origin_regex=cors_allow_origin_regex,
    allow_credentials=cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

register_chat_routes(app, agent)
register_stt_routes(app)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/ui")
    async def web_ui():
        return FileResponse(str(STATIC_DIR / "index.html"))


def serve():
    print("\n🚀 Starting Agno AI Chat Service...")
    print("📡 API Endpoints:")
    print("   - POST /api/chat         : 聊天（支持知识库增强）")
    print("   - POST /api/chat/stream  : 流式聊天（SSE）")
    print("   - POST /api/stt          : 语音转文字")
    print("   - WS   /stt              : 实时语音转文字")
    print("   - GET  /api/health       : 健康检查")
    print("   - GET  /ui               : Web 聊天界面")
    print("   - GET  /                 : AgentOS API 信息")
    print("=" * 60)
    agent_os.serve(app="app.api:app", host=APP_HOST, port=APP_PORT, reload=True)
