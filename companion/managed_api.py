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

    def ensure(self, settings, protected=(), timeout=180):
        from .services import api_status, local_url
        url = local_url(settings["url"])
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
                with logpath.open("ab") as log:
                    self.process = popen_external(
                        [str(python.resolve()), "-u", str(script.resolve()), "-a", parsed.hostname, "-p", str(parsed.port or 80)],
                        cwd=project.resolve(), stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self.url = url
        deadline = time.monotonic() + timeout
        while not self.closed.is_set():
            process = self.process
            if process is None or process.poll() is not None:
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

    def stop(self):
        with self.lock:
            process, self.process = self.process, None
            self.url = None
            if process is None or process.poll() is not None:
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

    def shutdown(self):
        # Mark first, so a racing generation cannot launch a replacement process.
        self.closed.set()
        self.stop()


api = LocalAPI()
