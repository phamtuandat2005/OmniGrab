# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
from pathlib import Path
import os

ROOT_DIR = Path(SPECPATH).resolve()
RUNTIME_DIR = ROOT_DIR / "build_runtime"
PLAYWRIGHT_DIR = RUNTIME_DIR / "playwright-browsers"
WHISPER_DIR = RUNTIME_DIR / "models" / "faster-whisper-base"

datas = [('ui', 'ui'), ('core', 'core'), ('assets', 'assets')]
if PLAYWRIGHT_DIR.is_dir():
    datas.append((str(PLAYWRIGHT_DIR), 'playwright-browsers'))
if WHISPER_DIR.is_dir():
    datas.append((str(WHISPER_DIR), 'models/faster-whisper-base'))

binaries = []
if (ROOT_DIR / "ffmpeg.exe").is_file():
    binaries.append((str(ROOT_DIR / "ffmpeg.exe"), '.'))
if (ROOT_DIR / "ffprobe.exe").is_file():
    binaries.append((str(ROOT_DIR / "ffprobe.exe"), '.'))

hiddenimports = [
    'PyQt6', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets',
    'yt_dlp', 'audioop', 'audioop_lts', 'requests',
    'win32com', 'win32com.client', 'win32com.propsys'
]
for pkg in [
    'playwright', 'faster_whisper', 'ctranslate2', 'curl_cffi',
    'f2', 'pydub', 'gtts', 'deep_translator', 'cryptography',
    'bs4', 'av', 'onnxruntime', 'win32com'
]:
    try:
        tmp_ret = collect_all(pkg)
        datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
    except Exception:
        pass


a = Analysis(
    ['main.py'],
    pathex=[str(ROOT_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='OmniGrab',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(ROOT_DIR / 'assets' / 'icon.ico')],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='OmniGrab',
)
