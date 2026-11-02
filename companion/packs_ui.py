"""Native offline pack browser; slow validation/copies stay off the GUI thread."""
import copy
from pathlib import Path
import shiboken6
from PySide6.QtCore import Qt,QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QCheckBox,
    QScrollArea,QWidget,QFrame,QPlainTextEdit,QDialogButtonBox,QMessageBox,QProgressBar)
from .file_dialogs import FileDialogs
from .pack_text import p
from .packs import PackPreview,validate_directory,install_and_use,restore_selection


def info_dialog(parent,title,text):
    dialog=QDialog(parent);dialog.setWindowTitle(title);dialog.resize(620,420)
    layout=QVBoxLayout(dialog);content=QPlainTextEdit(text);content.setReadOnly(True);layout.addWidget(content)
    buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
    dialog.exec()


def pack_info(pack):
    m=pack.manifest
    return (m['name']+'\n'+m['character']+' · '+m['language']+'\n'+m['description']+'\n'+
        p('inventory',lines=len(pack.profile['dialogues']),rules=len(pack.profile['rules']),missing=len(pack.missing))+'\n'+
        '\n'.join(f"{r['name']} · {r['event']} · {r.get('hotkey','')} → {r['source'] or 'voice/'} · {r['start']}–{r['end']}" for r in pack.profile['rules'])+
        ('\n\n'+p('missing_list',items='\n'.join(pack.manifest['missing_sources'])) if pack.manifest['missing_sources'] else ''))


class PackBrowser(QDialog):
    def __init__(self,window):
        super().__init__(window);self.w=window;self.busy=False;self.previews=[];self.setWindowTitle(p('title'));self.resize(760,600)
        from .audio import Audio
        self.audio=Audio(self);self.audio.profile={'voice_volume':70,'bgm_enabled':False}
        layout=QVBoxLayout(self)
        top=QHBoxLayout();self.import_button=QPushButton(p('import'));self.import_button.clicked.connect(self.import_file);top.addWidget(self.import_button)
        self.back=QPushButton(p('back'));self.back.setEnabled(hasattr(window,'pack_previous'));self.back.clicked.connect(self.return_previous);top.addWidget(self.back)
        self.start=QPushButton(p('start'));self.start.setVisible(window.paused);self.start.clicked.connect(self.start_companion);top.addWidget(self.start)
        self.bind_button=QPushButton(p("bind"));self.bind_button.setEnabled(False);self.bind_button.clicked.connect(self.link_wallpaper);top.addWidget(self.bind_button)
        layout.addLayout(top)
        self.status=QLabel(p('scanning'));self.status.setWordWrap(True);layout.addWidget(self.status)
        self.progress=QProgressBar();self.progress.setRange(0,0);self.progress.hide();layout.addWidget(self.progress)
        self.audio.message.connect(self.status.setText)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);self.content=QWidget();self.cards=QVBoxLayout(self.content);self.cards.addStretch();self.scroll.setWidget(self.content);layout.addWidget(self.scroll)
        close=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);close.rejected.connect(self.reject);layout.addWidget(close)
        self.finished.connect(self.cleanup)
        self.run(self.discover,self.show_catalog)
    def reject(self):
        if not self.busy:super().reject()
    def cleanup(self,*_):
        self.audio.stop()
        for item in self.previews:item.close()
        self.previews.clear()
    def run(self,job,callback):
        if self.busy:return
        self.busy=True;self.progress.show();self.import_button.setEnabled(False);self.content.setEnabled(False);self.back.setEnabled(False)
        self.status.setText(p('working'))
        def done(value):
            if not shiboken6.isValid(self):
                if isinstance(value,PackPreview):value.close()
                return
            self.busy=False;self.progress.hide();self.import_button.setEnabled(True);self.content.setEnabled(True);self.back.setEnabled(hasattr(self.w,'pack_previous'))
            try:callback(value)
            except Exception as exc:self.status.setText(p('unavailable',error=str(exc)))
        def failed(error):
            if shiboken6.isValid(self):
                self.busy=False;self.progress.hide();self.import_button.setEnabled(True);self.content.setEnabled(True);self.back.setEnabled(hasattr(self.w,'pack_previous'));self.status.setText(p('unavailable',error=error))
        self.w.submit(job,done,failed)
    def discover(self):
        from .pack_builtins import builtin_catalog
        entries=[('builtin',entry,None) for entry in builtin_catalog()]
        base=self.w.store.path.parent/'packs'
        if base.is_dir():
            for root in sorted(base.iterdir()):
                if not root.is_dir() or root.is_symlink():continue
                try:entries.append(('installed',validate_directory(root),None))
                except Exception as exc:entries.append(('invalid',root.name,str(exc)))
        return entries
    def show_catalog(self,entries):
        self.status.setText(p('note'))
        for kind,value,error in entries:self.add_card(kind,value,error)
    def add_card(self,kind,value,error=None):
        frame=QFrame();frame.setFrameShape(QFrame.Shape.StyledPanel);layout=QVBoxLayout(frame)
        if kind=='invalid':
            label=QLabel(str(value)+'\n'+p('unavailable',error=error));label.setWordWrap(True);layout.addWidget(label)
        else:
            m=value if kind=='builtin' else value.manifest
            label=QLabel(m['name']+' · '+p('builtin' if kind=='builtin' else 'installed')+'\n'+m['character']+' · '+m['language']+'\n'+m['description'])
            label.setWordWrap(True);label.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(label)
            count=m.get('recordings',0) if kind=='builtin' else value.recordings
            size=m.get('bytes',0) if kind=='builtin' else sum(f['size'] for f in m['files'])
            complete=m.get('complete',False) if kind=='builtin' else value.complete
            state=QLabel(p('summary',count=count,size=f'{size/1048576:.1f}',status=p('ready' if complete else 'missing')));state.setWordWrap(True);layout.addWidget(state)
            buttons=QHBoxLayout()
            for action in ('preview','rules','use'):
                b=QPushButton(p(action));b.setObjectName('pack_'+action);b.clicked.connect(lambda checked=False,k=kind,v=value,a=action:self.resolve(k,v,a));buttons.addWidget(b)
            layout.addLayout(buttons)
        self.cards.insertWidget(self.cards.count()-1,frame)
    def resolve(self,kind,value,action):
        if self.busy:return
        if kind=='builtin':
            from .pack_builtins import prepare_builtin
            def loaded(preview):self.previews.append(preview);self.perform(preview.pack,action)
            self.run(lambda:prepare_builtin(value['id'],self.w.store.path.parent/'pack-temp'),loaded)
        else:self.perform(value,action)
    def perform(self,pack,action):
        if action=='preview':
            source=pack.manifest['preview']
            if not source:self.status.setText(p('no_audio'));return
            self.audio.play_voice(pack.root/source);self.status.setText(p('preview')+' · '+Path(source).name)
        elif action=='rules':info_dialog(self,p('rules'),pack_info(pack))
        else:
            dialog=QDialog(self);dialog.setWindowTitle(p('confirm'));layout=QVBoxLayout(dialog)
            dialog.resize(650,480)
            text=QPlainTextEdit(pack_info(pack)+'\n\n'+p('note'));text.setReadOnly(True);layout.addWidget(text)
            operation=QCheckBox(p('operation'));operation.setChecked(False);operation.setEnabled(bool(pack.operation));layout.addWidget(operation)
            buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
            if dialog.exec()!=QDialog.DialogCode.Accepted:return
            if not self.w.autosave.flush():return
            self.audio.stop()
            def used(result):
                identifier,previous=result
                # A second use can always return to the immediate preceding setup.
                self.applied_id=identifier;self.bind_button.setEnabled(True)
                self.w.pack_previous=previous;self.w.reload_pack_state(identifier)
                self.status.setText(p('used'));self.back.setEnabled(True);self.start.setVisible(self.w.paused)
            opt=operation.isChecked()
            self.run(lambda:install_and_use(self.w.store,pack,opt),used)
    def import_file(self):
        if not self.w.autosave.flush():return
        value,_=FileDialogs.getOpenFileName(self,p('import'),str(self.w.store.path.parent),'Companion pack (*.wcpak)')
        if not value:return
        def loaded(preview):
            self.previews.append(preview)
            info_dialog(self,p('review'),pack_info(preview.pack))
            self.add_card('staged',preview.pack)
            self.status.setText(p('note'))
        self.run(lambda:PackPreview(value,self.w.store.path.parent/'pack-temp'),loaded)
    def return_previous(self):
        if not self.w.autosave.flush():return
        try:
            previous=self.w.pack_previous;restore_selection(self.w.store,previous)
            selected=previous.get('standalone_profile') if previous.get('run_mode')=='standalone' else previous.get('manual_profile')
            self.w.reload_pack_state(selected);self.status.setText(p('back'));del self.w.pack_previous;self.back.setEnabled(False)
        except Exception as exc:self.status.setText(p('unavailable',error=str(exc)))
    def link_wallpaper(self):
        if not self.w.autosave.flush():return
        config=copy.deepcopy(self.w.store.config);config['_wallpaper_command_query']=False
        backend=config.get('wallpaper_backend','wallpaper_engine');query=self.w.registry.wallpapers[backend][1]
        def found(result):
            if not result.get('path'):self.status.setText(p('bind_missing'));return
            existing=self.w.store.bound_profile(result['path'])
            if existing and existing['id']!=self.applied_id:self.status.setText(p('bind_conflict'));return
            if QMessageBox.question(self,p('bind'),p('bind_confirm')+'\n'+result.get('title',''),QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
            before=copy.deepcopy(self.w.store.config)
            try:
                profile=self.w.store.profile(self.applied_id)
                if not profile:raise ValueError(p('not_selected'))
                profile['wallpaper']=result['path'];self.w.store.config.update(run_mode='wallpaper_engine',manual_profile='')
                self.w.store.save();self.w.reload_pack_state(self.applied_id);self.status.setText(p('bind'))
            except Exception as exc:self.w.store.config=before;self.status.setText(p('unavailable',error=str(exc)))
        self.run(lambda:query(config),found)
    def start_companion(self):
        if self.w.paused:self.w.toggle_pause()
        self.start.hide()


class PackMixin:
    def open_companion_packs(self):
        if self.autosave.flush():PackBrowser(self).exec()
    def reload_pack_state(self,identifier=None):
        self.autosave.busy=True
        try:
            self.load_settings();self.apply_run_mode();self.refresh_profiles(identifier);self.activate_profile(force=True)
            self.operation_voices.refresh();self.autosave.baseline=self.autosave.forms();self.autosave.last=None;self.autosave.toast.hide()
        finally:self.autosave.busy=False
        if not self.is_standalone():self.detect()
    def export_companion_pack(self):
        if not self.autosave.flush():return
        profile=self.store.profile(self.editing_id)
        if not profile:self.report_error(p('not_selected'));return
        from .pack_export_ui import PackExportDialog
        PackExportDialog(self,copy.deepcopy(profile)).exec()
