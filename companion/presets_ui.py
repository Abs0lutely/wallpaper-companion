"""Explicit preview before importing portable rules, text and playback settings."""
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QLabel, QPlainTextEdit, QVBoxLayout


class PresetImportDialog(QDialog):
    def __init__(self, profiles, warnings, target=None, parent=None):
        from .ui import hint
        super().__init__(parent)
        self.setWindowTitle("导入互动配置 · 先确认内容")
        self.resize(650, 400)
        layout = QVBoxLayout(self)
        layout.addWidget(hint("配置文件只包含规则、台词和播放设置；不包含音频、密钥、插件或对方电脑路径。"))
        preview = QPlainTextEdit("\n".join(f"{p['name']}：{len(p['rules'])} 条规则，{len(p['dialogues'])} 条台词" for p in profiles))
        preview.setReadOnly(True)
        layout.addWidget(preview)
        self.mode = QComboBox()
        self.mode.setProperty("help_override", "新建独立配置，或仅在单配置文件时替换当前规则和台词；保留本机壁纸与音频目录。")
        self.mode.addItem("新建为未绑定配置（稍后绑定壁纸）", "new")
        if target and len(profiles) == 1:
            self.mode.addItem("应用到当前配置：" + target["name"], "replace")
        layout.addWidget(QLabel("导入方式"))
        layout.addWidget(self.mode)
        layout.addWidget(hint("应用到当前配置会替换规则、台词和播放设置；保留当前壁纸和音频目录，并解除共享台词关联，避免修改其他壁纸的台词。"))
        if warnings:
            layout.addWidget(hint("\n".join(warnings[:8])))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("确认导入")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
