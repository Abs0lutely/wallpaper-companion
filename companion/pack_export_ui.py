"""Review-first export of one profile; source paths appear only in local preview."""
import copy
from pathlib import Path
import shiboken6
from PySide6.QtCore import Qt,QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QPlainTextEdit,
    QPushButton,QCheckBox,QScrollArea,QWidget,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QLabel,QProgressBar)
from .pack_text import p
from .packs import plan_export,write_export,reference_sources
from .file_dialogs import FileDialogs


class PackExportDialog(QDialog):
    def __init__(self,window,profile):
        super().__init__(window);self.w=window;self.profile=profile;self.plan=None;self.busy=False;self.output=None
        self.setWindowTitle(p('export'));self.resize(800,680)
        outer=QVBoxLayout(self);scroll=QScrollArea();scroll.setWidgetResizable(True);content=QWidget();layout=QVBoxLayout(content);scroll.setWidget(content);outer.addWidget(scroll,1)
        self.form=QFormLayout();self.fields={}
        for key in ('name','character','language','author','description'):
            field=QLineEdit(profile['name'] if key=='name' else 'zh-CN' if key=='language' else '')
            self.fields[key]=field;self.form.addRow(p(key),field)
        layout.addLayout(self.form)
        options=QHBoxLayout();self.bgm=QCheckBox(p('bgm'));self.operation=QCheckBox(p('include_operation'))
        options.addWidget(self.bgm);options.addWidget(self.operation);layout.addLayout(options)
        hint=QLabel(p('export_hint'));hint.setWordWrap(True);layout.addWidget(hint)
        top=QHBoxLayout();self.scan=QPushButton(p('resources'));self.scan.clicked.connect(self.preview_resources);top.addWidget(self.scan)
        self.content_button=QPushButton(p("content"));self.content_button.setEnabled(False);self.content_button.clicked.connect(self.show_contents);top.addWidget(self.content_button)
        for key,checked in (('all',True),('none',False)):
            button=QPushButton(p(key));button.clicked.connect(lambda _,v=checked:self.select_all(v));top.addWidget(button)
        layout.addLayout(top)
        self.files=QTableWidget(0,3);self.files.setMinimumHeight(170);self.files.setHorizontalHeaderLabels([p('file'),p('source_header'),p('size')]);self.files.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.files.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.files.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);layout.addWidget(self.files,1)
        self.missing=QPlainTextEdit();self.missing.setReadOnly(True);self.missing.setMaximumHeight(100);layout.addWidget(self.missing)
        self.rights=QCheckBox(p('rights'));outer.addWidget(self.rights)
        self.status=QLabel();self.status.setWordWrap(True);outer.addWidget(self.status)
        self.progress=QProgressBar();self.progress.setRange(0,0);self.progress.hide();outer.addWidget(self.progress)
        bottom=QHBoxLayout();self.export_button=QPushButton(p('save'));self.export_button.clicked.connect(self.export_file);bottom.addWidget(self.export_button)
        self.open_button=QPushButton(p('open'));self.open_button.setEnabled(False);self.open_button.clicked.connect(self.open_directory);bottom.addWidget(self.open_button)
        close=QPushButton(p('close'));close.clicked.connect(self.reject);bottom.addWidget(close);outer.addLayout(bottom)
        for field in self.fields.values():field.textChanged.connect(self.invalidate)
        self.bgm.toggled.connect(self.invalidate);self.operation.toggled.connect(self.invalidate)
        self.files.itemChanged.connect(lambda _:self.refresh_summary())
    def reject(self):
        if not self.busy:super().reject()
    def invalidate(self,*_):
        self.plan=None;self.content_button.setEnabled(False);self.status.setText(p('source_changed'))
    def controls(self,enabled):
        for field in self.fields.values():field.setEnabled(enabled)
        for widget in (self.scan,self.export_button,self.bgm,self.operation,self.files,self.rights):widget.setEnabled(enabled)
        self.progress.setVisible(not enabled);self.busy=not enabled
    def run(self,task,callback):
        if self.busy:return
        self.controls(False);self.status.setText(p('working'))
        def done(value):
            if not shiboken6.isValid(self):return
            self.controls(True)
            try:callback(value)
            except Exception as exc:self.status.setText(p('unavailable',error=str(exc)))
        def failed(error):
            if shiboken6.isValid(self):self.controls(True);self.status.setText(p('unavailable',error=error))
        self.w.submit(task,done,failed)
    def preview_resources(self):
        metadata={key:field.text().strip() for key,field in self.fields.items()}
        from .operation_rules import config_payload
        from .assets import shared_root
        from .bundled_audio import bundled_root
        config=copy.deepcopy(self.w.store.config)
        operation=config_payload(config) if self.operation.isChecked() else None
        roots=[config.get('operation_voice_dir',''),self.profile.get('voice_dir',''),shared_root(self.w.store)/'voice',bundled_root()/'operation-voice',bundled_root()/'operation-voice-ja-JP']
        if config.get('operation_voice_pack_only'):roots=[config.get('operation_voice_dir','')]
        roots=[str(r) for r in roots if str(r).strip()]
        bgm=self.bgm.isChecked()
        self.run(lambda:plan_export(self.profile,metadata,include_bgm=bgm,operation=operation,operation_roots=roots,excluded_sources=reference_sources(config)),self.show_plan)
    def show_plan(self,plan):
        self.plan=plan;self.content_button.setEnabled(True);self.files.blockSignals(True);self.files.setRowCount(len(plan.sources))
        for row,(name,source) in enumerate(sorted(plan.sources.items())):
            item=QTableWidgetItem(name);item.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsUserCheckable);item.setCheckState(Qt.CheckState.Checked);item.setToolTip(name);self.files.setItem(row,0,item)
            for col,value in ((1,str(source)),(2,f'{plan.stamps[name][0]/1048576:.3f} MiB')):
                cell=QTableWidgetItem(value);cell.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable);cell.setToolTip(value);self.files.setItem(row,col,cell)
        self.files.blockSignals(False);self.refresh_summary()
    def show_contents(self):
        if not self.plan:return
        from .packs_ui import info_dialog
        profile=self.plan.preset['profiles'][0]
        text=p('inventory',lines=len(profile['dialogues']),rules=len(profile['rules']),missing=len(self.plan.missing))+'\n\n'
        text+='\n'.join(f"{r['name']} · {r['event']} → {r['source'] or 'voice/'}" for r in profile['rules'])
        text+='\n\n'+'\n'.join(f"{d['category']} · {d['text']}" for d in profile['dialogues'])
        info_dialog(self,p('content'),text)
    def selected(self):return [self.files.item(row,0).text() for row in range(self.files.rowCount()) if self.files.item(row,0).checkState()==Qt.CheckState.Checked]
    def select_all(self,checked):
        if self.busy:return
        self.files.blockSignals(True)
        for row in range(self.files.rowCount()):self.files.item(row,0).setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self.files.blockSignals(False);self.refresh_summary()
    def refresh_summary(self):
        if not self.plan:return
        selected=self.selected();excluded=[n for n in self.plan.sources if n not in selected]
        self.status.setText(p('summary',count=len([n for n in selected if n.startswith('voice/')]),size=f'{sum(self.plan.stamps[n][0] for n in selected)/1048576:.2f}',status=p('review')))
        self.missing.setPlainText(p('missing_list',items='\n'.join(self.plan.missing+excluded)))
    def export_file(self):
        if not self.plan or not self.rights.isChecked():self.status.setText(p('select_resources'));return
        target,_=FileDialogs.getSaveFileName(self,p('export'),str(self.w.store.path.parent/'companion-pack.wcpak'),'Companion pack (*.wcpak)')
        if not target:return
        plan=self.plan;selected=self.selected()
        def done(path):self.output=path;self.open_button.setEnabled(True);self.status.setText(p('done')+' '+str(path))
        self.run(lambda:write_export(plan,target,selected,self.w.store.protected()),done)
    def open_directory(self):
        if self.output:QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output.parent)))
