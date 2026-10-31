"""Native spring coverage, interruption and stable hit/layout geometry."""
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QAbstractButton,QPushButton,QToolButton,QCheckBox,QDialog,QDialogButtonBox,QVBoxLayout
from companion.core import ROOT,Store
from companion.ui import Window,STYLE
import shiboken6

output=ROOT/"output"; output.mkdir(exist_ok=True)
fixture=tempfile.TemporaryDirectory(dir=output)
store=Store(Path(fixture.name)/"data/config.json"); store.config.update(we_dir="",workshop_dir="")
app=QApplication([]); app.setQuitOnLastWindowClosed(False); app.setStyle("Fusion");app.setStyleSheet(STYLE)
report={}
with patch("companion.managed_api.api"),patch("companion.secrets.read_secret",return_value=""):
    w=Window(store,hooks=False);w.show();QTest.qWait(100)
    try:
        report["all_existing_app_buttons_attached"]=all(id(b) in w.button_motion.springs for b in w.findChildren(QAbstractButton))
        dialog=QDialog(w);layout=QVBoxLayout(dialog)
        button=QPushButton("弹簧动画测试",dialog);layout.addWidget(button)
        check=QCheckBox("键盘开关测试",dialog);layout.addWidget(check)
        tool=QToolButton(dialog);tool.setText("工具按钮测试");layout.addWidget(tool)
        box=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel,dialog);layout.addWidget(box)
        dialog.show();QTest.qWait(100)
        buttons=(button,check,tool,box.button(QDialogButtonBox.StandardButton.Save),box.button(QDialogButtonBox.StandardButton.Cancel))
        report["dynamic_dialog_checkbox_tool_and_standard_buttons_attached"]=all(id(b) in w.button_motion.springs for b in buttons)
        spring=w.button_motion.springs[id(button)];geometry=button.geometry();clicked=[]
        button.clicked.connect(lambda:clicked.append(1))
        QTest.mousePress(button,Qt.MouseButton.LeftButton);QTest.qWait(110)
        report["press_compresses_drawing_only"]=spring.effect.get_scale()<.98 and button.geometry()==geometry and not clicked
        QTest.mouseRelease(button,Qt.MouseButton.LeftButton)
        scales=[];geometry_stable=True
        for _ in range(42):
            QTest.qWait(10);scales.append(spring.effect.get_scale());geometry_stable &= button.geometry()==geometry
        report["release_has_spring_overshoot_and_returns_idle"]=max(scales)>1.0 and spring.effect.get_scale()==1.0 and not spring.effect.isEnabled()
        report["layout_and_click_semantics_unchanged"]=geometry_stable and clicked==[1]
        button.click();QTest.qWait(35)
        report["quick_programmatic_click_still_animates"]=spring.effect.isEnabled() and spring.effect.get_scale()<1
        button.click();QTest.qWait(500)
        report["repeated_clicks_settle_without_stale_scale"]=spring.effect.get_scale()==1 and not spring.effect.isEnabled() and len(clicked)==3
        QTest.keyClick(check,Qt.Key.Key_Space);QTest.qWait(500)
        report["keyboard_activation_preserves_toggle"]=check.isChecked() and w.button_motion.springs[id(check)].effect.get_scale()==1
        button.click();button.setEnabled(False);QTest.qWait(500)
        report["disabling_during_motion_settles"]=spring.effect.get_scale()==1 and not spring.effect.isEnabled()
        button.setEnabled(True);button.click();QTest.qWait(20);dialog.hide();QTest.qWait(30)
        report["hidden_dialog_stops_animation"]=spring.effect.get_scale()==1 and not spring.effect.isEnabled()
        key=id(button);shiboken6.delete(dialog);QTest.qWait(20)
        report["destroyed_buttons_removed_from_tracking"]=key not in w.button_motion.springs and key not in w.action_feedback.buttons
        w.navigation[2].click();QTest.qWait(500);w.grab().save(str(output/"speech-feedback.png"))
        (output/"smoke-button-motion.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(json.dumps(report),flush=True)
    finally:
        w.cleanup();shiboken6.delete(w)
fixture.cleanup()
sys.exit(0 if all(report.values()) else 1)
