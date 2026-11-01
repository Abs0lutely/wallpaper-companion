"""Validate (default) or copy only the 52 manifest clips into distribution assets."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from companion.operation_pack import require_pack, validate_pack
from companion.core import writable_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="按分类生成的音频根目录，只读取清单内 WAV")
    parser.add_argument("--apply", action="store_true", help="全部齐备后才复制；不覆盖已有不同内容")
    args = parser.parse_args()
    result = validate_pack(args.source)
    if args.apply:
        require_pack(args.source)
        target = writable_path(ROOT / "examples/audio/operation-voice")
        paths = [(args.source / name, writable_path(target / name)) for name in result["found"]]
        for src, dst in paths:
            if not dst.is_relative_to(target) or dst.exists() and dst.read_bytes() != src.read_bytes():
                raise ValueError("目标已有不同内容或路径异常，请先人工审阅：" + str(dst))
        for src, dst in paths:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                shutil.copy2(src, dst)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
