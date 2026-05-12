"""
Agno Agent with Zhipu AI (GLM) - FastAPI Service
知识库集成到 AgentOS UI，聊天支持知识库检索增强
"""
import os
import json
import asyncio
import time
import logging
from typing import Optional, List

from dotenv import load_dotenv
from pydantic import BaseModel
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.os import AgentOS
from agno.db.sqlite import SqliteDb
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from knowledge_base import knowledge, knowledge_retriever, sanitize_text

load_dotenv()

# 性能日志
perf_logger = logging.getLogger("perf")
_perf_handler = logging.StreamHandler()
_perf_handler.setFormatter(logging.Formatter("[PERF] %(message)s"))
perf_logger.addHandler(_perf_handler)
perf_logger.setLevel(logging.INFO)
perf_logger.propagate = False

# Get API key from environment variable
api_key = os.getenv("ZHIPUAI_API_KEY")
if not api_key:
    print("⚠️  Warning: ZHIPUAI_API_KEY environment variable not set!")
    print("   Please set it: export ZHIPUAI_API_KEY='your-api-key'")
    print("   Get your API key from: https://open.bigmodel.cn/")
    raise ValueError("ZHIPUAI_API_KEY is required but not set")

# 知识库相似度阈值：低于此分数的检索结果不注入上下文
# 可通过环境变量 KB_RELEVANCE_THRESHOLD 调整（默认 0.4）
KB_RELEVANCE_THRESHOLD = float(os.getenv("KB_RELEVANCE_THRESHOLD", "0.4"))

# SQLite 数据库（存储对话历史）
sqlite_db = SqliteDb(db_file="data/agent.db")

# Create agent
agno_agent = Agent(
    model=OpenAIChat(
        id="glm-4-flash",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        api_key=api_key,
        temperature=0.7,
        max_tokens=2048,
    ),
    db=sqlite_db,
    markdown=True,
    add_history_to_context=True,
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
        t_total = time.perf_counter()
        knowledge_sources = []
        # 净化用户输入，防止 surrogate 字符污染 LLM 上下文
        user_message = sanitize_text(request.message)

        # 自动检索知识库，有结果就用，没结果就正常回答
        kb_results = knowledge_retriever.search(user_message, limit=10, threshold=KB_RELEVANCE_THRESHOLD)
        if kb_results:
            context_parts = []
            for i, result in enumerate(kb_results, 1):
                # 净化知识库内容
                clean_content = sanitize_text(result['content'])
                context_parts.append(
                    f"[知识库片段 {i}] (来源: {result['source']})\n{clean_content}"
                )
            kb_context = "\n\n".join(context_parts)
            user_message = (
                f"请优先根据以下知识库内容来回答用户的问题。"
                f"即使知识库内容只是部分相关，也请结合这些内容给出有帮助的回答。"
                f"只有当知识库内容确实与问题完全无关时，再基于你自己的知识回答。\n\n"
                f"=== 知识库内容 ===\n{kb_context}\n=== 知识库内容结束 ===\n\n"
                f"用户问题: {user_message}"
            )
            knowledge_sources = list(set(r["source"] for r in kb_results))

        t_llm = time.perf_counter()
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: agno_agent.run(
                user_message,
                user_id=request.user_id,
                session_id=request.session_id,
            ),
        )
        llm_elapsed = (time.perf_counter() - t_llm) * 1000
        total_elapsed = (time.perf_counter() - t_total) * 1000
        perf_logger.info(f"llm_call: {llm_elapsed:.1f}ms | total_chat: {total_elapsed:.1f}ms | kb_used: {bool(kb_results)}")

        return ChatResponse(
            success=True,
            message=response.content if response else "No response generated",
            session_id=response.session_id if response else None,
            run_id=response.run_id if response else None,
            knowledge_sources=knowledge_sources if knowledge_sources else None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _build_kb_context(kb_results: list) -> tuple[str, list]:
    """从知识库检索结果构建上下文，返回 (prompt_context, sources)"""
    if not kb_results:
        return "", []
    context_parts = []
    for i, result in enumerate(kb_results, 1):
        clean_content = sanitize_text(result['content'])
        context_parts.append(
            f"[知识库片段 {i}] (来源: {result['source']})\n{clean_content}"
        )
    kb_context = "\n\n".join(context_parts)
    sources = list(set(r["source"] for r in kb_results))
    return kb_context, sources


@app.post("/api/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    """
    流式聊天接口（SSE），逐 token 返回响应。

    Example:
        curl -N -X POST http://localhost:7777/api/chat/stream \\
             -H "Content-Type: application/json" \\
             -d '{"message": "你好"}'

    返回格式 (Server-Sent Events):
        data: {"type":"start","session_id":"..."}
        data: {"type":"content","delta":"你"}
        data: {"type":"content","delta":"好"}
        ...
        data: {"type":"done","full_text":"...","knowledge_sources":[...]}
    """
    try:
        knowledge_sources = []
        user_message = sanitize_text(request.message)

        # 知识库检索
        kb_results = knowledge_retriever.search(user_message, limit=10, threshold=KB_RELEVANCE_THRESHOLD)
        if kb_results:
            kb_context, knowledge_sources = _build_kb_context(kb_results)
            user_message = (
                f"请优先根据以下知识库内容来回答用户的问题。"
                f"即使知识库内容只是部分相关，也请结合这些内容给出有帮助的回答。"
                f"只有当知识库内容确实与问题完全无关时，再基于你自己的知识回答。\n\n"
                f"=== 知识库内容 ===\n{kb_context}\n=== 知识库内容结束 ===\n\n"
                f"用户问题: {user_message}"
            )

        def generate():
            """SSE 生成器，逐 token 流式输出"""
            t0 = time.perf_counter()
            full_text = ""
            session_id = None

            # 发送 start 事件
            yield f"data: {json.dumps({'type': 'start'}, ensure_ascii=False)}\n\n"

            try:
                # 流式调用 agent
                run_response = agno_agent.run(
                    user_message,
                    user_id=request.user_id,
                    session_id=request.session_id,
                    stream=True,
                )

                for chunk in run_response:
                    if chunk and chunk.content:
                        delta = chunk.content
                        full_text_length_before = len(full_text)
                        # agno 流式模式下每次返回的是累积内容，取增量部分
                        if len(delta) > full_text_length_before:
                            new_delta = delta[full_text_length_before:]
                            full_text = delta
                            if new_delta:
                                yield f"data: {json.dumps({'type': 'content', 'delta': new_delta}, ensure_ascii=False)}\n\n"
                        else:
                            full_text = delta

                    if chunk and chunk.session_id:
                        session_id = chunk.session_id

            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
                return

            elapsed = (time.perf_counter() - t0) * 1000
            perf_logger.info(f"llm_stream: {elapsed:.1f}ms | chars: {len(full_text)} | kb_used: {bool(kb_results)}")

            # 发送 done 事件，包含完整文本和元数据
            done_data = {
                "type": "done",
                "full_text": full_text,
                "session_id": session_id,
                "knowledge_sources": knowledge_sources if knowledge_sources else None,
            }
            yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
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
    print("   - POST /api/chat/stream       : 流式聊天（SSE，逐 token 返回）")
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
