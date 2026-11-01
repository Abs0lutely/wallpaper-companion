"""Read-only duplicate review before any synthesis or API process startup."""
from .i18n import tr
import copy
from PySide6.QtWidgets import QMessageBox
from .services import generate, generate_dialogue_entries, generation_duplicates


class GenerationReviewMixin:
    def begin_generation_review(self, lines, output, settings, provider, skip, entries=None):
        snapshot = dict(lines=list(lines), output=output, settings=copy.deepcopy(settings), provider=provider,
                        skip=skip, entries=copy.deepcopy(entries), protected=self.store.protected())
        self.tts_busy = True; self.update_api_controls()
        self.generation_cancel.clear()
        self.begin_generation(len(lines))
        self.tts_status.setText(tr('ui.ae7ef2ea5378', '正在检查同名音频，尚未调用语音服务。文件模型标签：') + settings.get("_filename_model","未指定模型"))
        self.submit(lambda: generation_duplicates(lines, output, snapshot["protected"], snapshot["entries"], settings.get("_filename_model")),
                    lambda duplicates: self.review_generation(duplicates, snapshot), self.generation_error)

    def choose_duplicate_action(self, duplicates, total, skip, model_name=None):
        dialog = QMessageBox(self)
        dialog.setWindowTitle(tr('ui.b319164050c9', '发现同名音频'))
        dialog.setText(tr('ui.46acd233ae05', '{value0} 条待生成台词中，{value1} 条已有同名音频或与本批次其他台词重名。\n模型标签：{value2}。对照当前模型及旧的无模型标签文件，其他模型单独保存。\n请选择如何继续。原文件不会被覆盖。', value0=total, value1=len(duplicates), value2=model_name or '未指定模型'))
        dialog.setDetailedText("\n".join((item["category"] + "/" if item["category"] else "") + item["text"] for item in duplicates))
        skip_button = dialog.addButton(tr('ui.0ed0d54d7427', '跳过重复，生成其余'), QMessageBox.ButtonRole.AcceptRole)
        all_button = dialog.addButton(tr('ui.f31aa2b4d4d0', '全部生成，另存副本'), QMessageBox.ButtonRole.ActionRole)
        cancel_button = dialog.addButton(tr('ui.2cd0f3be8738', '取消'), QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(skip_button if skip else all_button)
        dialog.setEscapeButton(cancel_button)
        dialog.exec()
        return "skip" if dialog.clickedButton() is skip_button else "all" if dialog.clickedButton() is all_button else "cancel"

    def review_generation(self, duplicates, snapshot):
        action = self.choose_duplicate_action(duplicates, len(snapshot["lines"]), snapshot["skip"], snapshot["settings"].get("_filename_model")) if duplicates else ("skip" if snapshot["skip"] else "all")
        if action == "cancel":
            self.tts_busy = False; self.update_api_controls()
            self.tts_status.setText(tr('ui.8ffd78f67941', '已取消生成，尚未调用语音服务。'))
            self.finish_generation_progress(False, self.tts_status.text())
            return
        self.pending_generation_total = len(snapshot["lines"])
        protected, provider = snapshot["protected"], snapshot["provider"]
        if snapshot["entries"] is not None:
            self.submit(lambda: generate_dialogue_entries(snapshot["settings"], snapshot["entries"], snapshot["output"], protected,
                self.progress.emit, provider, action == "skip", self.generation_cancel, status=self.generation_state.emit), self.dialogue_generated, self.generation_error)
        else:
            self.submit(lambda: generate(snapshot["settings"], snapshot["lines"], snapshot["output"], protected,
                self.progress.emit, provider, self.generation_cancel, status=self.generation_state.emit, skip_existing=action == "skip"), self.generated, self.generation_error)
