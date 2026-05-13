"""
API 路由 — 聊天、流式聊天、语音转文字
所有对外暴露的接口集中在这里
"""
import asyncio
import base64
import json
import time
import logging
from typing import Optional, List

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, UploadFile, File, WebSocket
from fastapi.responses import StreamingResponse
import websockets.legacy.client as websockets_client_mod

from core.config import KB_RELEVANCE_THRESHOLD, KB_SEARCH_LIMIT
from core.knowledge import knowledge_retriever, sanitize_text

perf_logger = logging.getLogger("perf")

router = APIRouter()


# ============ 请求/响应模型 ============

class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = "default_user"
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    success: bool
    message: str
    session_id: Optional[str] = None
    run_id: Optional[str] = None
    knowledge_sources: Optional[List[str]] = None


class STTResponse(BaseModel):
    success: bool
    text: str
    error: Optional[str] = None


# ============ 工具函数 ============

def _build_kb_context(kb_results: list) -> tuple[str, list]:
    if not kb_results:
        return "", []
    context_parts = []
    for i, result in enumerate(kb_results, 1):
        clean_content = sanitize_text(result["content"])
        context_parts.append(f"[知识库片段 {i}] (来源: {result['source']})\n{clean_content}")
    kb_context = "\n\n".join(context_parts)
    sources = list(set(r["source"] for r in kb_results))
    return kb_context, sources


def _inject_kb_context(user_message: str) -> tuple[str, list]:
    """检索知识库并构建增强后的消息，返回 (enhanced_message, sources)"""
    kb_results = knowledge_retriever.search(user_message, limit=KB_SEARCH_LIMIT, threshold=KB_RELEVANCE_THRESHOLD)
    if not kb_results:
        return user_message, []
    kb_context, sources = _build_kb_context(kb_results)
    enhanced = (
        f"请优先根据以下知识库内容来回答用户的问题。"
        f"即使知识库内容只是部分相关，也请结合这些内容给出有帮助的回答。"
        f"只有当知识库内容确实与问题完全无关时，再基于你自己的知识回答。\n\n"
        f"=== 知识库内容 ===\n{kb_context}\n=== 知识库内容结束 ===\n\n"
        f"用户问题: {user_message}"
    )
    return enhanced, sources


# ============ 聊天接口 ============

def register_chat_routes(app, agent):
    """注册聊天相关路由（需要传入 agent 实例以避免循环导入）"""

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat_endpoint(request: ChatRequest):
        try:
            t_total = time.perf_counter()
            user_message = sanitize_text(request.message)
            user_message, knowledge_sources = _inject_kb_context(user_message)

            t_llm = time.perf_counter()
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: agent.run(user_message, user_id=request.user_id, session_id=request.session_id),
            )
            llm_elapsed = (time.perf_counter() - t_llm) * 1000
            total_elapsed = (time.perf_counter() - t_total) * 1000
            perf_logger.info(f"llm_call: {llm_elapsed:.1f}ms | total_chat: {total_elapsed:.1f}ms | kb_used: {bool(knowledge_sources)}")

            return ChatResponse(
                success=True,
                message=response.content if response else "No response generated",
                session_id=response.session_id if response else None,
                run_id=response.run_id if response else None,
                knowledge_sources=knowledge_sources or None,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/chat/stream")
    async def chat_stream_endpoint(request: ChatRequest):
        try:
            user_message = sanitize_text(request.message)
            user_message, knowledge_sources = _inject_kb_context(user_message)

            def generate():
                t0 = time.perf_counter()
                full_text = ""
                session_id = None
                yield f"data: {json.dumps({'type': 'start'}, ensure_ascii=False)}\n\n"

                try:
                    run_response = agent.run(
                        user_message, user_id=request.user_id, session_id=request.session_id, stream=True,
                    )
                    for chunk in run_response:
                        if chunk and chunk.content:
                            delta = chunk.content
                            full_text_length_before = len(full_text)
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
                perf_logger.info(f"llm_stream: {elapsed:.1f}ms | chars: {len(full_text)} | kb_used: {bool(knowledge_sources)}")
                done_data = {"type": "done", "full_text": full_text, "session_id": session_id, "knowledge_sources": knowledge_sources or None}
                yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n"

            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/health")
    async def health_check():
        return {"status": "healthy", "service": "Agno AI Chat"}


# ============ 语音转文字接口 ============

def register_stt_routes(app, for_ws=None):
    """注册 STT 相关路由

    for_ws=None: 注册 HTTP + WebSocket（默认）
    for_ws=False: 仅注册 HTTP POST /api/stt
    for_ws=True:  仅注册 WebSocket /stt
    """

    if for_ws is not False:
        @app.post("/api/stt", response_model=STTResponse)
        async def stt_endpoint(file: UploadFile = File(...)):
            """
            语音转文字接口（批量模式）

            上传 PCM/WAV 音频文件（16kHz, 16bit, 单声道），返回识别文字。
            """
            try:
                from tools.speech.iflytek import transcribe_audio

                audio_bytes = await file.read()
                perf_logger.info(f"stt: 收到音频 {len(audio_bytes)} bytes, filename={file.filename}")
                if not audio_bytes:
                    return STTResponse(success=False, text="", error="空音频文件")

                t0 = time.perf_counter()
                text = await transcribe_audio(audio_bytes)
                elapsed = (time.perf_counter() - t0) * 1000
                perf_logger.info(f"stt: {elapsed:.1f}ms | chars: {len(text)}")

                return STTResponse(success=True, text=text)
            except ValueError as e:
                return STTResponse(success=False, text="", error=str(e))
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

    if for_ws is not False:
        @app.websocket("/stt")
        async def stt_websocket(websocket: WebSocket):
            """
            实时语音转文字 WebSocket（流式模式）

            客户端发送 PCM 音频 chunks → 服务端转发到讯飞 → 识别结果实时返回。
            协议：
              客户端发送: binary PCM 数据 或 JSON {"action": "end"}
              服务端返回: JSON {"type": "partial", "text": "..."} 或 {"type": "final", "text": "..."}
            """
            from tools.speech.iflytek import _build_auth_url, IFLYTEK_IAT_URL
            from core.config import IFLYTEK_APP_ID, IFLYTEK_API_KEY, IFLYTEK_API_SECRET

            if not all([IFLYTEK_APP_ID, IFLYTEK_API_KEY, IFLYTEK_API_SECRET]):
                await websocket.accept()
                await websocket.send_json({"type": "error", "message": "讯飞凭证未配置"})
                await websocket.close()
                return

            await websocket.accept()

            try:
                auth_url = _build_auth_url(IFLYTEK_API_KEY, IFLYTEK_API_SECRET)
                async with websockets_client_mod.connect(auth_url, max_size=10 * 1024 * 1024) as iflytek_ws:
                    # 发送第一帧（空音频，仅参数）
                    first_frame = {
                        "common": {"app_id": IFLYTEK_APP_ID},
                        "business": {
                            "language": "zh_cn",
                            "domain": "iat",
                            "accent": "mandarin",
                            "vad_eos": 3000,
                            "dwa": "wpgs",
                        },
                        "data": {
                            "status": 0,
                            "format": "audio/L16;rate=16000",
                            "encoding": "raw",
                            "audio": "",
                        },
                    }
                    await iflytek_ws.send(json.dumps(first_frame))

                    async def forward_to_iflytek():
                        """接收浏览器音频 → 转发到讯飞"""
                        while True:
                            try:
                                msg = await websocket.receive()
                                if "bytes" in msg:
                                    chunk = msg["bytes"]
                                    if len(chunk) > 0:
                                        frame = {
                                            "data": {
                                                # 首帧参数已发送，音频流阶段固定使用中间帧 status=1
                                                "status": 1,
                                                "format": "audio/L16;rate=16000",
                                                "encoding": "raw",
                                                "audio": base64.b64encode(chunk).decode("utf-8"),
                                            },
                                        }
                                        await iflytek_ws.send(json.dumps(frame))
                                elif "text" in msg:
                                    data = json.loads(msg["text"])
                                    if data.get("action") == "end":
                                        # 发送最后一帧
                                        end_frame = {
                                            "data": {
                                                "status": 2,
                                                "format": "audio/L16;rate=16000",
                                                "encoding": "raw",
                                                "audio": "",
                                            },
                                        }
                                        await iflytek_ws.send(json.dumps(end_frame))
                                        return
                            except Exception:
                                return

                    async def forward_to_browser():
                        """接收讯飞结果 → 转发到浏览器"""
                        full_text = ""
                        while True:
                            try:
                                msg = await asyncio.wait_for(iflytek_ws.recv(), timeout=30)
                                data = json.loads(msg)
                                code = data.get("code", -1)
                                if code != 0:
                                    await websocket.send_json({
                                        "type": "error",
                                        "message": data.get("desc", f"讯飞错误 code={code}"),
                                    })
                                    return

                                # 解析识别结果
                                result_data = data.get("data", {}).get("result", {})
                                status = data.get("data", {}).get("status", -1)
                                chunk_text = ""
                                if result_data:
                                    for ws_item in result_data.get("ws", []):
                                        for cw in ws_item.get("cw", []):
                                            w = cw.get("w", "")
                                            if w:
                                                chunk_text += w

                                if chunk_text:
                                    full_text += chunk_text
                                    await websocket.send_json({
                                        "type": "partial",
                                        "text": chunk_text,
                                        "full_text": full_text,
                                    })

                                if status == 2:
                                    await websocket.send_json({
                                        "type": "final",
                                        "text": full_text,
                                    })
                                    return
                            except asyncio.TimeoutError:
                                await websocket.send_json({"type": "error", "message": "讯飞响应超时"})
                                return
                            except Exception:
                                return

                    await asyncio.gather(forward_to_iflytek(), forward_to_browser())

            except Exception as e:
                try:
                    await websocket.send_json({"type": "error", "message": str(e)})
                except Exception:
                    pass
            finally:
                try:
                    await websocket.close()
                except Exception:
                    pass
