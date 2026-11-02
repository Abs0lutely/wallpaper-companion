"""Standalone sound profiles without Wallpaper Engine discovery/polling."""
import copy
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QPushButton
from .i18n import tr


class ModeMixin:
    def is_standalone(self):return self.store.config.get("run_mode","wallpaper_engine")=="standalone"

    def change_run_mode(self):
        target=self.run_mode.currentData()
        if target==self.store.config.get("run_mode","wallpaper_engine"):return
        if not hasattr(self,"autosave"):return
        if not self.autosave.flush():self.load_settings();return
        before=copy.deepcopy(self.store.config)
        try:
            self.store.config["run_mode"]=target
            if target=="standalone" and not self.store.profile(self.store.config.get("standalone_profile")):
                selected=self.store.profile(self.editing_id)
                if not selected:
                    from .core import new_profile
                    selected=new_profile(tr("mode.default_profile","我的声音空间"))
                    self.store.config["profiles"].append(selected)
                self.store.config["standalone_profile"]=selected["id"]
            self.store.save()
            self.apply_run_mode()
            selected=self.store.config.get("standalone_profile") if self.is_standalone() else (self.store.config.get("manual_profile") or self.editing_id)
            self.refresh_profiles(selected)
            self.activate_profile(force=True)
            self.autosave.baseline=self.autosave.forms()
            self.autosave.record(before,{},tr("mode.saved","运行模式已切换；原有壁纸绑定和资源保留，可撤销。"))
            if not self.is_standalone():self.detect()
        except Exception as exc:
            self.store.config=before;self.load_settings();self.report_error(str(exc))

    def select_standalone_profile(self,identifier):
        if self.store.config.get("standalone_profile")==identifier:return
        previous=self.store.config.get("standalone_profile","")
        self.store.config["standalone_profile"]=identifier
        try:self.store.save()
        except Exception as exc:
            self.store.config["standalone_profile"]=previous
            self.report_error(str(exc));self.refresh_profiles(previous);return
        self.activate_profile(force=True)

    def apply_run_mode(self):
        standalone=self.is_standalone()
        if getattr(self,"applied_mode",None)!=standalone:
            self.mode_epoch=getattr(self,"mode_epoch",0)+1
            self.query_busy=False
            self.original_audio_request+=1
        self.applied_mode=standalone
        for b in self.findChildren(QPushButton):
            if b.property("requiresWE"):b.setVisible(not standalone)
        self.manual.setVisible(not standalone)
        self.detect_button.setVisible(not standalone)
        self.navigation[4].setVisible(not standalone)
        self.scan_bind_action.setVisible(not standalone)
        self.wallpaper_path.setVisible(not standalone)
        self.wallpaper_field_label.setVisible(not standalone)
        self.original_audio_card.setVisible(not standalone)
        self.profile_list_heading.setText(tr("mode.profiles","声音配置 · 可多选管理") if standalone else tr('ui.a154bc5ed5be','壁纸配置 · 可多选管理'))
        self.profile_identity_title.setText(tr("mode.sound_profile","声音配置") if standalone else tr('ui.180dafedd38c','壁纸与配置'))
        self.mode_notice.setText(tr("mode.standalone_help","独立声音伴随：无需 Wallpaper Engine，选择声音配置即可使用。") if standalone else tr("mode.we_help","跟随 WE 壁纸；未安装 WE 时可选择独立声音伴随。"))
        if not standalone and not self.store.config.get("we_dir"):
            self.mode_notice.setText(tr("mode.recommend","未发现 WE 安装目录，推荐选择独立声音伴随；不需要安装 WE。"))
        if standalone:
            self.current_display_text=tr("mode.standalone","独立声音伴随")
            self.current_display_tooltip=""
            if self.tabs.currentIndex()==4:self.tabs.setCurrentIndex(0)
        else:
            self.current_display_text=tr('ui.e8b970bc3e05','正在检测…')
        self.render_current_wallpaper()
        if hasattr(self,"poll"):
            if standalone:self.poll.stop()
            elif not self.poll.isActive():self.poll.start(self.store.config.get("poll_seconds",4)*1000)
        self.refresh_shell()
