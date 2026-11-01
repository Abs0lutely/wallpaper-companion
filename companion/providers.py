"""Speech capabilities. No UI dependencies and no machine-specific paths."""
from __future__ import annotations
from .i18n import tr

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
        raise ValueError(tr('ui.37099c146dc6', '请填写有效的 HTTP(S) 接口地址，不要在地址中嵌入密钥'))
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError(tr('ui.18261fc65fd5', '远程 API 必须使用 HTTPS；本机接口可使用 HTTP'))
    return value.rstrip("/")


def key(settings):
    value = settings.get("api_key", "") or os.environ.get(settings.get("key_env", ""), "")
    if not value:
        raise ValueError(tr('ui.d0712012d997', '请填写 API Key，或设置指定的密钥环境变量'))
    return value


def request_audio(url, *, headers=None, payload=None, body=None):
    with requests.Session() as client:
        client.trust_env = False  # local AI must not accidentally use a global proxy
        response = client.post(http_url(url), headers=headers, json=payload, data=body,
                               timeout=(10, 600), allow_redirects=False)
    if not response.ok or 300 <= response.status_code < 400:
        # Do not echo the response body: third parties can include credentials in errors.
        raise ValueError(tr('ui.63b0c60ab981', '语音服务请求失败：HTTP {value0}。请检查接口、权限和配额。', value0=response.status_code))
    return response.content


def gpt_sovits(settings, text):
    from .managed_api import api
    return api.synthesize(settings, text)


def compatible(settings, text):
    if not settings.get("model") or not settings.get("voice"):
        raise ValueError(tr('ui.b734caa172af', '请填写服务提供方支持的模型和音色 ID'))
    payload = dict(model=settings["model"], voice=settings["voice"], input=text, response_format="wav",
                   speed=float(settings.get("speed", 1)))
    headers = {"Content-Type": "application/json"}
    if settings.get("api_key") or os.environ.get(settings.get("key_env", ""), ""):
        headers["Authorization"] = "Bearer " + key(settings)
    return request_audio(settings["url"], headers=headers, payload=payload)


def azure(settings, text):
    if not settings.get("voice") or not settings.get("locale"):
        raise ValueError(tr('ui.61ae7e7aabed', '请填写 Azure 音色和语言区域'))
    speed = float(settings.get("speed", 1))
    if not .5 <= speed <= 2:
        raise ValueError(tr('ui.bd5144088a2f', 'Azure 语速需在 0.5–2.0 之间'))
    ssml = (f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang={quoteattr(settings["locale"])}>'
            f'<voice name={quoteattr(settings["voice"])}><prosody rate="{(speed - 1) * 100:+.0f}%">'
            f'{escape(text)}</prosody></voice></speak>')
    return request_audio(settings["url"], headers={"Ocp-Apim-Subscription-Key": key(settings),
                         "Content-Type": "application/ssml+xml", "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
                         "User-Agent": "WallpaperCompanion"}, body=ssml.encode("utf-8"))


def remote_check(settings):
    http_url(settings["url"])
    return tr('ui.24e44bbb169e', '接口地址格式有效。云端鉴权与音色支持请通过生成一条短台词验证（会产生服务调用）。')


def builtin_providers():
    from .services import api_status, start_api
    secret_fields = [Field("api_key", "API Key", "password", "", tr('ui.7e681106ceb7', '保存时写入 Windows 凭据管理器，不写入配置文件')),
                     Field("key_env", tr('ui.0813f932ba69', '密钥环境变量名'), default="", help=tr('ui.4f4def9fb031', '可选，例如 AZURE_SPEECH_KEY'))]
    return [
        SpeechProvider("gpt_sovits", tr('ui.3ea5dc8118a5', '本地 GPT-SoVITS'), [
            Field("url", tr('ui.d94c3fb87662', 'API 地址'), default="http://127.0.0.1:9880"),
            Field("project", tr('ui.f1e172d4d67b', '项目目录'), "directory"), Field("python", tr('ui.f35c1d9cbeb7', 'Python 可执行文件（可选）'), "file"),
            Field("gpt_weights", tr('ui.edfdaa8ce998', 'GPT 模型 (.ckpt)'), "gpt_model", help=tr('ui.0fa209226e3e', '与 SoVITS 配套选择；两项同时留空可沿用当前模型')),
            Field("sovits_weights", tr('ui.a0223161ecb1', 'SoVITS 模型 (.pth)'), "sovits_model", help=tr('ui.b1c40b989aa8', '扫描后选择或自行浏览，只有生成时才加载')),
            Field("reference", tr('ui.244b7fda3072', '参考音频'), "file"), Field("prompt", tr('ui.f0e150cc9240', '参考音频原文'), "multiline"),
            Field("text_lang", tr('ui.9fad67a039dc', '目标语言代码'), default="zh"), Field("prompt_lang", tr('ui.637464035bdb', '参考语言代码'), default="zh"),
            Field("speed", tr('ui.cd97a36868f3', '语速'), "float", 1.0),
            Field("allow_external_model_switch", tr('ui.12eb30b1fef3', '允许切换外部 API 模型（会影响其他使用者）'), "bool", False)], gpt_sovits, api_status,
            tr('ui.073674cbc018', '扫描/保存不启动 API。生成时自动启动，也可手动启动/关闭自建 API；自建服务使用独立推理配置并随声伴退出。外部服务切换需显式勾选允许。'), start_api),
        SpeechProvider("azure_speech", tr('ui.62d00ead806e', '微软 Azure Speech'), [
            Field("url", tr('ui.673ead0c0d1c', '完整合成接口地址'), default="", help=tr('ui.3db3ad9a2a8d', '例如 https://eastasia.tts.speech.microsoft.com/cognitiveservices/v1')),
            *secret_fields, Field("voice", tr('ui.f32bd1f97d29', '音色 ID'), default="zh-CN-XiaoxiaoNeural"),
            Field("locale", tr('ui.1dc2f5bc8558', '语言区域'), default="zh-CN"), Field("speed", tr('ui.cd97a36868f3', '语速'), "float", 1.0)],
            azure, remote_check, tr('ui.dd6ff001ef2a', '台词将发送给你配置的 Azure Speech 服务，按该服务账户计费。')),
        SpeechProvider("openai_compatible", tr('ui.e3a83704d771', 'OpenAI 兼容 TTS'), [
            Field("url", tr('ui.673ead0c0d1c', '完整合成接口地址'), default="", help=tr('ui.636fbf7767ec', '填写服务提供方的完整 /audio/speech 地址')),
            *secret_fields, Field("model", tr('ui.8b84338de394', '模型 ID')), Field("voice", tr('ui.f32bd1f97d29', '音色 ID')), Field("speed", tr('ui.cd97a36868f3', '语速'), "float", 1.0)],
            compatible, remote_check, tr('ui.ac1c1a34a143', '适用于返回 WAV 的 /audio/speech 兼容服务。模型和音色由服务方决定，不内置固定模型。'))]
