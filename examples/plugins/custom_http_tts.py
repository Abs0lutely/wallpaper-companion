"""Example third-party HTTP service returning PCM WAV, no host UI edits needed."""
from companion.extensions import Field, SpeechProvider
from companion.providers import remote_check, request_audio, key

API_VERSION = 1


def synthesize(settings, text):
    # Adapt this payload to your vendor's protocol. Return complete WAV bytes.
    return request_audio(settings["url"], headers={"Authorization": "Bearer " + key(settings)},
                         payload={"text": text, "speaker": settings["speaker"], "format": "wav"})


def register(registry):
    registry.register_speech(SpeechProvider(
        id="custom_http_tts", title="第三方 HTTP TTS 示例",
        fields=[Field("url", "完整 API 地址"), Field("api_key", "API Key", "password"),
                Field("key_env", "密钥环境变量名"), Field("speaker", "音色 ID")],
        synthesize=synthesize, check=remote_check,
        description="示例协议为 text/speaker/format JSON，请按服务方文档调整扩展中的 payload。"))
