"""Read-only distributed defaults: real WAV playback, fallback and file protection."""
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from companion.bundled_audio import validate_bundled_manifest,validate_starter_pack
from companion.operation_pack import require_pack
from companion.core import ROOT,Store,new_profile,candidates,writable_path
from companion.ui import Window
import shiboken6

app=QApplication([]); app.setQuitOnLastWindowClosed(False)
out=ROOT/"output"; out.mkdir(exist_ok=True); report={}; errors=[]
with tempfile.TemporaryDirectory(dir=out) as tmp, patch("companion.bundled_audio.bundled_root",return_value=ROOT/"examples/audio"), patch("companion.managed_api.api") as api:
    root=Path(tmp); empty=root/"empty-voice"; empty.mkdir()
    p=new_profile("新安装体验"); p.update(voice_dir=str(empty),voice_volume=1,bgm_enabled=False,desktop_only=False,fullscreen_mute=False)
    store=Store(root/"data/config.json"); store.config.update(profiles=[p],manual_profile=p["id"],operation_voice_enabled=False,we_dir="",workshop_dir=""); store.save()
    w=Window(store,hooks=False); w.report_error=errors.append; w.show(); w.activate_profile(force=True)
    def wait(predicate):
        end=time.monotonic()+8
        while not predicate():
            if time.monotonic()>=end:
                import faulthandler
                faulthandler.dump_traceback()
                print("AUDIO STATE",w.audio_library_busy,w.audio_refresh_pending,w.audio_scope.currentData(),w.audio_library_status.text(),errors,flush=True)
                print("SOURCES",w.audio_sources,flush=True)
                raise AssertionError("bundled audio timed out")
            QTest.qWait(20)
            time.sleep(.002)  # Yield the GIL so filesystem worker callbacks can finish.
    try:
        manifest=validate_bundled_manifest()
        report["all_180_assets_match_checksums"] = len(manifest["files"])==180 and len(validate_starter_pack()["files"])==38 and not any(manifest["missing"].values())
        operation=require_pack(ROOT/"examples/audio/operation-voice")
        report["all_52_operation_variants_complete"] = operation["complete"] and len(operation["found"])==52 and not operation["missing"]
        files=candidates(p,dict(source="",keyword=""))
        report["new_profile_uses_factory_samples_without_copying_user_data"] = len(files)==38 and not list(empty.iterdir())
        p["demo_language"]="ja-JP"
        japanese=candidates(p,{"source":""})
        report["japanese_demo_selectable_without_mixing_languages"]=len(japanese)==38 and all("starter-voice-ja-JP" in str(f) for f in japanese)
        p["demo_language"]="zh-CN"

        w.input_event("key",p["rules"][0]["id"])
        wait(lambda:w.audio.voice.playbackState()==QMediaPlayer.PlaybackState.PlayingState)
        report["wallpaper_rule_actually_plays_bundled_sample"] = "starter-voice" in w.audio.voice.source().toLocalFile()
        w.audio.voice.stop(); w.audio.voice.setSource(QUrl())
        returning=candidates(p,dict(source="返回桌面",keyword=""))
        idle=candidates(p,dict(source="闲置陪伴",keyword=""))
        report["new_model_named_return_and_idle_categories_available"] = len(returning)==6 and len(idle)==6 and all("-神里绫华_EN" in file.stem for file in returning+idle)
        w.audio.play_voice(returning[0])
        wait(lambda:w.audio.voice.playbackState()==QMediaPlayer.PlaybackState.PlayingState)
        report["new_model_named_clip_actually_plays"] = w.audio.voice.source().toLocalFile().endswith(returning[0].name)
        w.audio.voice.stop(); w.audio.voice.setSource(QUrl())
        p["use_bundled_demo"]=False
        report["fallback_can_be_disabled"] = not candidates(p,dict(source="",keyword=""))
        p["use_bundled_demo"]=True
        local=empty/"user.wav"; local.write_bytes(files[0].read_bytes())
        report["user_audio_takes_priority"] = candidates(p,dict(source="",keyword=""))==[local]
        opfolder=empty/"操作·保存"; opfolder.mkdir(); (opfolder/"不应进入壁纸随机播放.wav").write_bytes(local.read_bytes())
        report["generic_wallpaper_rules_exclude_operation_clips"] = candidates(p,dict(source="",keyword=""))==[local]
        wait(lambda:not w.operation_voices.scanning)
        store.config["operation_voice_enabled"]=True; w.operation_voices.refresh(); wait(lambda:not w.operation_voices.scanning)
        w.operation_voices.request("save")
        wait(lambda:w.audio.voice.playbackState()==QMediaPlayer.PlaybackState.PlayingState)
        report["factory_operation_clip_actually_plays"] = "operation-voice" in w.audio.voice.source().toLocalFile()
        w.audio.voice.stop(); w.audio.voice.setSource(QUrl()); store.config["operation_voice_enabled"]=False
        w.tabs.setCurrentIndex(6); wait(lambda:not w.audio_library_busy)
        w.audio_scope.setCurrentIndex(w.audio_scope.findData("bundled:voice")); wait(lambda:not w.audio_library_busy)
        report["factory_inventory_is_read_only_and_not_a_copy_target"] = len(w.audio_records)==180 and all(r["read_only"] for r in w.audio_records) and w.audio_target.findData("bundled:voice")==-1
        w.audio_table.selectRow(0); w.recycle_library_audio()
        report["factory_delete_is_rejected"] = len(errors)==1 and "只读" in errors.pop()
        try:
            writable_path(files[0],store.protected()); protected=False
        except ValueError: protected=True
        report["all_user_writes_protect_factory_assets"] = protected
        report["no_api_work_or_unexpected_errors"] = not api.start.called and not api.ensure.called and not api.synthesize.called and not errors
    finally:
        w.cleanup(); shiboken6.delete(w)
(out/"smoke-bundled-audio.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report)); sys.exit(0 if all(report.values()) else 1)
