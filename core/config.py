"""统一配置管理 — 所有环境变量和常量集中在这里"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 按 config.py 位置定位 .env，避免 uvicorn --reload 改变工作目录导致找不到
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ============ 路径 ============
DATA_DIR = Path("data")
CHROMA_DIR = str(DATA_DIR / "chromadb")
UPLOAD_DIR = DATA_DIR / "uploads"
DB_FILE = str(DATA_DIR / "agent.db")

# ============ LLM ============
ZHIPUAI_API_KEY = os.getenv("ZHIPUAI_API_KEY", "")
ZHIPUAI_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
ZHIPUAI_MODEL_ID = "glm-4-flash"

# ============ 知识库 ============
KB_RELEVANCE_THRESHOLD = float(os.getenv("KB_RELEVANCE_THRESHOLD", "0.4"))
KB_SEARCH_LIMIT = 10
EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
EMBEDDING_DIMENSIONS = 512

# ============ 讯飞语音听写 ============
IFLYTEK_APP_ID = os.getenv("IFLYTEK_APP_ID", "")
IFLYTEK_API_KEY = os.getenv("IFLYTEK_API_KEY", "")
IFLYTEK_API_SECRET = os.getenv("IFLYTEK_API_SECRET", "")

# ============ 服务监听 ============
APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", "7777"))

# ============ CORS ============
# 支持：
# 1) CORS_ALLOW_ORIGINS="*" 或 "http://127.0.0.1:7777,http://localhost:7777"
# 2) CORS_ALLOW_ORIGIN_REGEX="^(https?://(localhost|127\\.0\\.0\\.1)(:\\d+)?)$|^null$"
# 3) CORS_ALLOW_CREDENTIALS="true/false"
CORS_ALLOW_ORIGINS_RAW = os.getenv("CORS_ALLOW_ORIGINS", "")
CORS_ALLOW_ORIGIN_REGEX = os.getenv(
    "CORS_ALLOW_ORIGIN_REGEX",
    r"^(https?://(localhost|127\.0\.0\.1)(:\d+)?)$|^null$",
).strip() or None
CORS_ALLOW_CREDENTIALS = os.getenv("CORS_ALLOW_CREDENTIALS", "true").strip().lower() in {"1", "true", "yes", "on"}

if CORS_ALLOW_ORIGINS_RAW.strip() == "*":
    CORS_ALLOW_ORIGINS = ["*"]
elif CORS_ALLOW_ORIGINS_RAW.strip():
    CORS_ALLOW_ORIGINS = [o.strip() for o in CORS_ALLOW_ORIGINS_RAW.split(",") if o.strip()]
else:
    CORS_ALLOW_ORIGINS = []
