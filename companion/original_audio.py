"""Read-only evidence about original wallpaper audio, never a live audibility claim."""
from .i18n import tr
import json
import re
import shutil
import struct
import subprocess
from pathlib import Path
from .external import run_external

AUDIO_SUFFIXES = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".wma", ".opus"}
VIDEO_SUFFIXES = {".mp4", ".webm", ".mkv", ".avi", ".wmv", ".mov", ".m4v"}


def package_entries(path):
    """Read PKGV directory only (format documented by RePKG); never extract assets."""
    with Path(path).open("rb") as stream:
        def integer():
            value = stream.read(4)
            if len(value) != 4:
                raise ValueError(tr('ui.ef5f3fb275d7', 'PKG 索引被截断'))
            return struct.unpack("<I", value)[0]
        def string(limit):
            size = integer()
            if not 0 < size <= limit:
                raise ValueError(tr('ui.79792fe58688', 'PKG 字段长度不支持'))
            value = stream.read(size)
            if len(value) != size:
                raise ValueError(tr('ui.ef5f3fb275d7', 'PKG 索引被截断'))
            return value.decode("utf-8")
        magic = string(32)
        if magic not in {"PKGV0001", "PKGV0010", "PKGV0015", "PKGV0020"}:
            raise ValueError(tr('ui.8ae40105c709', '未知 PKG 版本'))
        count = integer()
        if count > 100000:
            raise ValueError(tr('ui.59b03ef510b2', 'PKG 索引过大'))
        names = []
        for _ in range(count):
            names.append(string(1024))
            integer()  # offset
            integer()  # length
            if stream.tell() > 16 * 1024 * 1024:
                raise ValueError(tr('ui.59b03ef510b2', 'PKG 索引过大'))
        return names


def detect_original_audio(config, wallpaper):
    path = Path(wallpaper) if wallpaper else None
    if path is None or not path.is_file():
        return dict(state="unknown", detail=tr('ui.62d2eadd1642', '无有效壁纸文件，无法检测'))
    suffix = path.suffix.casefold()
    if suffix in AUDIO_SUFFIXES:
        return dict(state="yes", detail=tr('ui.5aaa30243a4b', '壁纸入口本身是音频文件'))
    if suffix in VIDEO_SUFFIXES:
        probe = config.get("ffprobe", "") or shutil.which("ffprobe")
        if not probe:
            return dict(state="unknown", detail=tr('ui.e789e2c18b8d', '未找到 ffprobe；可在运行设置中选择，或手动覆盖检测结果'))
        try:
            result = run_external([str(probe), "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "json", str(path)],
                                    capture_output=True, timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode:
                raise ValueError(tr('ui.825776ae193c', 'ffprobe 未能读取视频音轨'))
            streams = json.loads(result.stdout.decode("utf-8"))
            if "streams" not in streams:
                raise ValueError(tr('ui.cdf48596bb87', 'ffprobe 没有返回音轨信息'))
            found = bool(streams["streams"])
            return dict(state="yes" if found else "no", detail=tr('ui.637f76cb8ac5', '视频含音轨（可能是 BGM 或其他声音）') if found else tr('ui.3d4c351553ca', '视频没有音轨'))
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            return dict(state="unknown", detail=str(exc))
    if suffix == ".pkg":
        try:
            names = package_entries(path)
            if any(Path(name).suffix.casefold() in AUDIO_SUFFIXES for name in names):
                return dict(state="possible", detail=tr('ui.b31e356c90ad', '场景包索引含音频素材，不能确认是否正在播放'))
            return dict(state="unknown", detail=tr('ui.842687e4ccc5', '包内未发现独立音频文件；仍可能引用共享素材或视频声音'))
        except (OSError, ValueError, UnicodeError) as exc:
            return dict(state="unknown", detail=tr('ui.72c80212903e', '场景包检测未完成：') + str(exc))
    try:
        # Positive evidence only. WebAudio/scripts can play sounds dynamically.
        for file in path.parent.rglob("*"):
            if file.is_file() and file.suffix.casefold() in AUDIO_SUFFIXES:
                return dict(state="possible", detail=tr('ui.1f375fb772f3', '壁纸目录含音频素材，不能确认是否启用'))
        if path.suffix.casefold() in {".html", ".htm", ".json"} and path.stat().st_size < 2 * 1024 * 1024:
            text = path.read_text(encoding="utf-8", errors="replace")
            if re.search(r'<audio\b|new\s+Audio\s*\(|AudioContext|"sound"\s*:', text, re.I):
                return dict(state="possible", detail=tr('ui.e72d2a8d5b42', '入口中发现声音代码或声音层'))
    except OSError as exc:
        return dict(state="unknown", detail=str(exc))
    return dict(state="unknown", detail=tr('ui.32a85a689dac', '没有直接声音证据，无法排除脚本或外部声音'))


def should_block_bgm(profile, detection):
    policy = profile.get("original_audio_policy", "safe")
    state = profile.get("original_audio_override", "auto")
    state = detection.get("state", "unknown") if state == "auto" else state
    if policy == "allow":
        return False
    if policy == "detected":
        return state in {"yes", "possible"}
    return state != "no"
