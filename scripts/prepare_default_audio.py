"""Stage only known default dialogue WAVs, preserving source and existing assets."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from companion.action_lines import operation_dialogues
from companion.dialogues import starter_dialogues
from companion.core import filename_for,writable_path
from companion.operation_pack import require_pack,validate_wave


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    source=args.source.resolve(); target=writable_path(ROOT/"examples/audio")
    require_pack(source)
    found=[]; missing={}
    for pack,entries in [("starter-voice",starter_dialogues()),("operation-voice",operation_dialogues())]:
        missing[pack]=[]
        for e in entries:
            relative=Path(e["category"])/filename_for(e["text"])
            file=source/relative
            if not file.is_file():
                missing[pack].append(relative.as_posix()); continue
            if file.is_symlink() or not file.resolve().is_relative_to(source):
                raise ValueError("源音频含链接或路径异常")
            info=validate_wave(file)
            found.append(dict(pack=pack,category=e["category"],text=e["text"],sha256=hashlib.sha256(file.read_bytes()).hexdigest(),bytes=file.stat().st_size,**info))
            destination=writable_path(target/pack/relative)
            if not destination.is_relative_to(target) or destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest()!=found[-1]["sha256"]:
                raise ValueError("分发目录已有不同内容，请先人工审阅："+str(relative))
    if not any(e["pack"]=="starter-voice" for e in found):
        raise ValueError("没有匹配的默认陪伴台词音频")
    manifest=dict(format="wallpaper-companion-bundled-audio",version=1,origin="用户提供并授权随程序分发的默认台词合成音频",files=found,missing=missing)
    if args.apply:
        for e in found:
            relative=Path(e["category"])/filename_for(e["text"])
            destination=target/e["pack"]/relative
            destination.parent.mkdir(parents=True,exist_ok=True)
            if not destination.exists(): shutil.copy2(source/relative,destination)
        (target/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
        starter=dict(format="wallpaper-companion-starter-audio",version=1,files=[{k:v for k,v in e.items() if k!="pack"} for e in found if e["pack"]=="starter-voice"],missing=missing["starter-voice"])
        (target/"starter-voice/manifest.json").write_text(json.dumps(starter,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(dict(files=len(found),bytes=sum(e["bytes"] for e in found),missing=missing,applied=args.apply),ensure_ascii=True,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
