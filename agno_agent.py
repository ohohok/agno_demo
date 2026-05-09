"""
Agno Agent with Zhipu AI (GLM) - FastAPI Service
知识库集成到 AgentOS UI，聊天支持知识库检索增强
"""
import os
from typing import Optional, List

from dotenv import load_dotenv
from pydantic import BaseModel
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.os import AgentOS
from fastapi import HTTPException

from knowledge_base import knowledge, knowledge_retriever

load_dotenv()

# Get API key from environment variable
api_key = os.getenv("ZHIPUAI_API_KEY")
if not api_key:
    print("⚠️  Warning: ZHIPUAI_API_KEY environment variable not set!")
    print("   Please set it: export ZHIPUAI_API_KEY='your-api-key'")
    print("   Get your API key from: https://open.bigmodel.cn/")
    raise ValueError("ZHIPUAI_API_KEY is required but not set")

# Create agent without tools and database (simple chat mode)
agno_agent = Agent(
    model=OpenAIChat(
        id="glm-4-flash",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        api_key=api_key,
        temperature=0.7,
        max_tokens=2048,
    ),
    markdown=True,
    add_history_to_context=False,
)

# Create the AgentOS，传入 knowledge 实例以启用内置知识库管理
agent_os = AgentOS(agents=[agno_agent], knowledge=[knowledge])
# Get the FastAPI app for the AgentOS
app = agent_os.get_app()


# Request/Response Models
class ChatRequest(BaseModel):
    """Chat request model"""
    message: str
    user_id: Optional[str] = "default_user"
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response model"""
    success: bool
    message: str
    session_id: Optional[str] = None
    run_id: Optional[str] = None
    knowledge_sources: Optional[List[str]] = None  # 引用的知识库来源


# Custom API endpoints
@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    聊天接口，自动从知识库检索相关内容（如果有的话）

    Example usage:
    curl -X POST http://localhost:7777/api/chat \
         -H "Content-Type: application/json" \
         -d '{"message": "你好", "user_id": "user123"}'
    """
    try:
        knowledge_sources = []
        user_message = request.message

        # 自动检索知识库，有结果就用，没结果就正常回答
        kb_results = knowledge_retriever.search(request.message)
        if kb_results:
            context_parts = []
            for i, result in enumerate(kb_results, 1):
                context_parts.append(
                    f"[知识库片段 {i}] (来源: {result['source']})\n{result['content']}"
                )
            kb_context = "\n\n".join(context_parts)
            user_message = (
                f"请基于以下知识库内容回答用户的问题。如果知识库中没有相关信息，请如实说明。\n\n"
                f"=== 知识库内容 ===\n{kb_context}\n=== 知识库内容结束 ===\n\n"
                f"用户问题: {request.message}"
            )
            knowledge_sources = list(set(r["source"] for r in kb_results))

        response = agno_agent.run(
            user_message,
            user_id=request.user_id,
            session_id=request.session_id,
        )

        return ChatResponse(
            success=True,
            message=response.content if response else "No response generated",
            session_id=response.session_id if response else None,
            run_id=response.run_id if response else None,
            knowledge_sources=knowledge_sources if knowledge_sources else None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Agno AI Chat"}


# ************* Run AgentOS *************
if __name__ == "__main__":
    print("\n🚀 Starting Agno AI Chat Service (with Knowledge Base)...")
    print("📡 API Endpoints:")
    print("   - POST /api/chat              : 聊天（支持知识库增强）")
    print("   - POST /knowledge/content     : 上传文件到知识库 (AgentOS UI)")
    print("   - GET  /knowledge/content     : 列出知识库文档 (AgentOS UI)")
    print("   - POST /knowledge/search      : 搜索知识库 (AgentOS UI)")
    print("   - GET  /api/health            : 健康检查")
    print("   - GET  /                      : AgentOS UI")
    print("\n💡 测试聊天:")
    print('   curl -X POST http://localhost:7777/api/chat \\')
    print('        -H "Content-Type: application/json" \\')
    print('        -d \'{"message": "你好"}\'')
    print("\n💡 知识库管理:")
    print("   打开 AgentOS UI: http://localhost:7777")
    print("   在界面中直接上传、管理、搜索知识库文档")
    print("\n" + "="*60)
    agent_os.serve(app="agno_agent:app", reload=True)
