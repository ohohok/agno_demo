"""Agent 创建和配置"""
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.db.sqlite import SqliteDb

from core.config import ZHIPUAI_API_KEY, ZHIPUAI_BASE_URL, ZHIPUAI_MODEL_ID, DB_FILE
from tools import IFlytekSTTToolKit


def create_agent() -> Agent:
    """创建配置好的 Agent（含工具注册）"""
    if not ZHIPUAI_API_KEY:
        raise ValueError("ZHIPUAI_API_KEY 未设置，请在 .env 中配置")

    return Agent(
        model=OpenAIChat(
            id=ZHIPUAI_MODEL_ID,
            base_url=ZHIPUAI_BASE_URL,
            api_key=ZHIPUAI_API_KEY,
            temperature=0.7,
            max_tokens=2048,
        ),
        db=SqliteDb(db_file=DB_FILE),
        tools=[IFlytekSTTToolKit()],
        markdown=True,
        add_history_to_context=True,
    )
