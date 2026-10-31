"""Lazy, owned GPT-SoVITS process lifecycle; never terminate an external server."""
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import psutil
import requests

from .core import DATA, writable_path
from .external import popen_external


class LocalAPI:
    def __init__(self, data_dir=DATA):
        self.data_dir = Path(data_dir)
        self.lock = threading.Lock()
        self.closed = threading.Event()
        self.process = None
        self.url = None
        self.generation_lock = threading.Lock()
        self.loaded_models = None
        self.runtime_config = None

    def owns_service(self):
        with self.lock:
            return self.process is not None and self.process.poll() is None

    def start(self, settings, protected=()):
        """Explicit user action; never switch or stop an externally owned API."""
        from .services import local_url
        from .sovits_config import model_key
        with self.generation_lock:
            url = local_url(settings["url"])
            selected = model_key(settings)
            if self.owns_service() and (self.url != url or selected and self.loaded_models != (url, selected, "owned")):
                raise ValueError("自建 API 已运行；更换端口或模型前，请先关闭自建 API，再启动。")
            self.ensure(settings, protected)
            return (f"自建 API 已就绪：{url}；可生成语音，关闭按钮仅管理此自建进程。" if self.owns_service() else
                    f"已连接外部 API：{url}；未启动新进程，也不会关闭或切换外部服务。")

    def close_owned(self):
        if not self.generation_lock.acquire(blocking=False):
            raise RuntimeError("正在加载模型或生成语音，请等待当前任务完成后关闭 API。")
        try:
            owned = self.owns_service()
            self.stop()
            return "自建 API 已关闭并回收进程；下次可重新启动。" if owned else "没有本程序启动的 API 可关闭；外部服务请在原程序中管理。"
        finally:
            self.generation_lock.release()

    def ensure(self, settings, protected=(), timeout=180):
        from .services import api_status, local_url
        from .sovits_config import model_key, runtime_config
        url = local_url(settings["url"])
        selected = model_key(settings)
        if self.closed.is_set():
            raise RuntimeError("程序正在退出，已取消语音生成")
        try:
            message = api_status(settings)
            if self.closed.is_set():
                raise RuntimeError("程序正在退出，已取消语音生成")
            return message
        except requests.RequestException:
            pass
        # An incompatible service on the port is an error, not a reason to spawn.
        with self.lock:
            if self.closed.is_set():
                raise RuntimeError("程序正在退出，已取消启动 API")
            if self.process is not None and self.process.poll() is None:
                if self.url != url:
                    raise ValueError("已有本程序启动的 API；请先退出并重启声伴，再更换接口端口")
            else:
                project = Path(settings.get("project", ""))
                python = Path(settings["python"]) if settings.get("python") else project / "runtime/python.exe"
                script = project / "api_v2.py"
                if not python.is_file() or not script.is_file():
                    raise ValueError("未找到 GPT-SoVITS 的 Python 或 api_v2.py；请在生成页配置项目和 Python 路径")
                parsed = urlparse(url)
                logpath = writable_path(self.data_dir / "sovits-api.log", protected)
                logpath.parent.mkdir(parents=True, exist_ok=True)
                self.runtime_config = runtime_config(settings, self.data_dir, protected)
                command = [str(python.resolve()), "-u", str(script.resolve()), "-a", parsed.hostname, "-p", str(parsed.port or 80)]
                if self.runtime_config:
                    command.extend(["-c", str(self.runtime_config)])
                try:
                    with logpath.open("ab") as log:
                        self.process = popen_external(command, cwd=project.resolve(), stdout=log, stderr=log,
                            stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                except Exception:
                    if self.runtime_config:
                        self.runtime_config.unlink(missing_ok=True)
                        self.runtime_config = None
                    raise
                self.url = url
                self.loaded_models = (url, selected, "owned") if selected else None
        deadline = time.monotonic() + timeout
        while not self.closed.is_set():
            process = self.process
            if process is None or process.poll() is not None:
                self.stop()
                raise RuntimeError("API 已退出；请查看数据目录中的 sovits-api.log")
            try:
                message = api_status(settings)
                if not self.closed.is_set():
                    return message
            except requests.RequestException:
                pass
            if time.monotonic() >= deadline:
                self.stop()
                raise TimeoutError("API 加载超时，已停止本程序启动的进程；请检查 sovits-api.log 后重试")
            self.closed.wait(.5)
        raise RuntimeError("语音生成已取消")

    def synthesize(self, settings, text):
        from .characters import project_file, validate_character
        from .providers import request_audio
        from .services import local_url, session
        from .sovits_config import model_key
        import uuid
        # Model load + request are serialized, so another local task cannot
        # change the selected voice between the two operations.
        with self.generation_lock:
            validate_character(settings)
            selected = model_key(settings)
            url = local_url(settings["url"])
            if selected and self.process is not None and self.process.poll() is None and self.url == url:
                if self.loaded_models != (url, selected, "owned"):
                    # Cross-version models/vocoders can retain large GPU caches.
                    # Only our own API is restarted, and only at generation time.
                    self.stop()
            self.ensure(settings, settings.get("_protected_dirs", ()))
            owned = self.process is not None and self.process.poll() is None and self.url == url
            if selected:
                if not owned and settings.get("allow_external_model_switch") is not True:
                    raise ValueError("该 API 已由其他软件启动。若要切换它的模型，请勾选允许切换外部 API 模型，或改用空闲端口让声伴独立启动。")
                key = (url, selected, "owned" if owned else settings.get("_tts_batch_id") or uuid.uuid4().hex)
                if self.loaded_models != key:
                    self.loaded_models = None
                    try:
                        with session() as client:
                            for endpoint, weight in (("/set_sovits_weights", selected[1][0]), ("/set_gpt_weights", selected[0][0])):
                                if self.closed.is_set():
                                    raise RuntimeError("语音生成已取消")
                                response = client.get(url + endpoint, params={"weights_path": weight}, timeout=(5, 180), allow_redirects=False)
                                if not response.ok or response.json().get("message") != "success":
                                    raise ValueError("模型加载失败，请核对配套权重及 API 日志；未发送合成请求")
                        if self.closed.is_set():
                            raise RuntimeError("语音生成已取消")
                        self.loaded_models = key
                    except Exception:
                        if owned:
                            self.stop()
                        raise
            if self.closed.is_set():
                raise RuntimeError("语音生成已取消")
            payload = dict(text=text, text_lang=settings.get("text_lang", "zh"),
                ref_audio_path=str(project_file(settings, "reference")), prompt_text=settings["prompt"],
                prompt_lang=settings.get("prompt_lang", "zh"), speed_factor=float(settings.get("speed", 1)),
                media_type="wav", streaming_mode=False, text_split_method="cut5", batch_size=1, seed=-1)
            return request_audio(url + "/tts", payload=payload)

    def stop(self):
        with self.lock:
            process, self.process = self.process, None
            self.url = None
            self.loaded_models = None
            config = self.runtime_config
            if process is None or process.poll() is not None:
                if config:
                    config.unlink(missing_ok=True)
                    self.runtime_config = None
                return
            try:
                parent = psutil.Process(process.pid)
                children = parent.children(recursive=True)
                for child in reversed(children):
                    try:
                        child.terminate()
                    except psutil.NoSuchProcess:
                        pass
                parent.terminate()
                _, alive = psutil.wait_procs([*children, parent], timeout=2)
                for item in alive:
                    try:
                        item.kill()
                    except psutil.NoSuchProcess:
                        pass
                psutil.wait_procs(alive, timeout=2)
                process.wait(timeout=2)
            except psutil.NoSuchProcess:
                process.wait(timeout=2)
            if config:
                config.unlink(missing_ok=True)
                self.runtime_config = None

    def shutdown(self):
        # Mark first, so a racing generation cannot launch a replacement process.
        self.closed.set()
        self.stop()


api = LocalAPI()
