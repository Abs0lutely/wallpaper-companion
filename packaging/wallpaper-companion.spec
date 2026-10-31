# PyInstaller onedir build: keep Qt DLLs replaceable and avoid temporary extraction.
from pathlib import Path

root = Path(SPECPATH).parent
a = Analysis(
    [str(root / "main.py")], pathex=[str(root)], binaries=[], datas=[],
    hiddenimports=["pynput.keyboard._win32", "pynput.mouse._win32",
                   "keyring.backends.Windows", "win32ctypes.pywin32.win32cred"],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets"],
    hookspath=[], runtime_hooks=[], noarchive=False,
)
# Qt 6.10 uses Windows' unversioned ICU API. A Conda environment can make
# dependency analysis collect a different ICU build with suffixed exports;
# bundling that DLL shadows System32 and prevents QtCore from importing.
# Windows 10/11 already supplies the ICU runtime expected by this Qt wheel.
a.binaries = [entry for entry in a.binaries
              if Path(entry[0]).name.lower() not in {"icuuc.dll", "icudt78.dll"}]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="WallpaperCompanion",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False,
          icon=str(root / "build/app.ico"), version=str(root / "build/version.txt"))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="WallpaperCompanion")
