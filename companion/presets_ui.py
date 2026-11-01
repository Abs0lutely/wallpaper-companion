"""Explicit preview before importing portable rules, text and playback settings."""
from .i18n import tr
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QLabel, QPlainTextEdit, QVBoxLayout


class PresetImportDialog(QDialog):
    def __init__(self, profiles, warnings, target=None, parent=None):
        from .ui import hint
        super().__init__(parent)
        self.setWindowTitle(tr('ui.eb00d2b05c65', '导入互动配置 · 先确认内容'))
        self.resize(650, 400)
        layout = QVBoxLayout(self)
        layout.addWidget(hint(tr('ui.62421a9908e9', '配置文件只包含规则、台词和播放设置；不包含音频、密钥、插件或对方电脑路径。')))
        preview = QPlainTextEdit("\n".join(tr('ui.b2096a3badce', '{value0}：{value1} 条规则，{value2} 条台词', value0=p['name'], value1=len(p['rules']), value2=len(p['dialogues'])) for p in profiles))
        preview.setReadOnly(True)
        layout.addWidget(preview)
        self.mode = QComboBox()
        self.mode.setProperty("help_override", tr('ui.27c9da913f51', '新建独立配置，或仅在单配置文件时替换当前规则和台词；保留本机壁纸与音频目录。'))
        self.mode.addItem(tr('ui.a310df388233', '新建为未绑定配置（稍后绑定壁纸）'), "new")
        if target and len(profiles) == 1:
            self.mode.addItem(tr('ui.6b93c5998fa7', '应用到当前配置：') + target["name"], "replace")
        layout.addWidget(QLabel(tr('ui.53a42c6b6e8c', '导入方式')))
        layout.addWidget(self.mode)
        layout.addWidget(hint(tr('ui.41f65b825204', '应用到当前配置会替换规则、台词和播放设置；保留当前壁纸和音频目录，并解除共享台词关联，避免修改其他壁纸的台词。')))
        if warnings:
            layout.addWidget(hint("\n".join(warnings[:8])))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(tr('ui.4a8d6841b402', '确认导入'))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr('ui.2cd0f3be8738', '取消'))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
