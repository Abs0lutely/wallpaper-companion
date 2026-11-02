"""Create a source-only GitHub handoff without local config, audio, environments or keys."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOP = ["main.py", "README.md", "README.en.md", "USER_GUIDE.md", "USER_GUIDE.en.md", "USAGE.md", "USAGE.en.md", "COMPANION_PACKS.md", "COMPANION_PACKS.en.md", "AGENTS.md", "EXTENSIONS.md", "THIRD_PARTY.md", "LICENSE", "requirements.txt",
       "pyproject.toml", ".gitignore", "setup.ps1", "setup.cmd", "start.cmd", "debug.cmd", "plugins/.gitkeep",
       "PROJECT_HANDOFF.md", "BUILDING.md", "RELEASE_GUIDE.md", "build_release.cmd", "requirements-build.txt", ".gitattributes"]
files = [ROOT / name for name in TOP]
for folder in ["companion", "examples", "tests", "scripts", ".github", "packaging"]:
    files.extend(p for p in (ROOT / folder).rglob("*") if p.is_file()
                 and "__pycache__" not in p.parts and p.suffix in {".py", ".yml", ".md", ".json", ".ps1", ".spec", ".iss", ".isl", ".txt"}
                 and p.name != "prepare_demo.py")
files = sorted(set(files))
dist = ROOT / "dist"
dist.mkdir(exist_ok=True)
archive = dist / "wallpaper-companion-source.zip"
manifest = {}
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        assert not any(part in {"data", "output", ".conda", ".venv", ".git"} for part in Path(relative).parts)
        bundle.write(path, "wallpaper-companion/" + relative)
        manifest[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
(dist / "source-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"archive": str(archive), "files": len(files), "bytes": archive.stat().st_size}, ensure_ascii=True))
