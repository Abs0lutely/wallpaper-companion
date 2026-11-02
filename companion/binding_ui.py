"""Explicit shared-JSON preview, guarded switching, and safe detach."""
from PySide6.QtWidgets import QMessageBox
from .file_dialogs import FileDialogs
from .i18n import tr
from .dialogue_binding import preview_binding,switch_binding


class DialogueBindingMixin:
    def browse_dialogue_file(self):
        path,_=FileDialogs.getOpenFileName(self.dialogue_file,tr("binding.browse","选择共用台词 JSON"),self.accepted_dialogue_file,"JSON (*.json)")
        if path:self.dialogue_file.setText(path);self.change_dialogue_file()

    def detach_dialogue_file(self):
        self.dialogue_file.setText("");self.change_dialogue_file()

    def change_dialogue_file(self):
        value=self.dialogue_file.text().strip()
        old=getattr(self,"accepted_dialogue_file","")
        if value==old:return True
        self.dialogue_file.setText(old)
        if not self.editing_id:
            self.report_error(tr("binding.select","请先选择配置。"));return False
        try:
            path,entries,stamp=preview_binding(self.store,value,self.collect_dialogues())
            message=tr("binding.preview","将切换台词关联至 {path}，共 {count} 条。已有文件只读取，不覆盖；新文件使用当前台词。取消将保留原关联。",path=str(path) if path else tr("binding.embedded","本配置内嵌台词"),count=len(entries))
            dialog=QMessageBox(QMessageBox.Icon.Question,tr("binding.confirm","确认切换台词文件"),message,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,self)
            dialog.setDetailedText("\n".join(e["category"]+": "+e["text"] for e in entries));dialog.setDefaultButton(QMessageBox.StandardButton.No)
            if dialog.exec()!=QMessageBox.StandardButton.Yes:return False
            if not self.autosave.flush():return False
            before=__import__('copy').deepcopy(self.store.config)
            files={path:None} if path and stamp is None else {}
            switch_binding(self.store,self.editing_id,value,self.collect_dialogues(),stamp)
            self.refresh_profiles(self.editing_id)
            self.autosave.baseline=self.autosave.forms()
            self.autosave.record(before,files,tr("binding.saved","台词关联已更新；未覆盖目标文件，可撤销。"))
            return True
        except Exception as exc:
            self.report_error(str(exc));return False
