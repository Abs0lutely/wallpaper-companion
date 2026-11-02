"""Copy only approved Japanese default WAVs; keep source files and Chinese packs."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from companion.voice_locales import translated_lines
from companion.audio_names import matching_files
from companion.operation_pack import validate_wave
from companion.core import writable_path


def prepare(source, apply=False):
    source=Path(source).resolve();root=writable_path(ROOT/"examples/audio")
    manifest_path=root/"manifest.json"
    original=json.loads(manifest_path.read_text(encoding="utf-8"))
    files=[];copies=[]
    for kind in ("starter","operation"):
        pack=("starter-voice" if kind=="starter" else "operation-voice")+"-ja-JP"
        for e in translated_lines(kind,"ja-JP"):
            matches=matching_files(source/e["category"],e["text"])
            if not matches:matches=matching_files(source/e["category"].rsplit("·",1)[0],e["text"])
            if len(matches)!=1:raise ValueError("Expected one approved WAV: "+e["text"])
            src=matches[0]
            if src.suffix.lower()!=".wav" or src.is_symlink() or not src.resolve().is_relative_to(source):raise ValueError("Unsafe source")
            validate_wave(src)
            entry=dict(pack=pack,locale="ja-JP",category=e["category"],text=e["text"],filename=src.name,bytes=src.stat().st_size,sha256=hashlib.sha256(src.read_bytes()).hexdigest())
            target=writable_path(root/pack/e["category"]/src.name)
            if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()!=entry["sha256"]:raise ValueError("Existing asset differs: "+str(target))
            copies.append((src,target));files.append(entry)
    assert len(files)==90
    if apply:
        for src,target in copies:
            target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():shutil.copy2(src,target)
        original["files"]=[e for e in original["files"] if e["pack"] not in {"starter-voice-ja-JP","operation-voice-ja-JP"}]+files
        original["origin"]="User-authorized Chinese and Japanese default recordings"
        manifest_path.write_text(json.dumps(original,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        starter=dict(format="wallpaper-companion-starter-audio",version=1,locale="ja-JP",files=[{k:v for k,v in e.items() if k!="pack"} for e in files if e["pack"]=="starter-voice-ja-JP"],missing=[])
        (root/"starter-voice-ja-JP/manifest.json").write_text(json.dumps(starter,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return dict(files=len(files),bytes=sum(e["bytes"] for e in files),applied=apply)

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--source",type=Path,required=True);parser.add_argument("--apply",action="store_true")
    args=parser.parse_args();print(json.dumps(prepare(args.source,args.apply)))
