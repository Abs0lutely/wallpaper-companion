"""Start every picker from the current value, never implicit OS recent folders."""
from pathlib import Path
from PySide6.QtWidgets import QFileDialog as NativeFileDialog


def initial_path(value="",fallback=None,base=None,directory=False,save=False):
    from .core import DATA
    fallback=Path(fallback or DATA).expanduser()
    path=Path(str(value)).expanduser() if str(value).strip() else fallback
    if not path.is_absolute():path=Path(base or fallback)/path
    path=path.resolve()
    if path.exists():return str(path.parent if directory and path.is_file() else path)
    name=path.name
    while not path.exists() and path.parent!=path:path=path.parent
    if path.is_file():path=path.parent
    return str(path/name if save and name else path)


def context(parent):
    from .core import DATA
    window=parent.window() if parent is not None else None
    store=getattr(window,"store",None)
    fallback=store.path.parent if store else DATA
    if store and getattr(window,"editing_id",None):
        profile=store.profile(window.editing_id) or {}
        fallback=profile.get("asset_dir") or profile.get("voice_dir") or fallback
    base=None
    relative=parent.property("projectRelative") if parent is not None else False
    if relative and hasattr(window,"provider_widgets"):
        project=window.provider_widgets.get("project")
        if project and project.text().strip():base=project.text().strip()
    if parent is not None and parent.property("pathBase"):base=parent.property("pathBase")
    return fallback,base


class FileDialogs:
    @staticmethod
    def _path(parent,value,directory=False,save=False):
        fallback,base=context(parent)
        return initial_path(value,fallback,base,directory,save)
    @staticmethod
    def getExistingDirectory(parent=None,caption="",directory="",*args,**kwargs):
        return NativeFileDialog.getExistingDirectory(parent,caption,FileDialogs._path(parent,directory,True),*args,**kwargs)
    @staticmethod
    def getOpenFileName(parent=None,caption="",directory="",*args,**kwargs):
        return NativeFileDialog.getOpenFileName(parent,caption,FileDialogs._path(parent,directory),*args,**kwargs)
    @staticmethod
    def getOpenFileNames(parent=None,caption="",directory="",*args,**kwargs):
        return NativeFileDialog.getOpenFileNames(parent,caption,FileDialogs._path(parent,directory),*args,**kwargs)
    @staticmethod
    def getSaveFileName(parent=None,caption="",directory="",*args,**kwargs):
        return NativeFileDialog.getSaveFileName(parent,caption,FileDialogs._path(parent,directory,save=True),*args,**kwargs)
