"""
讯飞语音听写 Toolkit（IAT 流式 API）
- 可作为 Agent Tool Calling 使用（LLM 自动调用）
- 也可通过 /api/stt 接口直接调用

使用讯飞语音听写 API（WebSocket 协议）：
  音频格式：PCM，16kHz，16bit，单声道
  协议：wss://iat-api.xfyun.cn/v2/iat
"""
import asyncio
import base64
import hashlib
import hmac
import json
import logging
from typing import Optional

import websockets.legacy.client as websockets_client
from agno.tools.toolkit import Toolkit

from core.config import IFLYTEK_APP_ID, IFLYTEK_API_KEY, IFLYTEK_API_SECRET

logger = logging.getLogger(__name__)

IFLYTEK_IAT_URL = "wss://iat-api.xfyun.cn/v2/iat"


def _build_auth_url(api_key: str, api_secret: str) -> str:
    """生成讯飞 IAT WebSocket 鉴权 URL（HMAC-SHA256 签名）"""
    from urllib.parse import urlencode
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

    signature_origin = f"host: iat-api.xfyun.cn\ndate: {date_str}\nGET /v2/iat HTTP/1.1"

    hmac_obj = hmac.new(
        api_secret.encode("utf-8"),
        signature_origin.encode("utf-8"),
        digestmod=hashlib.sha256,
    )
    signature = base64.b64encode(hmac_obj.digest()).decode("utf-8")

    auth_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    auth_base64 = base64.b64encode(auth_origin.encode("utf-8")).decode("utf-8")

    params = urlencode({"authorization": auth_base64, "date": date_str, "host": "iat-api.xfyun.cn"})
    return f"{IFLYTEK_IAT_URL}?{params}"


async def transcribe_audio(audio_bytes: bytes, app_id: str = "", api_key: str = "", api_secret: str = "") -> str:
    """
    将 PCM 音频转为文字（异步）。

    Args:
        audio_bytes: PCM 音频数据（16kHz, 16bit, 单声道）
        app_id: 讯飞 APP ID（默认从环境变量读取）
        api_key: 讯飞 API Key（默认从环境变量读取）
        api_secret: 讯飞 API Secret（默认从环境变量读取）

    Returns:
        识别出的文字
    """
    app_id = app_id or IFLYTEK_APP_ID
    api_key = api_key or IFLYTEK_API_KEY
    api_secret = api_secret or IFLYTEK_API_SECRET

    if not all([app_id, api_key, api_secret]):
        raise ValueError("讯飞语音听写需要配置 IFLYTEK_APP_ID、IFLYTEK_API_KEY、IFLYTEK_API_SECRET")

    url = _build_auth_url(api_key, api_secret)
    result_texts = []

    try:
        async with websockets_client.connect(url, max_size=10 * 1024 * 1024) as ws:
            chunk_size = 1280  # 40ms @ 16kHz 16bit mono

            async def send_audio():
                for i in range(0, len(audio_bytes), chunk_size):
                    chunk = audio_bytes[i: i + chunk_size]
                    if i == 0:
                        # 第一帧：带参数
                        frame = {
                            "common": {"app_id": app_id},
                            "business": {
                                "language": "zh_cn",
                                "domain": "iat",
                                "accent": "mandarin",
                                "vad_eos": 5000,
                                "dwa": "wpgs",
                            },
                            "data": {
                                "status": 0,
                                "format": "audio/L16;rate=16000",
                                "encoding": "raw",
                                "audio": base64.b64encode(chunk).decode("utf-8"),
                            },
                        }
                    elif i + chunk_size < len(audio_bytes):
                        # 中间帧
                        frame = {
                            "data": {
                                "status": 1,
                                "format": "audio/L16;rate=16000",
                                "encoding": "raw",
                                "audio": base64.b64encode(chunk).decode("utf-8"),
                            },
                        }
                    else:
                        # 最后一帧
                        frame = {
                            "data": {
                                "status": 2,
                                "format": "audio/L16;rate=16000",
                                "encoding": "raw",
                                "audio": base64.b64encode(chunk).decode("utf-8"),
                            },
                        }
                    await ws.send(json.dumps(frame))
                    await asyncio.sleep(0.04)

            async def receive_results():
                while True:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=30)
                        data = json.loads(msg)
                        code = data.get("code", -1)
                        if code != 0:
                            print(f"[STT] 讯飞错误: code={code}, desc={data.get('desc', '')}")
                            return
                        # 解析识别结果
                        result_data = data.get("data", {}).get("result", {})
                        if result_data:
                            ws_list = result_data.get("ws", [])
                            for ws_item in ws_list:
                                for cw in ws_item.get("cw", []):
                                    w = cw.get("w", "")
                                    if w:
                                        result_texts.append(w)
                        # status=2 表示最后一帧
                        if data.get("data", {}).get("status") == 2:
                            return
                    except asyncio.TimeoutError:
                        print("[STT] 讯飞接收超时")
                        return

            await asyncio.gather(send_audio(), receive_results())
    except Exception as e:
        print(f"[STT] 讯飞异常: {type(e).__name__}: {e}")
        raise

    return "".join(result_texts)


def transcribe_audio_sync(audio_bytes: bytes, **kwargs) -> str:
    """同步版本的语音转文字"""
    return asyncio.run(transcribe_audio(audio_bytes, **kwargs))


class IFlytekSTTToolKit(Toolkit):
    """
    讯飞语音听写 Toolkit

    Agent 使用方式：
        agent = Agent(tools=[IFlytekSTTToolKit()])
        # Agent 可以自动调用 speech_to_text 工具

    API 使用方式：
        POST /api/stt  (上传音频文件，返回文字)
    """

    def __init__(self):
        super().__init__(
            name="speech_to_text",
            tools=[self.speech_to_text],
            instructions=(
                "将 PCM 格式的音频数据转换为文字。"
                "音频要求：16kHz 采样率，16bit 位深，单声道。"
                "支持中文普通话识别。"
            ),
        )

    def speech_to_text(self, audio_base64: str) -> str:
        """
        将音频转换为文字。

        Args:
            audio_base64: Base64 编码的 PCM 音频数据（16kHz, 16bit, 单声道）

        Returns:
            识别出的文字
        """
        try:
            audio_bytes = base64.b64decode(audio_base64)
            return transcribe_audio_sync(audio_bytes)
        except Exception as e:
            return f"语音识别失败: {str(e)}"
