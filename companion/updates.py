"""Release discovery and bounded, cancellable downloads. No GUI or installation."""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

REPOSITORY = "Abs0lutely/wallpaper-companion"
RELEASES_URL = f"https://github.com/{REPOSITORY}/releases"
API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
MAX_DOWNLOAD = 512 * 1024**2
CHECK_INTERVAL = 24 * 60 * 60


class UpdateCancelled(Exception):
    pass


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r"v?\d+\.\d+\.\d+", value):
        raise ValueError("Invalid release version")
    return tuple(map(int, value.removeprefix("v").split(".")))


def current_version(app_dir):
    marker = Path(app_dir) / "app-version.txt"
    if marker.is_file():
        value = marker.read_text(encoding="utf-8").strip()
    else:
        import tomllib
        value = tomllib.loads((Path(app_dir) / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    version_tuple(value)
    return value


def trusted_url(url, *, asset=False):
    p = urlparse(url)
    prefix = f"/{REPOSITORY}/releases/" + ("download/" if asset else "tag/")
    if p.scheme != "https" or p.netloc != "github.com" or not p.path.startswith(prefix) or p.query or p.fragment:
        raise ValueError("Unexpected release URL")
    return url


@dataclass(frozen=True)
class Release:
    version: str
    notes: str
    page: str
    name: str
    url: str
    size: int
    checksum_url: str
    digest: str = ""


def parse_release(payload, current, portable):
    if payload.get("draft") or payload.get("prerelease"):
        return None
    tag = payload.get("tag_name", "")
    if version_tuple(tag) <= version_tuple(current):
        return None
    version = tag.removeprefix("v")
    suffix = "portable.zip" if portable else "setup.exe"
    name = f"WallpaperCompanion-{version}-windows-x64-{suffix}"
    assets = payload.get("assets", [])
    matches = [a for a in assets if a.get("name") == name]
    sums = [a for a in assets if a.get("name") == "SHA256SUMS.txt"]
    if len(matches) != 1 or len(sums) != 1:
        raise ValueError("Release is missing unique package or checksum assets")
    item, checksum = matches[0], sums[0]
    size = item.get("size")
    if type(size) is not int or not 0 < size <= MAX_DOWNLOAD:
        raise ValueError("Release package size is invalid")
    for asset in (item, checksum):
        trusted_url(asset.get("browser_download_url", ""), asset=True)
        if urlparse(asset["browser_download_url"]).path != f"/{REPOSITORY}/releases/download/{tag}/{asset['name']}":
            raise ValueError("Asset does not belong to the selected release")
    digest = item.get("digest") or ""
    if digest and not re.fullmatch(r"sha256:[a-fA-F0-9]{64}", digest):
        raise ValueError("Invalid asset digest")
    return Release(version, str(payload.get("body") or "")[:100_000],
                   trusted_url(payload.get("html_url", "")), name, item["browser_download_url"],
                   size, checksum["browser_download_url"], digest.removeprefix("sha256:").lower())


def _check_cancel(cancel):
    if cancel.is_set():
        raise UpdateCancelled()


class ReleaseClient:
    def __init__(self, session=None):
        self.session = session or requests.Session()
        self.session.headers.update({"Accept": "application/vnd.github+json", "User-Agent": "WallpaperCompanion-Updater"})

    def small_get(self, url, cancel, limit):
        _check_cancel(cancel)
        chunks = []
        total = 0
        with self.session.get(url, timeout=(5, 15), stream=True) as response:
            response.raise_for_status()
            for chunk in response.iter_content(64 * 1024):
                _check_cancel(cancel)
                total += len(chunk)
                if total > limit:
                    raise ValueError("Update response is too large")
                chunks.append(chunk)
        return b"".join(chunks)

    def latest(self, current, portable, cancel):
        return parse_release(json.loads(self.small_get(API_URL, cancel, 2 * 1024**2)), current, portable)

    def download(self, release, directory, cancel, progress=lambda done, total: None):
        checksums = self.small_get(release.checksum_url, cancel, 64 * 1024).decode("utf-8-sig")
        matches = []
        for line in checksums.splitlines():
            match = re.fullmatch(r"([a-fA-F0-9]{64})\s+\*?(.+)", line.strip())
            if match and match[2] == release.name:
                matches.append(match[1].lower())
        if len(matches) != 1 or release.digest and release.digest != matches[0]:
            raise ValueError("Package checksum is missing, duplicated or inconsistent")
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / release.name
        partial = destination.with_suffix(destination.suffix + ".part")
        checksum = hashlib.sha256()
        count = 0
        try:
            with self.session.get(release.url, timeout=(5, 15), stream=True) as response:
                response.raise_for_status()
                with partial.open("wb") as output:
                    for chunk in response.iter_content(256 * 1024):
                        _check_cancel(cancel)
                        count += len(chunk)
                        if count > release.size:
                            raise ValueError("Downloaded package exceeds release size")
                        output.write(chunk)
                        checksum.update(chunk)
                        progress(count, release.size)
            _check_cancel(cancel)
            if count != release.size or checksum.hexdigest() != matches[0]:
                raise ValueError("Package size or SHA256 verification failed")
            partial.replace(destination)
            return destination, matches[0]
        finally:
            partial.unlink(missing_ok=True)


def read_state(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def write_state(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def check_due(state, now=None):
    now = time.time() if now is None else now
    stamp = state.get("last_check", 0)
    return type(stamp) not in (int, float) or stamp <= 0 or stamp > now or now - stamp >= CHECK_INTERVAL
