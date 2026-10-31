"""Speech capabilities. No UI dependencies and no machine-specific paths."""
from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlparse
from xml.sax.saxutils import escape, quoteattr

import requests

from .extensions import Field, SpeechProvider


def http_url(value):
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("请填写有效的 HTTP(S) 接口地址，不要在地址中嵌入密钥")
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("远程 API 必须使用 HTTPS；本机接口可使用 HTTP")
    return value.rstrip("/")


def key(settings):
    value = settings.get("api_key", "") or os.environ.get(settings.get("key_env", ""), "")
    if not value:
        raise ValueError("请填写 API Key，或设置指定的密钥环境变量")
    return value


def request_audio(url, *, headers=None, payload=None, body=None):
    with requests.Session() as client:
        client.trust_env = False  # local AI must not accidentally use a global proxy
        response = client.post(http_url(url), headers=headers, json=payload, data=body,
                               timeout=(10, 600), allow_redirects=False)
    if not response.ok or 300 <= response.status_code < 400:
        # Do not echo the response body: third parties can include credentials in errors.
        raise ValueError(f"语音服务请求失败：HTTP {response.status_code}。请检查接口、权限和配额。")
    return response.content


def gpt_sovits(settings, text):
    from .services import local_url
    reference = Path(settings.get("reference", ""))
    if not reference.is_file() or not settings.get("prompt", "").strip():
        raise ValueError("请选择参考音频，并填写逐字对应的参考原文")
    payload = dict(text=text, text_lang=settings.get("text_lang", "zh"), ref_audio_path=str(reference.resolve()),
                   prompt_text=settings["prompt"], prompt_lang=settings.get("prompt_lang", "zh"),
                   speed_factor=float(settings.get("speed", 1)), media_type="wav", streaming_mode=False,
                   text_split_method="cut5", batch_size=1, seed=-1)
    from .managed_api import api
    api.ensure(settings)
    return request_audio(local_url(settings["url"]) + "/tts", payload=payload)


def compatible(settings, text):
    if not settings.get("model") or not settings.get("voice"):
        raise ValueError("请填写服务提供方支持的模型和音色 ID")
    payload = dict(model=settings["model"], voice=settings["voice"], input=text, response_format="wav",
                   speed=float(settings.get("speed", 1)))
    headers = {"Content-Type": "application/json"}
    if settings.get("api_key") or os.environ.get(settings.get("key_env", ""), ""):
        headers["Authorization"] = "Bearer " + key(settings)
    return request_audio(settings["url"], headers=headers, payload=payload)


def azure(settings, text):
    if not settings.get("voice") or not settings.get("locale"):
        raise ValueError("请填写 Azure 音色和语言区域")
    speed = float(settings.get("speed", 1))
    if not .5 <= speed <= 2:
        raise ValueError("Azure 语速需在 0.5–2.0 之间")
    ssml = (f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang={quoteattr(settings["locale"])}>'
            f'<voice name={quoteattr(settings["voice"])}><prosody rate="{(speed - 1) * 100:+.0f}%">'
            f'{escape(text)}</prosody></voice></speak>')
    return request_audio(settings["url"], headers={"Ocp-Apim-Subscription-Key": key(settings),
                         "Content-Type": "application/ssml+xml", "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
                         "User-Agent": "WallpaperCompanion"}, body=ssml.encode("utf-8"))


def remote_check(settings):
    http_url(settings["url"])
    return "接口地址格式有效。云端鉴权与音色支持请通过生成一条短台词验证（会产生服务调用）。"


def builtin_providers():
    from .services import api_status, start_api
    secret_fields = [Field("api_key", "API Key", "password", "", "保存时写入 Windows 凭据管理器，不写入配置文件"),
                     Field("key_env", "密钥环境变量名", default="", help="可选，例如 AZURE_SPEECH_KEY")]
    return [
        SpeechProvider("gpt_sovits", "本地 GPT-SoVITS", [
            Field("url", "API 地址", default="http://127.0.0.1:9880"),
            Field("project", "项目目录", "directory"), Field("python", "Python 可执行文件（可选）", "file"),
            Field("reference", "参考音频", "file"), Field("prompt", "参考音频原文", "multiline"),
            Field("text_lang", "目标语言代码", default="zh"), Field("prompt_lang", "参考语言代码", default="zh"),
            Field("speed", "语速", "float", 1.0)], gpt_sovits, api_status,
            "仅在生成时自动启动本地 API，退出声伴时停止自建 API；已运行的外部接口只复用。参考音频与原文必须对应，沿用当前模型。", start_api),
        SpeechProvider("azure_speech", "微软 Azure Speech", [
            Field("url", "完整合成接口地址", default="", help="例如 https://eastasia.tts.speech.microsoft.com/cognitiveservices/v1"),
            *secret_fields, Field("voice", "音色 ID", default="zh-CN-XiaoxiaoNeural"),
            Field("locale", "语言区域", default="zh-CN"), Field("speed", "语速", "float", 1.0)],
            azure, remote_check, "台词将发送给你配置的 Azure Speech 服务，按该服务账户计费。"),
        SpeechProvider("openai_compatible", "OpenAI 兼容 TTS", [
            Field("url", "完整合成接口地址", default="", help="填写服务提供方的完整 /audio/speech 地址"),
            *secret_fields, Field("model", "模型 ID"), Field("voice", "音色 ID"), Field("speed", "语速", "float", 1.0)],
            compatible, remote_check, "适用于返回 WAV 的 /audio/speech 兼容服务。模型和音色由服务方决定，不内置固定模型。")]
