"""
main.py - Điểm khởi chạy ứng dụng OmniGrab.

Tải video hàng loạt từ TikTok, Douyin, Facebook.
"""

from __future__ import annotations

import os
import sys

# Dung Chromium di kem ban phat hanh, khong phu thuoc Chrome/Edge tren may khach.
if sys.platform == "win32" and getattr(sys, "frozen", False):
    _runtime_base = getattr(sys, "_MEIPASS", None)
    if not _runtime_base:
        _runtime_base = os.environ.get(
            "NUITKA_ONEFILE_DIRECTORY", os.path.dirname(sys.executable)
        )
    _bundled_browsers = os.path.join(_runtime_base, "playwright-browsers")
    if os.path.isdir(_bundled_browsers):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = _bundled_browsers

if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("OmniGrab.VideoDownloader.1.0")
    except Exception:
        pass
    try:
        if sys.stdout is not None:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr is not None:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Tắt log cảnh báo cấp độ thấp của Qt Multimedia / FFmpeg để tránh tràn console
os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia*=false;qt.multimedia.ffmpeg*=false")

# Vá tương thích PyAV 19+ cho faster-whisper và tắt log cảnh báo rác
try:
    # pyrefly: ignore [missing-import]
    import av
    try:
        av.logging.set_level(av.logging.ERROR)
    except Exception:
        pass
    # pyrefly: ignore [missing-assign]
    _orig_av_open = av.open

    def _safe_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)

    av.open = _safe_av_open
except Exception:
    pass

# Vá tương thích cho f2 khi đóng gói (tránh thiếu conf.yaml)
import core.f2_patch

# pyrefly: ignore [missing-import]
from PyQt6.QtWidgets import QApplication
# pyrefly: ignore [missing-import]
from PyQt6.QtCore import Qt
# pyrefly: ignore [missing-import]
from PyQt6.QtGui import QFont, QIcon
# pyrefly: ignore [missing-import]
from ui.main_window import MainWindow
from ui.styles import get_app_stylesheet

from core.security import run_security_checks, get_resource_path, setup_ffmpeg_environment

# Tự động nạp ffmpeg và ffprobe vào PATH hệ thống ngay khi khởi chạy
setup_ffmpeg_environment()


def _ensure_windows_shortcut(ico_path: str) -> None:
    """Đăng ký shortcut Start Menu có kèm AppUserModelID để Windows Shell luôn hiển thị icon."""
    if sys.platform != "win32":
        return
    try:
        import win32com.client
        from win32com.propsys import propsys, pscon

        shortcut_path = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\OmniGrab.lnk")
        shell = win32com.client.Dispatch("WScript.Shell")
        is_frozen = getattr(sys, "frozen", False)

        target_exe = os.path.abspath(sys.executable)
        if is_frozen:
            target_args = ""
            target_dir = os.path.dirname(target_exe)
            # Ưu tiên icon nhúng trực tiếp trong file exe để luôn hợp lệ vĩnh viễn
            icon_loc = f"{target_exe},0"
        else:
            target_args = f'"{os.path.abspath(sys.argv[0])}"'
            target_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            abs_ico = os.path.abspath(ico_path)
            icon_loc = f"{abs_ico},0" if os.path.isfile(abs_ico) else f"{target_exe},0"

        need_update = True
        if os.path.isfile(shortcut_path):
            try:
                existing = shell.CreateShortCut(shortcut_path)
                old_ico = existing.IconLocation.split(",")[0].strip('"')
                # Nếu icon cũ trỏ vào file không tồn tại (ví dụ thư mục Temp bị xóa) hoặc TargetPath khác
                if old_ico and not os.path.isfile(old_ico):
                    need_update = True
                elif existing.TargetPath.lower() == target_exe.lower() and existing.IconLocation == icon_loc:
                    need_update = False
            except Exception:
                need_update = True

        if need_update:
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.TargetPath = target_exe
            shortcut.Arguments = target_args
            shortcut.WorkingDirectory = target_dir
            shortcut.IconLocation = icon_loc
            shortcut.Save()

            store = propsys.SHGetPropertyStoreFromParsingName(shortcut_path, None, 2)
            if store:
                store.SetValue(pscon.PKEY_AppUserModel_ID, propsys.PROPVARIANTType("OmniGrab.VideoDownloader.1.0"))
                store.Commit()
    except Exception:
        pass


def _setup_windows_taskbar_icon(hwnd_id: int, ico_path: str) -> None:
    """Ép Windows Taskbar và Titlebar hiển thị Icon thông qua Win32 API và Shell Property Store."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        LR_DEFAULTSIZE = 0x00000040
        GCLP_HICON = -14
        GCLP_HICONSM = -34

        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32

        LoadImage = user32.LoadImageW
        LoadImage.argtypes = [
            wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
            ctypes.c_int, ctypes.c_int, wintypes.UINT
        ]
        LoadImage.restype = wintypes.HANDLE

        SendMessage = user32.SendMessageW
        SendMessage.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        SendMessage.restype = wintypes.LPARAM

        SetClassLongPtr = getattr(user32, "SetClassLongPtrW", None) or getattr(user32, "SetClassLongW", None)
        if SetClassLongPtr:
            SetClassLongPtr.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LPARAM]
            SetClassLongPtr.restype = wintypes.LPARAM

        hwnd = wintypes.HWND(hwnd_id)
        is_frozen = getattr(sys, "frozen", False)

        hicon_big = None
        hicon_small = None

        if is_frozen and sys.executable:
            # Trong file .exe: Trích xuất trực tiếp icon nhúng từ PE header
            try:
                h_big = wintypes.HICON()
                h_small = wintypes.HICON()
                shell32.ExtractIconExW.argtypes = [
                    wintypes.LPCWSTR, ctypes.c_int,
                    ctypes.POINTER(wintypes.HICON), ctypes.POINTER(wintypes.HICON),
                    wintypes.UINT
                ]
                shell32.ExtractIconExW.restype = wintypes.UINT
                n = shell32.ExtractIconExW(sys.executable, 0, ctypes.byref(h_big), ctypes.byref(h_small), 1)
                if n > 0:
                    hicon_big = h_big.value
                    hicon_small = h_small.value
            except Exception:
                pass
            relaunch_target = f"{os.path.abspath(sys.executable)},0"
        else:
            abs_path = os.path.abspath(ico_path)
            relaunch_target = f"{abs_path},0"

        # Dự phòng nạp từ file .ico nếu trích xuất PE chưa có
        if not hicon_big and os.path.isfile(ico_path):
            abs_path = os.path.abspath(ico_path)
            hicon_big = LoadImage(None, abs_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
            if not hicon_big:
                hicon_big = LoadImage(None, abs_path, IMAGE_ICON, 256, 256, LR_LOADFROMFILE)

        if not hicon_small and os.path.isfile(ico_path):
            abs_path = os.path.abspath(ico_path)
            hicon_small = LoadImage(None, abs_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
            if not hicon_small:
                hicon_small = LoadImage(None, abs_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)

        if hicon_big:
            SendMessage(hwnd, WM_SETICON, ICON_BIG, hicon_big)
            if SetClassLongPtr:
                SetClassLongPtr(hwnd, GCLP_HICON, hicon_big)
        if hicon_small:
            SendMessage(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
            if SetClassLongPtr:
                SetClassLongPtr(hwnd, GCLP_HICONSM, hicon_small)

        # 2. Gán Shell Property Store trực tiếp vào HWND cho Windows 10/11 Taskbar
        try:
            from win32com.propsys import propsys, pscon
            store = propsys.SHGetPropertyStoreForWindow(hwnd_id)
            if store:
                store.SetValue(pscon.PKEY_AppUserModel_ID, propsys.PROPVARIANTType("OmniGrab.VideoDownloader.1.0"))
                store.SetValue(pscon.PKEY_AppUserModel_RelaunchIconResource, propsys.PROPVARIANTType(relaunch_target))
                store.Commit()
        except Exception:
            pass

        # 3. Yêu cầu Windows Shell cập nhật thay đổi icon
        try:
            shell32.SHChangeNotify(0x08000000, 0x0000, None, None)  # SHCNE_ASSOCCHANGED
        except Exception:
            pass

    except Exception:
        pass


def main() -> None:
    """Khởi chạy ứng dụng OmniGrab."""
    # Kích hoạt các lớp bảo vệ trước khi nạp giao diện
    run_security_checks()

    # Bật DPI scaling cho màn hình độ phân giải cao
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)

    # Thiết lập icon ứng dụng (tương thích Nuitka/PyInstaller)
    _icon_ico = os.path.normpath(get_resource_path("assets/icon.ico"))
    _icon_png = os.path.normpath(get_resource_path("assets/icon.png"))
    _icon_path = _icon_ico if os.path.isfile(_icon_ico) else _icon_png

    if os.path.isfile(_icon_path):
        _ensure_windows_shortcut(_icon_path)
        app_icon = QIcon(_icon_path)
        app.setWindowIcon(app_icon)
    else:
        app_icon = QIcon()

    # Thiết lập font mặc định
    font = QFont("Segoe UI", 10)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    app.setFont(font)

    # Áp dụng Dark Theme
    app.setStyleSheet(get_app_stylesheet())

    # Tạo & hiển thị cửa sổ chính
    window = MainWindow()
    if not app_icon.isNull():
        window.setWindowIcon(app_icon)
    window.show()

    # Ép icon Windows Taskbar và Class Icon qua Win32 API sau khi show cửa sổ
    if os.path.isfile(_icon_path):
        _setup_windows_taskbar_icon(int(window.winId()), _icon_path)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
