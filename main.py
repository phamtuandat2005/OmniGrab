"""
main.py - Điểm khởi chạy ứng dụng OmniGrab.

Tải video hàng loạt từ TikTok, Douyin, Facebook.
"""

from __future__ import annotations

import os
import sys

# Vá tương thích PyAV 19+ cho faster-whisper
try:
    import av
    _orig_av_open = av.open

    def _safe_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)

    av.open = _safe_av_open
except Exception:
    pass

# pyrefly: ignore [missing-import]
from PyQt6.QtWidgets import QApplication
# pyrefly: ignore [missing-import]
from PyQt6.QtCore import Qt
# pyrefly: ignore [missing-import]
from PyQt6.QtGui import QFont, QIcon
# pyrefly: ignore [missing-import]
from ui.main_window import MainWindow
from ui.styles import get_app_stylesheet

from core.security import run_security_checks, get_resource_path


def main() -> None:
    """Khởi chạy ứng dụng OmniGrab."""
    
    # Kích hoạt các lớp bảo vệ trước khi nạp giao diện
    run_security_checks()
    
    # Đặt App User Model ID cho Windows — bắt buộc để taskbar hiển thị đúng icon
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("OmniGrab.VideoDownloader.1.0")
    except Exception:
        pass  # Không phải Windows, bỏ qua

    # Bật DPI scaling cho màn hình độ phân giải cao
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)

    # Thiết lập icon ứng dụng (tương thích Nuitka/PyInstaller)
    _icon_ico = get_resource_path("assets/icon.ico")
    _icon_png = get_resource_path("assets/icon.png")

    # Ưu tiên .ico (nhiều kích thước, Windows nhận tốt hơn), fallback .png
    _icon_path = _icon_ico if os.path.isfile(_icon_ico) else _icon_png
    if os.path.isfile(_icon_path):
        app_icon = QIcon(_icon_path)
        app.setWindowIcon(app_icon)

    # Thiết lập font mặc định
    font = QFont("Segoe UI", 10)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    app.setFont(font)

    # Áp dụng Dark Theme
    app.setStyleSheet(get_app_stylesheet())

    # Tạo & hiển thị cửa sổ chính
    window = MainWindow()
    if os.path.isfile(_icon_path):
        window.setWindowIcon(QIcon(_icon_path))
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
