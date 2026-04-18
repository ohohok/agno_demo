"""
Agno Agent with Zhipu AI (GLM) - FastAPI Service
Provides RESTful API endpoints for AI chat interactions
"""
import os
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.os import AgentOS
from fastapi import HTTPException

# Load environment variables from .env file
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
    add_history_to_context=True,  # Keep conversation history in memory
)
# Create the AgentOS
agent_os = AgentOS(agents=[agno_agent])
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


# Custom API endpoints
@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Simple chat endpoint for direct API interaction
    
    Example usage:
    curl -X POST http://localhost:7777/api/chat \
         -H "Content-Type: application/json" \
         -d '{"message": "你好", "user_id": "user123"}'
    """
    try:
        response = agno_agent.run(
            request.message,
            user_id=request.user_id,
            session_id=request.session_id,
        )
        
        return ChatResponse(
            success=True,
            message=response.content if response else "No response generated",
            session_id=response.session_id if response else None,
            run_id=response.run_id if response else None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Agno AI Chat"}


# ************* Run AgentOS *************
if __name__ == "__main__":
    print("\n🚀 Starting Agno AI Chat Service...")
    print("📡 API Endpoints:")
    print("   - POST /api/chat     : Chat with AI")
    print("   - GET  /api/health   : Health check")
    print("   - GET  /             : AgentOS UI")
    print("\n💡 Test the API:")
    print('   curl -X POST http://localhost:7777/api/chat \\')
    print('        -H "Content-Type: application/json" \\')
    print('        -d \'{"message": "你好"}\'')
    print("\n" + "="*60)
    agent_os.serve(app="agno_agent:app", reload=True)
