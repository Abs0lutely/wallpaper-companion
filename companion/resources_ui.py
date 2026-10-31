"""Explicit per-channel sharing choices without moving or duplicating audio."""
from pathlib import Path
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QVBoxLayout
from .assets import channel_resources, private_root, shared_root
from .core import identity


class ResourceDialog(QDialog):
    def __init__(self, store, profile, parent=None, dedicated=False):
        from .ui import hint, path_field
        super().__init__(parent)
        self.setWindowTitle("共享 / 专用资源目录")
        self.resize(660, 320)
        self.profile, self.store = profile, store
        self.shared = shared_root(store)
        layout = QVBoxLayout(self)
        layout.addWidget(hint("共享模式直接引用共享文件夹，不复制文件；专用模式使用本壁纸目录，音频可在音频库导入。语音、BGM 和台词可分别选择。切换不会移动或删除旧文件。"))
        layout.addWidget(hint("共享根目录：" + str(self.shared) + "（可在音频库更改）"))
        self.root = QLineEdit(str(private_root(store, profile)))
        form = QFormLayout()
        form.addRow("专用根目录（默认 data 下）", path_field(self.root))
        self.modes = {}
        for key, label, name in [("voice_dir", "语音来源", "voice"), ("bgm_dir", "BGM 来源", "bgm"), ("dialogue_file", "台词库来源", "dialogues.json")]:
            combo = QComboBox()
            for text, value in [("直接引用共享资源", "shared"), ("本壁纸专用目录", "private"), ("保留当前路径", "custom")]:
                combo.addItem(text, value)
            current = profile.get(key, "")
            mode = "shared" if identity(current) == identity(str(self.shared / name)) else "private" if not current or identity(current) == identity(str(private_root(store, profile) / name)) else "custom"
            combo.setCurrentIndex(combo.findData("private" if dedicated else mode))
            combo.setToolTip("直接共享无需重复存储；专用目录可导入自己的音频；保留当前路径不改变旧配置。")
            self.modes[key] = combo
            form.addRow(label, combo)
        layout.addLayout(form)
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(self.accept)
        controls.rejected.connect(self.reject)
        layout.addWidget(controls)

    def apply(self):
        if not self.root.text().strip():
            raise ValueError("专用根目录不能为空；可使用默认 data 路径")
        return channel_resources(self.profile, self.shared, self.root.text().strip(),
                                 {key: combo.currentData() for key, combo in self.modes.items()}, self.store.protected())
