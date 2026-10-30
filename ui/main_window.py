"""
ui/main_window.py — OmniGrab v4.0 Desktop
Giao diện hiện đại chuẩn VS Code với Menu Bar, QStackedWidget & DubbingDialog popup.

Layout:
  Cột trái  : QStackedWidget (Trang 0: Dán link | Trang 1: Quét kênh)
  Cột phải  : Tiến trình + Realtime Log
  Bottom    : QStatusBar với tóm tắt + nút BẮT ĐẦU TẢI

Ngôn ngữ giao diện: 100% Tiếng Việt.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# pyrefly: ignore [missing-import]
from PyQt6.QtCore import QByteArray, QRect, QSettings, Qt, QTimer, QUrl
# pyrefly: ignore [missing-import]
from PyQt6.QtGui import (
    QAction,
    QColor,
    QDesktopServices,
    QFont,
    QGuiApplication,
    QIcon,
    QKeySequence,
    QIntValidator,
    QTextCursor,
    QTextOption,
)
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
# pyrefly: ignore [missing-import]
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from core.dubber import DubConfig, DubSegment, check_dub_dependencies
from core.dub_worker import DubWorker
from core.license_manager import LicenseManager
from core.parser import extract_urls, read_urls_from_file
from core.security import get_resource_path
from core.update_checker import (
    GITHUB_RELEASE_API_URL,
    ReleaseUpdate,
    find_release_update,
)
from core.version import APP_VERSION
from core.worker import DownloadWorker, ScanChannelWorker
from ui.activation_dialog import ActivationDialog
from ui.cookie_dialog import CookieFailedDialog, CookieGuideDialog, CookiePromptDialog
from ui.dubbing_studio import DubbingStudioWidget
from ui.icons import get_svg_icon, get_svg_pixmap
from ui.styles import (
    COLORS,
    PLATFORM_COLORS,
    btn_primary_style,
    btn_secondary_style,
    btn_stop_style,
    card_style,
)
from ui.widgets import CollapsibleSection, TableEmptyState
from ui.video_gallery_dialog import VideoGalleryDialog

_SETTINGS_FILE = Path.home() / ".omnigrab_settings.json"


def _resolve_icon_path(rel_path: str) -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target = os.path.join(base, rel_path)
    return target if os.path.exists(target) else rel_path


# ══════════════════════════════════════════════════════════════════════
# DIALOG LỒNG TIẾNG AI — Popup độc lập
# ══════════════════════════════════════════════════════════════════════

class DubbingDialog(QDialog):
    """
    Popup cài đặt Lồng tiếng AI Tiếng Việt.
    Bật lên qua Menu Công cụ → Cài đặt Lồng tiếng AI (Ctrl+L).
    """

    def __init__(
        self,
        auto_dub: bool,
        src_lang: str,
        voice: str,
        bg_volume: int,
        voice_volume: int = 220,
        mute_original: bool = False,
        whisper_model: str = "base",
        gemini_api_key: str = "",
        auto_open_dubbed: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cài đặt & Lồng tiếng AI Tiếng Việt")
        self.setMinimumWidth(600)
        self.setModal(True)

        # Lưu giá trị trả về
        self.result_auto_dub = auto_dub
        self.result_auto_open_dubbed = auto_open_dubbed
        self.result_src_lang = src_lang
        self.result_voice = voice
        self.result_bg_volume = bg_volume
        self.result_voice_volume = voice_volume
        self.result_mute_original = mute_original
        self.result_whisper_model = whisper_model
        self.result_gemini_api_key = gemini_api_key

        self._build_ui(
            auto_dub, src_lang, voice, bg_volume, voice_volume, mute_original,
            whisper_model, gemini_api_key, auto_open_dubbed
        )

    # ─────────────── Build UI ───────────────

    def _build_ui(
        self,
        auto_dub: bool,
        src_lang: str,
        voice: str,
        bg_volume: int,
        voice_volume: int,
        mute_original: bool,
        whisper_model: str,
        gemini_api_key: str = "",
        auto_open_dubbed: bool = True,
    ) -> None:
        c = COLORS
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c['bg_secondary']};
            }}
            QLabel {{
                color: {c['text_primary']};
                background: transparent;
            }}
            QCheckBox {{
                color: {c['text_secondary']};
                font-size: 13px;
            }}
            QComboBox, QSpinBox, QLineEdit {{
                background-color: {c['bg_input']};
                color: {c['text_primary']};
                border: 1px solid {c['bg_input_border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QComboBox:focus, QSpinBox:focus, QLineEdit:focus {{
                border-color: {c['border_focus']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QSlider::groove:horizontal {{
                background: {c['border']};
                height: 6px;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {c['accent_blue']};
                width: 16px;
                height: 16px;
                border-radius: 8px;
                margin: -5px 0;
            }}
            QSlider::sub-page:horizontal {{
                background: {c['accent_blue']};
                border-radius: 3px;
            }}
            QPushButton {{
                background-color: {c['btn_secondary_bg']};
                color: {c['text_primary']};
                border: 1px solid {c['btn_outline_border']};
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {c['btn_secondary_hover']};
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(18)

        # ── Header ──
        lbl_header = QLabel("Cài đặt Module Lồng tiếng AI")
        lbl_header.setStyleSheet(
            f"font-size:16px; font-weight:700; color:{c['text_primary']};"
        )
        root.addWidget(lbl_header)

        sep = self._make_sep()
        root.addWidget(sep)

        # ── Checkbox bật/tắt ──
        self._chk_auto = QCheckBox(
            "Tự động lồng tiếng Tiếng Việt sau khi tải video MP4 xong"
        )
        self._chk_auto.setChecked(auto_dub)
        root.addWidget(self._chk_auto)

        self._chk_auto_open = QCheckBox(
            "Tự động mở video sau khi lồng tiếng / dịch xong"
        )
        self._chk_auto_open.setChecked(auto_open_dubbed)
        root.addWidget(self._chk_auto_open)

        # ── Grid cài đặt ──
        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(12)

        # Ngôn ngữ gốc
        grid.addWidget(self._lbl("Ngôn ngữ video gốc:"), 0, 0)
        self._combo_lang = QComboBox()
        self._combo_lang.addItem("Tiếng Trung (Douyin)", "zh-CN")
        self._combo_lang.addItem("Tiếng Anh (TikTok / Facebook)", "en")
        self._combo_lang.addItem("Tiếng Nhật", "ja")
        self._combo_lang.addItem("Tiếng Hàn", "ko")
        # Chọn ngôn ngữ hiện tại
        idx = self._combo_lang.findData(src_lang)
        if idx < 0 and src_lang in ("zh", "zh-TW", "zh-CN"):
            idx = self._combo_lang.findData("zh-CN")
        if idx >= 0:
            self._combo_lang.setCurrentIndex(idx)
        grid.addWidget(self._combo_lang, 0, 1)

        # Giọng đọc
        grid.addWidget(self._lbl("Giọng đọc AI:"), 1, 0)
        self._combo_voice = QComboBox()
        self._combo_voice.addItem("Giọng Google Tiếng Việt (Chuẩn, tốc độ cao)", "vi")
        idx_v = self._combo_voice.findData(voice)
        if idx_v >= 0:
            self._combo_voice.setCurrentIndex(idx_v)
        else:
            self._combo_voice.setCurrentIndex(0)
        grid.addWidget(self._combo_voice, 1, 1)

        # Whisper model
        grid.addWidget(self._lbl("Độ chính xác nhận diện:"), 2, 0)
        self._combo_model = QComboBox()
        self._combo_model.addItem("tiny — Nhanh nhất", "tiny")
        self._combo_model.addItem("base — Cân bằng (khuyến nghị)", "base")
        self._combo_model.addItem("medium — Chính xác cao nhất (nét)", "medium")
        idx_m = self._combo_model.findData(whisper_model)
        if idx_m >= 0:
            self._combo_model.setCurrentIndex(idx_m)
        grid.addWidget(self._combo_model, 2, 1)

        # Âm lượng giọng đọc AI
        grid.addWidget(self._lbl("Âm lượng giọng đọc:"), 3, 0)
        v_vol_row = QHBoxLayout()
        self._slider_voice_vol = QSlider(Qt.Orientation.Horizontal)
        self._slider_voice_vol.setRange(100, 300)
        self._slider_voice_vol.setValue(voice_volume)
        self._slider_voice_vol.setToolTip("100% = gốc | 220% = chuẩn phòng thu kèm loudnorm | 300% = tối đa")
        self._lbl_voice_vol = QLabel(f"{voice_volume}%")
        self._lbl_voice_vol.setStyleSheet(
            f"color:{c['status_success']}; font-weight:700; min-width:40px;"
        )
        self._slider_voice_vol.valueChanged.connect(
            lambda v: self._lbl_voice_vol.setText(f"{v}%")
        )
        v_vol_row.addWidget(self._slider_voice_vol)
        v_vol_row.addWidget(self._lbl_voice_vol)
        v_vol_w = QWidget()
        v_vol_w.setLayout(v_vol_row)
        grid.addWidget(v_vol_w, 3, 1)

        # Âm lượng video gốc / Nhạc nền
        grid.addWidget(self._lbl("Âm lượng video gốc:"), 4, 0)
        bg_vol_row = QHBoxLayout()
        self._slider_vol = QSlider(Qt.Orientation.Horizontal)
        self._slider_vol.setRange(0, 50)
        self._slider_vol.setValue(bg_volume)
        self._slider_vol.setToolTip("0% = tắt tiếng gốc | 10% = chuẩn nền êm dịu | 50% = tiếng gốc to")
        self._lbl_vol = QLabel("0% (Đã tắt)" if mute_original else f"{bg_volume}%")
        self._lbl_vol.setStyleSheet(
            f"color:{c['status_warning']}; font-weight:700; min-width:50px;"
        )
        self._slider_vol.valueChanged.connect(self._on_slider_bg_changed)
        bg_vol_row.addWidget(self._slider_vol)
        bg_vol_row.addWidget(self._lbl_vol)

        self._chk_mute_orig = QCheckBox("Tắt hẳn tiếng gốc")
        self._chk_mute_orig.setChecked(mute_original)
        self._chk_mute_orig.setToolTip("Khi tích chọn, âm lượng video gốc sẽ về 0% (chỉ giữ hình ảnh và giọng thuyết minh)")
        self._chk_mute_orig.toggled.connect(self._on_mute_toggled)
        bg_vol_row.addWidget(self._chk_mute_orig)

        if mute_original:
            self._slider_vol.setEnabled(False)

        bg_vol_w = QWidget()
        bg_vol_w.setLayout(bg_vol_row)
        grid.addWidget(bg_vol_w, 4, 1)

        # Gemini API Key
        grid.addWidget(self._lbl("Gemini API Key (Miễn phí):"), 5, 0)
        key_box = QVBoxLayout()
        key_box.setSpacing(4)

        key_row = QHBoxLayout()
        key_row.setSpacing(6)

        self._txt_key = QLineEdit()
        self._txt_key.setPlaceholderText("Dán Gemini API Key từ Google AI Studio (AIzaSy...)")
        self._txt_key.setText(gemini_api_key)
        self._txt_key.setEchoMode(QLineEdit.EchoMode.Password)
        key_row.addWidget(self._txt_key, 1)

        self._btn_toggle_key = QPushButton("")
        self._btn_toggle_key.setIcon(get_svg_icon("eye"))
        self._btn_toggle_key.setToolTip("Ẩn/Hiện API Key")
        self._btn_toggle_key.setFixedWidth(36)
        self._btn_toggle_key.setStyleSheet(btn_secondary_style())
        self._btn_toggle_key.clicked.connect(self._toggle_key_visibility)
        key_row.addWidget(self._btn_toggle_key)

        btn_get_key = QPushButton("Lấy API Key")
        btn_get_key.setIcon(get_svg_icon("external-link"))
        btn_get_key.setToolTip("Mở Google AI Studio để lấy API Key miễn phí 0đ")
        btn_get_key.setStyleSheet(btn_secondary_style())
        btn_get_key.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://aistudio.google.com/app/apikey"))
        )
        key_row.addWidget(btn_get_key)

        key_w = QWidget()
        key_w.setLayout(key_row)
        key_box.addWidget(key_w)

        lbl_hint = QLabel("Miễn phí từ Google AI Studio, dịch nhanh, tự động phân tích ngữ cảnh phim.")
        lbl_hint.setStyleSheet(f"color:{c['text_muted']}; font-size:11px;")
        key_box.addWidget(lbl_hint)

        key_container = QWidget()
        key_container.setLayout(key_box)
        grid.addWidget(key_container, 4, 1)

        grid.setColumnStretch(1, 1)
        root.addLayout(grid)

        # ── Trạng thái thư viện ──
        sep2 = self._make_sep()
        root.addWidget(sep2)
        self._lbl_dep_status = QLabel("Đang kiểm tra thư viện...")
        self._lbl_dep_status.setStyleSheet(
            f"color:{c['text_muted']}; font-size:12px;"
        )
        root.addWidget(self._lbl_dep_status)
        QTimer.singleShot(100, self._check_deps)

        # ── Nút Lưu & Áp dụng ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("Hủy bỏ")
        btn_cancel.setStyleSheet(btn_secondary_style())
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_save = QPushButton("Lưu & Áp dụng")
        btn_save.setIcon(get_svg_icon("check"))
        btn_save.setStyleSheet(btn_primary_style())
        btn_save.clicked.connect(self._save_and_accept)
        btn_row.addWidget(btn_save)
        root.addLayout(btn_row)

    # ─────────────── Helpers ───────────────

    def _toggle_key_visibility(self) -> None:
        if self._txt_key.echoMode() == QLineEdit.EchoMode.Password:
            self._txt_key.setEchoMode(QLineEdit.EchoMode.Normal)
            self._btn_toggle_key.setIcon(get_svg_icon("key"))
        else:
            self._txt_key.setEchoMode(QLineEdit.EchoMode.Password)
            self._btn_toggle_key.setIcon(get_svg_icon("eye"))

    def _lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{COLORS['text_secondary']}; font-size:13px;")
        return lbl

    def _make_sep(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background:{COLORS['border']}; max-height:1px;")
        return sep

    def _check_deps(self) -> None:
        c = COLORS
        try:
            deps = check_dub_dependencies()
            missing = [k for k, v in deps.items() if not v]
            if not missing:
                self._lbl_dep_status.setText("Tất cả thư viện sẵn sàng — có thể lồng tiếng ngay")
                self._lbl_dep_status.setStyleSheet(
                    f"color:{c['status_success']}; font-size:12px; font-weight:600;"
                )
            else:
                self._lbl_dep_status.setText(
                    f"Chưa cài đặt: {', '.join(missing)}. "
                    "Chạy: pip install faster-whisper gTTS requests pydub"
                )
                self._lbl_dep_status.setStyleSheet(
                    f"color:{c['status_warning']}; font-size:12px; font-weight:600;"
                )
        except Exception:
            self._lbl_dep_status.setText("Không kiểm tra được thư viện")

    def _on_slider_bg_changed(self, v: int) -> None:
        if not self._chk_mute_orig.isChecked():
            self._lbl_vol.setText(f"{v}%")

    def _on_mute_toggled(self, checked: bool) -> None:
        if checked:
            self._slider_vol.setEnabled(False)
            self._lbl_vol.setText("0% (Đã tắt)")
        else:
            self._slider_vol.setEnabled(True)
            self._lbl_vol.setText(f"{self._slider_vol.value()}%")

    def _save_and_accept(self) -> None:
        self.result_auto_dub = self._chk_auto.isChecked()
        self.result_auto_open_dubbed = self._chk_auto_open.isChecked()
        self.result_src_lang = self._combo_lang.currentData() or "zh-CN"
        self.result_voice = self._combo_voice.currentData() or "vi"
        self.result_voice_volume = self._slider_voice_vol.value()
        self.result_mute_original = self._chk_mute_orig.isChecked()
        self.result_bg_volume = 0 if self._chk_mute_orig.isChecked() else self._slider_vol.value()
        self.result_whisper_model = self._combo_model.currentData() or "base"
        self.result_gemini_api_key = self._txt_key.text().strip()
        self.accept()


# ══════════════════════════════════════════════════════════════════════
# CỬA SỔ CHÍNH
# ══════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    """Cửa sổ giao diện chính OmniGrab v4.0 — layout chuẩn VS Code."""

    # ────────── Trang QStackedWidget ──────────
    PAGE_LINKS = 0
    PAGE_CHANNEL = 1
    PAGE_STUDIO = 2

    def __init__(self) -> None:
        super().__init__()

        # ── Trạng thái hệ thống ──
        self._worker: Optional[DownloadWorker] = None
        self._scan_worker: Optional[ScanChannelWorker] = None
        self._dub_worker: Optional[DubWorker] = None
        self.dubbing_worker: Optional[DubWorker] = None

        self._is_downloading = False
        self._is_scanning = False
        self._is_dubbing = False

        self._total_urls = 0
        self._success_count = 0
        self._fail_count = 0
        self._active_count = 0
        self._failed_urls: List[str] = []
        self._scanned_videos: List[Dict[str, Any]] = []

        # ── Bản quyền ──
        self._license_manager = LicenseManager()

        # ── Cấu hình người dùng (đồng bộ với DubbingDialog) ──
        self.output_dir: str = str(Path.home() / "Videos" / "OmniGrab_Downloads")
        self.cookies_path: str = ""
        self.auto_dub: bool = False
        self.dub_lang: str = "zh-CN"
        self.dub_voice: str = "vi"
        self.bg_volume: int = 10              # % (0-50, mặc định 10)
        self.voice_volume: int = 220          # % (100-300, mặc định 220)
        self.mute_original: bool = False
        self.whisper_model: str = "base"
        self.gemini_api_key: str = ""
        self.max_workers: int = 3
        self.auto_open_dubbed: bool = True
        self.auto_upload_tiktok: bool = False
        self.tiktok_privacy: str = "public"
        self.tiktok_delay_minutes: int = 45
        self.tiktok_cookies_path: str = ""
        self.tiktok_headless: bool = False
        self.auto_upload_youtube: bool = False
        self.youtube_privacy: str = "public"
        self.youtube_cookies_path: str = "youtube_cookies.txt"
        self.youtube_client_secrets: str = "client_secret.json"
        self.youtube_schedule_enabled: bool = False
        self.youtube_schedule_date: str = ""
        self.youtube_schedule_time: str = ""
        self.youtube_scheduled_time_str: str = ""
        self.youtube_default_tags: str = "Shorts, AI, PhimHay, ReviewPhim"
        self.active_page: int = self.PAGE_LINKS
        self.studio_last_video: str = ""
        self._saved_screen_name: str = ""
        self._saved_screen_idx: int = 0
        self._saved_window_w: int = 1280
        self._saved_window_h: int = 760
        self._saved_is_maximized: bool = False
        self._first_show_done: bool = False
        self._update_manager = QNetworkAccessManager(self)
        self._update_reply: Optional[QNetworkReply] = None
        self._manual_update_check = False

        # Nạp cài đặt đã lưu từ phiên trước
        self._load_settings()

        # Tạo thư mục lưu video
        try:
            os.makedirs(self.output_dir, exist_ok=True)
        except OSError:
            self.output_dir = str(Path.home() / "Downloads")

        self._setup_window()
        self._build_menubar()
        self._build_central()
        self._build_statusbar()
        self._connect_signals()
        self._refresh_statusbar()
        self._update_license_statusbar()
        self._update_cookie_ui()
        self._restore_active_page()
        self._append_log(
            "HỆ THỐNG",
            f"OmniGrab v{APP_VERSION} sẵn sàng. Dán link vào ô nhập hoặc vào Chế độ tải → Quét kênh.",
        )
        QTimer.singleShot(2500, self._check_for_updates_automatically)

    # ══════════════════════════════════════════════════════════════════
    # CẤU HÌNH NGƯỜI DÙNG (PERSISTENCE)
    # ══════════════════════════════════════════════════════════════════

    def _load_settings(self) -> None:
        """Nạp cấu hình đã lưu từ JSON / QSettings."""
        data: Dict[str, Any] = {}
        if _SETTINGS_FILE.is_file():
            try:
                with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}

        qs = QSettings("OmniGrab", "OmniGrab")

        # 1. Tự động lồng tiếng
        if "auto_dub" in data:
            self.auto_dub = bool(data["auto_dub"])
        else:
            self.auto_dub = qs.value("auto_dub", False, type=bool)

        # 2. Ngôn ngữ gốc video
        self.dub_lang = str(data.get("dub_lang") or qs.value("dub_lang", "zh-CN", type=str) or "zh-CN")

        # 3. Giọng đọc gTTS
        saved_voice = str(data.get("dub_voice") or qs.value("dub_voice", "vi", type=str) or "vi")
        self.dub_voice = "vi" if ("hoaimy" in saved_voice.lower() or "neural" in saved_voice.lower()) else saved_voice

        # 4. Âm lượng video gốc / Ducking
        raw_vol = data.get("bg_volume") if "bg_volume" in data else qs.value("bg_volume", 10, type=int)
        try:
            self.bg_volume = max(0, min(50, int(raw_vol)))
        except (ValueError, TypeError):
            self.bg_volume = 10

        # Âm lượng giọng đọc (100% - 300%, mặc định 220%)
        raw_voice_vol = data.get("voice_volume") if "voice_volume" in data else qs.value("voice_volume", 220, type=int)
        try:
            self.voice_volume = max(100, min(300, int(raw_voice_vol)))
        except (ValueError, TypeError):
            self.voice_volume = 220

        # Tắt hẳn âm thanh gốc
        if "mute_original" in data:
            self.mute_original = bool(data["mute_original"])
        else:
            self.mute_original = qs.value("mute_original", False, type=bool)

        # 5. Whisper Model
        self.whisper_model = str(data.get("whisper_model") or qs.value("whisper_model", "base", type=str) or "base")

        # 6. Thư mục lưu
        saved_dir = str(data.get("output_dir") or qs.value("output_dir", "", type=str) or "")
        if saved_dir and os.path.isdir(saved_dir):
            self.output_dir = saved_dir

        # 7. File Cookie
        saved_cookie = str(data.get("cookies_path") or qs.value("cookies_path", "", type=str) or "")
        if saved_cookie and os.path.isfile(saved_cookie):
            self.cookies_path = saved_cookie

        # 8. Số luồng tải đồng thời
        raw_workers = data.get("max_workers") if "max_workers" in data else qs.value("max_workers", 3, type=int)
        try:
            self.max_workers = max(1, min(10, int(raw_workers)))
        except (ValueError, TypeError):
            self.max_workers = 3

        # 9. Gemini API Key (Miễn phí 0đ)
        self.gemini_api_key = str(data.get("gemini_api_key") or qs.value("gemini_api_key", "", type=str) or "")

        # 10. Màn hình làm việc (Chế độ tải / Studio)
        raw_page = data.get("active_page") if "active_page" in data else qs.value("active_page", self.PAGE_LINKS, type=int)
        try:
            self.active_page = int(raw_page)
        except (ValueError, TypeError):
            self.active_page = self.PAGE_LINKS
        if self.active_page not in (self.PAGE_LINKS, self.PAGE_CHANNEL, self.PAGE_STUDIO):
            self.active_page = self.PAGE_LINKS

        self.studio_last_video = str(data.get("studio_last_video") or qs.value("studio_last_video", "", type=str) or "")

        # 11. Màn hình máy tính & kích thước
        self._saved_window_w = data.get("window_w") if "window_w" in data else qs.value("window_w", 1280, type=int)
        self._saved_window_h = data.get("window_h") if "window_h" in data else qs.value("window_h", 760, type=int)
        self._saved_is_maximized = bool(data.get("is_maximized") if "is_maximized" in data else qs.value("is_maximized", False, type=bool))
        self._saved_screen_name = str(data.get("screen_name") or qs.value("screen_name", "", type=str) or "")
        self._saved_screen_idx = data.get("screen_idx") if "screen_idx" in data else qs.value("screen_idx", 0, type=int)

        # 12. Tự động mở video sau khi lồng tiếng / dịch xong
        if "auto_open_dubbed" in data:
            self.auto_open_dubbed = bool(data["auto_open_dubbed"])
        else:
            self.auto_open_dubbed = qs.value("auto_open_dubbed", True, type=bool)

        # 13. Cấu hình tự động đăng TikTok
        self.auto_upload_tiktok = bool(data.get("auto_upload_tiktok") if "auto_upload_tiktok" in data else qs.value("auto_upload_tiktok", False, type=bool))
        self.tiktok_privacy = str(data.get("tiktok_privacy") or qs.value("tiktok_privacy", "public", type=str) or "public")
        raw_tt_delay = data.get("tiktok_delay_minutes") if "tiktok_delay_minutes" in data else qs.value("tiktok_delay_minutes", 45, type=int)
        try:
            self.tiktok_delay_minutes = max(1, min(180, int(raw_tt_delay)))
        except (ValueError, TypeError):
            self.tiktok_delay_minutes = 45
        saved_tt_cookie = str(data.get("tiktok_cookies_path") or qs.value("tiktok_cookies_path", "", type=str) or "")
        self.tiktok_cookies_path = saved_tt_cookie if (saved_tt_cookie and os.path.isfile(saved_tt_cookie)) else ""
        self.tiktok_headless = bool(data.get("tiktok_headless") if "tiktok_headless" in data else qs.value("tiktok_headless", False, type=bool))

        # 14. Cấu hình tự động đăng YouTube Shorts
        self.auto_upload_youtube = bool(data.get("auto_upload_youtube") if "auto_upload_youtube" in data else qs.value("auto_upload_youtube", False, type=bool))
        self.youtube_privacy = str(data.get("youtube_privacy") or qs.value("youtube_privacy", "public", type=str) or "public")
        self.youtube_cookies_path = str(data.get("youtube_cookies_path") or data.get("youtube_client_secrets") or qs.value("youtube_cookies_path", "youtube_cookies.txt", type=str) or "youtube_cookies.txt")
        self.youtube_client_secrets = str(data.get("youtube_client_secrets") or qs.value("youtube_client_secrets", "client_secret.json", type=str) or "client_secret.json")
        self.youtube_schedule_enabled = bool(data.get("youtube_schedule_enabled") if "youtube_schedule_enabled" in data else qs.value("youtube_schedule_enabled", False, type=bool))
        self.youtube_schedule_date = str(data.get("youtube_schedule_date") or qs.value("youtube_schedule_date", "", type=str) or "")
        self.youtube_schedule_time = str(data.get("youtube_schedule_time") or qs.value("youtube_schedule_time", "", type=str) or "")
        self.youtube_scheduled_time_str = str(data.get("youtube_scheduled_time_str") or qs.value("youtube_scheduled_time_str", "", type=str) or "")
        self.youtube_default_tags = str(data.get("youtube_default_tags") or qs.value("youtube_default_tags", "Shorts, AI, PhimHay, ReviewPhim", type=str) or "Shorts, AI, PhimHay, ReviewPhim")

    def _save_settings(self) -> None:
        """Lưu toàn bộ cài đặt người dùng vào JSON và QSettings."""
        # 1. Thu thập trang làm việc hiện tại
        cur_page = self.PAGE_LINKS
        if hasattr(self, "_stack") and self._stack is not None:
            cur_page = self._stack.currentIndex()
        elif hasattr(self, "active_page"):
            cur_page = self.active_page

        studio_vid = getattr(self, "studio_last_video", "")
        if hasattr(self, "studio_widget") and self.studio_widget and getattr(self.studio_widget, "current_video_path", ""):
            cur_vid = self.studio_widget.current_video_path
            if os.path.isfile(cur_vid):
                studio_vid = cur_vid

        # 2. Thu thập kích thước cửa sổ và màn hình máy tính hiện tại
        is_max = getattr(self, "_saved_is_maximized", False)
        win_w = getattr(self, "_saved_window_w", 1280)
        win_h = getattr(self, "_saved_window_h", 760)

        try:
            if self.isVisible() or self.width() > 0:
                is_max = self.isMaximized()
                normal_geo = self.normalGeometry() if is_max else self.geometry()
                win_w = normal_geo.width()
                win_h = normal_geo.height()
        except Exception:
            pass

        screen_name = ""
        screen_idx = 0
        try:
            screen = self.screen() or QGuiApplication.primaryScreen()
            if screen:
                screen_name = screen.name()
                screens = QGuiApplication.screens()
                for idx, s in enumerate(screens):
                    if s.name() == screen.name():
                        screen_idx = idx
                        break
        except Exception:
            pass

        payload = {
            "auto_dub": self.auto_dub,
            "dub_lang": self.dub_lang,
            "dub_voice": self.dub_voice,
            "bg_volume": self.bg_volume,
            "voice_volume": getattr(self, "voice_volume", 220),
            "mute_original": getattr(self, "mute_original", False),
            "whisper_model": self.whisper_model,
            "gemini_api_key": self.gemini_api_key,
            "output_dir": self.output_dir,
            "cookies_path": self.cookies_path,
            "max_workers": self.max_workers,
            "auto_open_dubbed": getattr(self, "auto_open_dubbed", True),
            "auto_upload_tiktok": getattr(self, "auto_upload_tiktok", False),
            "tiktok_privacy": getattr(self, "tiktok_privacy", "public"),
            "tiktok_delay_minutes": getattr(self, "tiktok_delay_minutes", 45),
            "tiktok_cookies_path": getattr(self, "tiktok_cookies_path", ""),
            "tiktok_headless": getattr(self, "tiktok_headless", True),
            "auto_upload_youtube": getattr(self, "auto_upload_youtube", False),
            "youtube_privacy": getattr(self, "youtube_privacy", "public"),
            "youtube_cookies_path": getattr(self, "youtube_cookies_path", "youtube_cookies.txt"),
            "youtube_client_secrets": getattr(self, "youtube_client_secrets", "client_secret.json"),
            "youtube_schedule_enabled": getattr(self, "youtube_schedule_enabled", False),
            "youtube_schedule_date": getattr(self, "youtube_schedule_date", ""),
            "youtube_schedule_time": getattr(self, "youtube_schedule_time", ""),
            "youtube_scheduled_time_str": getattr(self, "youtube_scheduled_time_str", ""),
            "youtube_default_tags": getattr(self, "youtube_default_tags", "Shorts, AI, PhimHay, ReviewPhim"),
            "active_page": cur_page,
            "studio_last_video": studio_vid,
            "window_w": win_w,
            "window_h": win_h,
            "is_maximized": is_max,
            "screen_name": screen_name,
            "screen_idx": screen_idx,
        }
        # Cập nhật cache nội bộ
        self.active_page = cur_page
        self.studio_last_video = studio_vid
        self._saved_is_maximized = is_max
        self._saved_window_w = win_w
        self._saved_window_h = win_h
        self._saved_screen_name = screen_name
        self._saved_screen_idx = screen_idx

        # Lưu ra file JSON
        try:
            with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        # Lưu đồng bộ vào QSettings
        try:
            qs = QSettings("OmniGrab", "OmniGrab")
            for k, v in payload.items():
                if v is not None:
                    qs.setValue(k, v)
            qs.sync()
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════
    # THIẾT LẬP CỬA SỔ
    # ══════════════════════════════════════════════════════════════════

    def _setup_window(self) -> None:
        self.setWindowTitle(
            "OmniGrab v4.0 — Tải & Lồng tiếng AI Tiếng Việt"
            " | TikTok · Douyin · Facebook · YouTube"
        )
        self.setMinimumSize(1100, 660)

        # Thiết lập Icon cho cửa sổ và Taskbar
        ico_path = os.path.normpath(get_resource_path("assets/icon.ico"))
        png_path = os.path.normpath(get_resource_path("assets/icon.png"))
        target_icon = ico_path if os.path.isfile(ico_path) else png_path
        if os.path.isfile(target_icon):
            self.setWindowIcon(QIcon(target_icon))

        # Luôn căn cửa sổ vào chính giữa màn hình máy tính
        self._center_window()

    def _center_window(self) -> None:
        """Căn cửa sổ vào chính giữa màn hình máy tính (hỗ trợ đa màn hình)."""
        screens = QGuiApplication.screens()
        if not screens:
            self.resize(1280, 760)
            return

        # Xác định màn hình mục tiêu (từ cấu hình phiên trước nếu có nhiều màn hình)
        target_screen = None
        saved_name = getattr(self, "_saved_screen_name", "")
        saved_idx = getattr(self, "_saved_screen_idx", -1)

        if saved_name:
            for s in screens:
                if s.name() == saved_name:
                    target_screen = s
                    break

        if not target_screen and 0 <= saved_idx < len(screens):
            target_screen = screens[saved_idx]

        if not target_screen:
            target_screen = QGuiApplication.primaryScreen() or screens[0]

        avail = target_screen.availableGeometry()

        # Đặt kích thước phù hợp
        w = max(1100, int(getattr(self, "_saved_window_w", 1280) or 1280))
        h = max(660, int(getattr(self, "_saved_window_h", 760) or 760))
        w = min(w, avail.width() - 40)
        h = min(h, avail.height() - 40)
        self.resize(w, h)

        # Căn chính xác tâm màn hình
        center_x = avail.x() + (avail.width() - w) // 2
        center_y = avail.y() + (avail.height() - h) // 2
        self.move(center_x, center_y)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not getattr(self, "_first_show_done", False):
            self._first_show_done = True
            # Nếu trước đó phóng to toàn màn hình, khôi phục maximized
            if getattr(self, "_saved_is_maximized", False):
                self.showMaximized()
            else:
                # Căn giữa màn hình sau khi hệ điều hành hiển thị cửa sổ
                self._center_window()

    # ══════════════════════════════════════════════════════════════════
    # MENU BAR
    # ══════════════════════════════════════════════════════════════════

    def _build_menubar(self) -> None:
        c = COLORS
        bar = self.menuBar()
        assert bar is not None
        bar.setStyleSheet(f"""
            QMenuBar {{
                background-color: {c['bg_secondary']};
                color: {c['text_primary']};
                border-bottom: 1px solid {c['border']};
                padding: 2px 4px;
                font-size: 13px;
            }}
            QMenuBar::item {{
                background: transparent;
                padding: 6px 14px;
                border-radius: 4px;
            }}
            QMenuBar::item:selected {{
                background-color: {c['btn_secondary_hover']};
            }}
            QMenu {{
                background-color: {c['bg_card']};
                color: {c['text_primary']};
                border: 1px solid {c['border']};
                border-radius: 6px;
                padding: 4px;
                font-size: 13px;
            }}
            QMenu::item {{
                padding: 8px 24px 8px 16px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {c['btn_secondary_hover']};
            }}
            QMenu::separator {{
                height: 1px;
                background: {c['border']};
                margin: 4px 8px;
            }}
            QMenu::item:disabled {{
                color: {c['text_placeholder']};
            }}
        """)

        # ── 1. Tệp ──
        menu_file = bar.addMenu("Tệp")

        act_output = QAction("Thư mục lưu video...", self)
        act_output.triggered.connect(self._on_choose_output_dir)
        menu_file.addAction(act_output)

        act_view_downloads = QAction("Xem video đã tải xuống...", self)
        act_view_downloads.triggered.connect(lambda: self.open_downloaded_videos_gallery())
        menu_file.addAction(act_view_downloads)

        act_cookie = QAction("Nạp file Cookie (.txt)...", self)
        act_cookie.triggered.connect(self._on_choose_cookie)
        menu_file.addAction(act_cookie)

        act_import = QAction("Nhập danh sách link từ file...", self)
        act_import.triggered.connect(self._on_import_file)
        menu_file.addAction(act_import)

        menu_file.addSeparator()

        act_quit = QAction("Thoát", self)
        act_quit.setShortcut(QKeySequence("Alt+F4"))
        act_quit.triggered.connect(self.close)
        menu_file.addAction(act_quit)

        # ── 2. Chế độ tải ──
        menu_mode = bar.addMenu("Chế độ tải")

        act_links = QAction("1. Tải theo danh sách liên kết", self)
        act_links.setShortcut(QKeySequence("Ctrl+1"))
        act_links.triggered.connect(lambda: self._switch_page(self.PAGE_LINKS))
        menu_mode.addAction(act_links)

        act_channel = QAction("2. Quét & Tải theo Kênh / Hồ sơ", self)
        act_channel.setShortcut(QKeySequence("Ctrl+2"))
        act_channel.triggered.connect(lambda: self._switch_page(self.PAGE_CHANNEL))
        menu_mode.addAction(act_channel)

        act_studio = QAction("3. Studio Lồng tiếng & Soát kịch bản", self)
        act_studio.setShortcut(QKeySequence("Ctrl+3"))
        act_studio.triggered.connect(lambda: self._switch_page(self.PAGE_STUDIO))
        menu_mode.addAction(act_studio)

        # ── 3. Công cụ ──
        menu_tools = bar.addMenu("Công cụ")

        act_gallery = QAction("Xem video đã tải xuống...", self)
        act_gallery.setShortcut(QKeySequence("Ctrl+4"))
        act_gallery.triggered.connect(lambda: self.open_downloaded_videos_gallery())
        menu_tools.addAction(act_gallery)

        menu_tools.addSeparator()

        act_threads = QAction("Cài đặt số luồng tải đồng thời...", self)
        act_threads.triggered.connect(self._on_set_threads)
        menu_tools.addAction(act_threads)

        act_dub_settings = QAction("Cài đặt Lồng tiếng AI...", self)
        act_dub_settings.setShortcut(QKeySequence("Ctrl+L"))
        act_dub_settings.triggered.connect(self._on_open_dub_dialog)
        menu_tools.addAction(act_dub_settings)

        act_mix_settings = QAction("Cài đặt Tỷ lệ Hòa âm (Voice & Nhạc nền)...", self)
        act_mix_settings.triggered.connect(self._on_open_audio_mix_dialog)
        menu_tools.addAction(act_mix_settings)

        act_tiktok_settings = QAction("Cài đặt Tự động Đăng TikTok...", self)
        act_tiktok_settings.triggered.connect(self._on_open_tiktok_dialog)

        act_youtube_settings = QAction("Cài đặt Tự động Đăng & Hẹn giờ YouTube...", self)
        act_youtube_settings.triggered.connect(self._on_open_youtube_dialog)

        menu_upload_settings = menu_tools.addMenu("Cài đặt đăng video")
        menu_upload_settings.addAction(act_tiktok_settings)
        menu_upload_settings.addAction(act_youtube_settings)

        act_dub_file = QAction("Lồng tiếng file MP4 có sẵn trên máy...", self)
        act_dub_file.triggered.connect(self._on_dub_manual)
        menu_tools.addAction(act_dub_file)

        menu_tools.addSeparator()

        act_update = QAction("Cập nhật lõi yt-dlp & FFmpeg", self)
        act_update.triggered.connect(self._on_update_tools)
        menu_tools.addAction(act_update)

        # ── 4. Trợ giúp ──
        menu_help = bar.addMenu("Trợ giúp")

        act_activate = QAction("Kích hoạt bản quyền...", self)
        act_activate.triggered.connect(self._on_open_activation_dialog)
        menu_help.addAction(act_activate)

        menu_help.addSeparator()

        act_check_updates = QAction("Kiểm tra cập nhật...", self)
        act_check_updates.triggered.connect(self._check_for_updates_manually)
        menu_help.addAction(act_check_updates)

        act_about = QAction("Thông tin phần mềm (About)", self)
        act_about.triggered.connect(self._on_about)
        menu_help.addAction(act_about)

        act_guide = QAction("Hướng dẫn sử dụng", self)
        act_guide.triggered.connect(self._on_guide)
        menu_help.addAction(act_guide)

    # ══════════════════════════════════════════════════════════════════
    # GIAO DIỆN CHÍNH (Central Widget)
    # ══════════════════════════════════════════════════════════════════

    def _build_central(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(10)

        # ── Cột trái: QStackedWidget ──
        self._stack = QStackedWidget()
        self.stacked_widget = self._stack  # Alias thuận tiện
        self.studio_widget = DubbingStudioWidget(parent=self)

        self._stack.addWidget(self._build_page_links())    # 0
        self._stack.addWidget(self._build_page_channel())  # 1
        self._stack.addWidget(self.studio_widget)          # 2
        self._stack.setCurrentIndex(self.PAGE_LINKS)

        # Kết nối sự kiện từ Studio
        self.studio_widget.back_requested.connect(lambda: self._switch_page(self.PAGE_LINKS))
        self.studio_widget.export_dubbing_requested.connect(self._on_studio_export_dubbing)
        self.studio_widget.video_loaded.connect(self._on_studio_video_loaded)
        self.studio_widget.status_message.connect(self._on_studio_status_message)
        self.studio_widget.progress_updated.connect(self._on_studio_progress_updated)
        self.studio_widget.audio_mix_changed.connect(self._on_studio_audio_mix_changed)
        self.studio_widget.set_audio_mix_settings(
            getattr(self, "voice_volume", 220),
            getattr(self, "bg_volume", 10),
            getattr(self, "mute_original", False),
        )

        # ── Cột phải: Tiến trình & Log ──
        right = self._build_right_panel()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._stack)
        splitter.addWidget(right)
        splitter.setSizes([560, 680])

        root.addWidget(splitter)

    # ─────────────────────────────────────────────────────────────────
    # TRANG 0 — Tải theo danh sách liên kết
    # ─────────────────────────────────────────────────────────────────

    def _build_page_links(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # ── Tiêu đề trang ──
        btn_gallery = QPushButton("Xem video đã tải")
        btn_gallery.setIcon(get_svg_icon("film", COLORS["text_secondary"]))
        btn_gallery.setStyleSheet(self._s_small_btn())
        btn_gallery.setToolTip("Mở trình phát xem video đã tải xuống (Ctrl+4)")
        btn_gallery.clicked.connect(lambda: self.open_downloaded_videos_gallery())

        bar = self._page_titlebar(
            "Tải theo danh sách liên kết",
            "Ctrl+1 để chuyển trang",
            icon_name="link",
            extra_btn=btn_gallery,
        )
        layout.addLayout(bar)

        # ── Card ô nhập URL ──
        card = self._make_card()
        card_l = QVBoxLayout(card)
        card_l.setContentsMargins(14, 10, 14, 10)
        card_l.setSpacing(8)

        # Header với nút hỗ trợ
        hdr = QHBoxLayout()
        lbl = QLabel("Dán danh sách liên kết vào đây (mỗi dòng 1 link):")
        lbl.setStyleSheet(f"color:{COLORS['text_secondary']}; font-size:12.5px;")
        hdr.addWidget(lbl)
        hdr.addStretch()

        btn_paste = QPushButton("Dán clipboard")
        btn_paste.setIcon(get_svg_icon("clipboard"))
        btn_paste.setFixedHeight(28)
        btn_paste.setStyleSheet(self._s_small_btn())
        btn_paste.clicked.connect(self._on_paste_clipboard)
        hdr.addWidget(btn_paste)

        btn_clear = QPushButton("Xóa hết")
        btn_clear.setIcon(get_svg_icon("trash"))
        btn_clear.setFixedHeight(28)
        btn_clear.setStyleSheet(self._s_small_btn())
        btn_clear.clicked.connect(lambda: self._url_input.clear())
        hdr.addWidget(btn_clear)
        card_l.addLayout(hdr)

        # Ô nhập
        self._url_input = QPlainTextEdit()
        self._url_input.setPlaceholderText(
            "Dán link TikTok, Douyin, Facebook, YouTube vào đây...\n"
            "Hỗ trợ cả văn bản chia sẻ kèm link, ví dụ:\n"
            "  7.12 复制打开抖音 https://v.douyin.com/xxxxx/\n"
            "  https://www.tiktok.com/@user/video/1234567890"
        )
        self._url_input.setMinimumHeight(300)
        self._url_input.textChanged.connect(self._update_button_states)
        card_l.addWidget(self._url_input, 1)

        self._url_count_label = QLabel("0 liên kết phát hiện")
        self._url_count_label.setStyleSheet(
            f"color:{COLORS['text_muted']}; font-size:12px;"
        )
        card_l.addWidget(self._url_count_label)
        layout.addWidget(card, 1)

        return page

    # ─────────────────────────────────────────────────────────────────
    # TRANG 1 — Quét Kênh / Hồ sơ
    # ─────────────────────────────────────────────────────────────────

    def _build_page_channel(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # ── Tiêu đề trang ──
        btn_gallery_ch = QPushButton("Xem video đã tải")
        btn_gallery_ch.setIcon(get_svg_icon("film", COLORS["text_secondary"]))
        btn_gallery_ch.setStyleSheet(self._s_small_btn())
        btn_gallery_ch.setToolTip("Mở trình phát xem video đã tải xuống (Ctrl+4)")
        btn_gallery_ch.clicked.connect(lambda: self.open_downloaded_videos_gallery())

        bar = self._page_titlebar(
            "Quét & Tải theo Kênh / Hồ sơ",
            "Ctrl+2 để chuyển trang",
            icon_name="user",
            extra_btn=btn_gallery_ch,
        )
        layout.addLayout(bar)

        # ── Card nhập kênh ──
        card_top = self._make_card()
        tl = QVBoxLayout(card_top)
        tl.setContentsMargins(14, 10, 14, 10)
        tl.setSpacing(10)

        # URL kênh + nút quét
        url_row = QHBoxLayout()
        self._channel_url_input = QLineEdit()
        self._channel_url_input.setPlaceholderText(
            "TikTok: @username  |  Douyin: /user/xxx  |  Facebook: /pagename hoặc profile.php?id=...&sk=reels_tab"
        )
        url_row.addWidget(self._channel_url_input, 1)

        lbl_max = QLabel("Số lượng:")
        lbl_max.setStyleSheet(f"color:{COLORS['text_secondary']}; font-size:12px;")
        url_row.addWidget(lbl_max)

        self._scan_limit_combo = QComboBox()
        self._scan_limit_combo.setEditable(True)
        self._scan_limit_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._scan_limit_combo.addItem("All")
        self._scan_limit_combo.setCurrentText("50")
        self._scan_limit_combo.setValidator(QIntValidator(1, 1000000, self._scan_limit_combo))
        self._scan_limit_combo.setFixedWidth(90)
        self._scan_limit_combo.setToolTip(
            "Nhập số video tối đa cần quét hoặc mở danh sách để chọn All. All tiếp tục phân trang đến khi nguồn không còn trả video."
        )
        url_row.addWidget(self._scan_limit_combo)

        lbl_vid = QLabel("video")
        lbl_vid.setStyleSheet(f"color:{COLORS['text_secondary']}; font-size:12px;")
        url_row.addWidget(lbl_vid)

        self._btn_scan = QPushButton("Quét kênh")
        self._btn_scan.setIcon(get_svg_icon("search"))
        self._btn_scan.setFixedHeight(34)
        self._btn_scan.setStyleSheet(btn_secondary_style())
        url_row.addWidget(self._btn_scan)
        tl.addLayout(url_row)

        # ── Banner trạng thái Cookie trực quan ──
        tl.addWidget(self._build_cookie_banner())

        # Bộ lọc Viral thu gọn được
        tl.addWidget(self._build_filter_section())

        # Status
        self._scan_status_label = QLabel("Nhập URL kênh rồi nhấn Quét kênh để bắt đầu.")
        self._scan_status_label.setStyleSheet(
            f"color:{COLORS['text_muted']}; font-size:12px;"
        )
        tl.addWidget(self._scan_status_label)
        layout.addWidget(card_top)

        # ── Card bảng kết quả ──
        card_res = self._make_card()
        rl = QVBoxLayout(card_res)
        rl.setContentsMargins(14, 10, 14, 10)
        rl.setSpacing(8)

        res_hdr = QHBoxLayout()
        lbl_res = QLabel("Danh sách video tìm thấy:")
        lbl_res.setStyleSheet(
            f"font-weight:700; font-size:13px; color:{COLORS['text_primary']};"
        )
        res_hdr.addWidget(lbl_res)
        res_hdr.addStretch()

        self._lbl_scan_count = QLabel("0 video")
        self._lbl_scan_count.setStyleSheet(f"""
            background-color: {COLORS['badge_total_bg']};
            border: 1px solid {COLORS['border']};
            border-radius: 5px;
            color: {COLORS['text_secondary']};
            font-size: 12px;
            font-weight: 600;
            padding: 3px 10px;
        """)
        res_hdr.addWidget(self._lbl_scan_count)
        rl.addLayout(res_hdr)

        # QTableWidget 7 cột
        self._result_table = QTableWidget()
        self._result_table.setColumnCount(7)
        self._result_table.setHorizontalHeaderLabels([
            "✓", "Tiêu đề video", "Lượt xem", "Lượt thích", "Thời lượng", "Ngày đăng", "URL (Nhấp để mở)"
        ])
        h = self._result_table.horizontalHeader()
        h.setMinimumSectionSize(36)
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self._result_table.setColumnWidth(0, 36)
        self._result_table.setColumnWidth(2, 95)
        self._result_table.setColumnWidth(3, 95)
        self._result_table.setColumnWidth(4, 90)
        self._result_table.setColumnWidth(5, 105)
        self._result_table.verticalHeader().setVisible(False)
        self._result_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._result_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._result_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._result_table.setAlternatingRowColors(True)
        self._result_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._result_table.customContextMenuRequested.connect(self._on_table_context_menu)
        self._result_table.cellClicked.connect(self._on_table_cell_clicked)
        self._result_table.cellDoubleClicked.connect(self._on_table_cell_double_clicked)
        rl.addWidget(self._result_table, 1)

        # Empty State cho bảng khi chưa có video nào
        self._channel_empty_state = TableEmptyState(
            self._result_table,
            icon_name="search",
            title="Chưa có video nào",
            description="Nhập liên kết kênh ở trên và nhấn Quét kênh để tải danh sách video.",
        )

        # Nút chọn + xuất
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(8)
        self._btn_select_all = QPushButton("Chọn tất cả")
        self._btn_select_all.setIcon(get_svg_icon("check-square"))
        self._btn_select_all.setFixedHeight(30)
        self._btn_select_all.setStyleSheet(self._s_small_btn())
        btn_bar.addWidget(self._btn_select_all)

        self._btn_deselect_all = QPushButton("Bỏ chọn")
        self._btn_deselect_all.setIcon(get_svg_icon("square"))
        self._btn_deselect_all.setFixedHeight(30)
        self._btn_deselect_all.setStyleSheet(self._s_small_btn())
        btn_bar.addWidget(self._btn_deselect_all)

        self._btn_export_csv = QPushButton("Xuất CSV")
        self._btn_export_csv.setIcon(get_svg_icon("file-spreadsheet"))
        self._btn_export_csv.setFixedHeight(30)
        self._btn_export_csv.setStyleSheet(self._s_small_btn())
        self._btn_export_csv.setEnabled(False)
        btn_bar.addWidget(self._btn_export_csv)

        btn_bar.addStretch()

        self._lbl_selected_count = QLabel("Đã chọn: 0 video")
        self._lbl_selected_count.setStyleSheet(
            f"color:{COLORS['text_muted']}; font-size:12px;"
        )
        btn_bar.addWidget(self._lbl_selected_count)
        rl.addLayout(btn_bar)
        layout.addWidget(card_res, 1)

        return page

    # ─────────────────────────────────────────────────────────────────
    # BỘ LỌC VIRAL (dùng trong Page Channel)
    # ─────────────────────────────────────────────────────────────────

    def _build_cookie_banner(self) -> QFrame:
        """Thanh trạng thái Cookie nổi bật ngay trên trang Quét kênh."""
        c = COLORS
        self._cookie_banner = QFrame()
        self._cookie_banner.setObjectName("cookie_banner")
        layout = QHBoxLayout(self._cookie_banner)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)

        self._cookie_status_icon = QLabel()
        self._cookie_status_icon.setPixmap(get_svg_pixmap("cookie", color=c['status_warning'], size=18))
        layout.addWidget(self._cookie_status_icon)

        self._cookie_status_text = QLabel("Cookie: Chưa nạp (TikTok / Douyin yêu cầu Cookie để quét toàn bộ kênh)")
        self._cookie_status_text.setStyleSheet(f"color: {c['status_warning']}; font-size: 12px; font-weight: 500;")
        layout.addWidget(self._cookie_status_text, 1)

        self._btn_banner_load_cookie = QPushButton("Nạp Cookie (.txt)")
        self._btn_banner_load_cookie.setIcon(get_svg_icon("cookie"))
        self._btn_banner_load_cookie.setFixedHeight(27)
        self._btn_banner_load_cookie.setStyleSheet(self._s_small_btn())
        self._btn_banner_load_cookie.clicked.connect(self._on_choose_cookie)
        layout.addWidget(self._btn_banner_load_cookie)

        self._btn_banner_guide_cookie = QPushButton("Hướng dẫn")
        self._btn_banner_guide_cookie.setIcon(get_svg_icon("info"))
        self._btn_banner_guide_cookie.setFixedHeight(27)
        self._btn_banner_guide_cookie.setStyleSheet(self._s_small_btn())
        self._btn_banner_guide_cookie.clicked.connect(self._show_cookie_guide)
        layout.addWidget(self._btn_banner_guide_cookie)

        self._btn_banner_clear_cookie = QPushButton("Bỏ")
        self._btn_banner_clear_cookie.setIcon(get_svg_icon("x"))
        self._btn_banner_clear_cookie.setFixedHeight(27)
        self._btn_banner_clear_cookie.setStyleSheet(self._s_small_btn())
        self._btn_banner_clear_cookie.clicked.connect(self._on_clear_cookie)
        self._btn_banner_clear_cookie.setVisible(False)
        layout.addWidget(self._btn_banner_clear_cookie)

        self._cookie_banner.setStyleSheet(f"""
            QFrame#cookie_banner {{
                background-color: {c['status_warning_bg']};
                border: 1px solid {c['status_warning_border']};
                border-radius: 6px;
            }}
        """)
        return self._cookie_banner

    def _update_cookie_ui(self) -> None:
        """Cập nhật giao diện thanh Cookie dựa trên self.cookies_path."""
        if not hasattr(self, "_cookie_banner"):
            return
        c = COLORS
        if self.cookies_path and os.path.isfile(self.cookies_path):
            filename = os.path.basename(self.cookies_path)
            self._cookie_status_icon.setPixmap(get_svg_pixmap("check", color=c["status_success"], size=18))
            self._cookie_status_text.setText(
                f"Cookie: Đã nạp ({filename}) — Sẵn sàng quét kênh"
            )
            self._cookie_status_text.setStyleSheet(
                f"color: {c['status_success']}; font-size: 12px; font-weight: 600;"
            )
            self._cookie_banner.setStyleSheet(f"""
                QFrame#cookie_banner {{
                    background-color: {c['status_success_bg']};
                    border: 1px solid {c['status_success_border']};
                    border-radius: 6px;
                }}
            """)
            self._btn_banner_load_cookie.setText("Đổi Cookie")
            self._btn_banner_load_cookie.setIcon(get_svg_icon("refresh"))
            self._btn_banner_clear_cookie.setVisible(True)
        else:
            self._cookie_status_icon.setPixmap(get_svg_pixmap("cookie", color=c["status_warning"], size=18))
            self._cookie_status_text.setText(
                "Cookie: Chưa nạp (Kênh Douyin quét trực tiếp không cần Cookie)"
            )
            self._cookie_status_text.setStyleSheet(
                f"color: {c['status_warning']}; font-size: 12px; font-weight: 500;"
            )
            self._cookie_banner.setStyleSheet(f"""
                QFrame#cookie_banner {{
                    background-color: {c['status_warning_bg']};
                    border: 1px solid {c['status_warning_border']};
                    border-radius: 6px;
                }}
            """)
            self._btn_banner_load_cookie.setText("Nạp Cookie (.txt)")
            self._btn_banner_load_cookie.setIcon(get_svg_icon("cookie"))
            self._btn_banner_clear_cookie.setVisible(False)

    def _build_filter_section(self) -> QWidget:
        c = COLORS
        self._filter_section = CollapsibleSection(
            title="Bộ lọc nâng cao (Lượt xem, thích, thời lượng, ngày)",
            icon_name="filter",
            initially_expanded=False,
        )

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)

        def flbl(t: str) -> QLabel:
            lbl = QLabel(t)
            lbl.setStyleSheet(f"color:{c['text_secondary']}; font-size:12px;")
            return lbl

        grid.addWidget(flbl("Lượt xem tối thiểu:"), 0, 0)
        self._filter_min_views = QSpinBox()
        self._filter_min_views.setRange(0, 10_000_000)
        self._filter_min_views.setSingleStep(1000)
        self._filter_min_views.setSpecialValueText("Không lọc")
        self._filter_min_views.setMinimumWidth(110)
        grid.addWidget(self._filter_min_views, 0, 1)

        grid.addWidget(flbl("Lượt thích tối thiểu:"), 0, 2)
        self._filter_min_likes = QSpinBox()
        self._filter_min_likes.setRange(0, 1_000_000)
        self._filter_min_likes.setSingleStep(100)
        self._filter_min_likes.setSpecialValueText("Không lọc")
        self._filter_min_likes.setMinimumWidth(110)
        grid.addWidget(self._filter_min_likes, 0, 3)

        grid.addWidget(flbl("Thời lượng:"), 1, 0)
        self._filter_duration = QComboBox()
        self._filter_duration.addItems(["Tất cả", "Dưới 60 giây (Shorts/Reels)", "Trên 60 giây"])
        self._filter_duration.setMinimumWidth(150)
        grid.addWidget(self._filter_duration, 1, 1)

        grid.addWidget(flbl("Ngày đăng:"), 1, 2)
        self._filter_date = QComboBox()
        self._filter_date.addItems(["Tất cả", "3 ngày qua", "7 ngày qua", "30 ngày qua"])
        self._filter_date.setMinimumWidth(150)
        grid.addWidget(self._filter_date, 1, 3)

        self._filter_min_views.valueChanged.connect(self._on_viral_filter_changed)
        self._filter_min_likes.valueChanged.connect(self._on_viral_filter_changed)
        self._filter_duration.currentIndexChanged.connect(self._on_viral_filter_changed)
        self._filter_date.currentIndexChanged.connect(self._on_viral_filter_changed)

        grid.setColumnStretch(4, 1)
        self._filter_section.content_layout.addLayout(grid)
        return self._filter_section

    # ─────────────────────────────────────────────────────────────────
    # CỘT PHẢI — Tiến trình & Log
    # ─────────────────────────────────────────────────────────────────

    def _build_right_panel(self) -> QWidget:
        c = COLORS
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        card = self._make_card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(14, 10, 14, 10)
        cl.setSpacing(8)

        # Tiêu đề
        lbl = QLabel("Tiến trình tải & Nhật ký hệ thống")
        lbl.setStyleSheet(
            f"font-weight:700; font-size:13px; color:{c['text_primary']};"
        )
        cl.addWidget(lbl)

        # Badges
        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        self._badge_total = self._make_badge(
            "Tổng: 0 video", c["badge_total_bg"], c["border"]
        )
        self._badge_success = self._make_badge(
            "Đã tải: 0", c["badge_success_bg"], c["badge_success_border"]
        )
        self._badge_active = self._make_badge(
            "Đang tải: 0", c["badge_active_bg"], c["badge_active_border"]
        )
        self._badge_error = self._make_badge(
            "Lỗi: 0", c["badge_error_bg"], c["badge_error_border"]
        )
        for b in [self._badge_total, self._badge_success, self._badge_active, self._badge_error]:
            badge_row.addWidget(b)
        badge_row.addStretch()
        cl.addLayout(badge_row)

        # Progress bar
        self._progress_label = QLabel("Tiến độ: 0%")
        self._progress_label.setStyleSheet(
            f"color:{c['text_secondary']}; font-size:12px;"
        )
        cl.addWidget(self._progress_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        cl.addWidget(self._progress_bar)

        # Thông báo trạng thái / Hoạt động (Nhận từ Studio, Download, TikTok, AI...)
        self._status_notify_box = QFrame()
        self._status_notify_box.setStyleSheet(f"""
            QFrame {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border']};
                border-left: 3px solid {c['accent_orange']};
                border-radius: 6px;
            }}
        """)
        sn_layout = QHBoxLayout(self._status_notify_box)
        sn_layout.setContentsMargins(8, 6, 8, 6)
        sn_layout.setSpacing(6)

        self._status_notify_label = QLabel("")
        self._status_notify_label.setStyleSheet(f"""
            QLabel {{
                color: {c['accent_orange']};
                font-size: 11.5px;
                font-weight: 500;
                background: transparent;
                border: none;
            }}
        """)
        self._status_notify_label.setWordWrap(True)
        sn_layout.addWidget(self._status_notify_label, 1)

        self._status_notify_box.setVisible(False)
        cl.addWidget(self._status_notify_box)

        # Log header
        log_hdr = QHBoxLayout()
        lbl_log = QLabel("NHẬT KÝ HOẠT ĐỘNG (REALTIME)")
        lbl_log.setStyleSheet(
            f"color:{c['text_muted']}; font-size:11px; font-weight:600; letter-spacing:0.5px;"
        )
        log_hdr.addWidget(lbl_log)
        log_hdr.addStretch()

        self._btn_export_errors = QPushButton("Xuất file lỗi (.txt)")
        self._btn_export_errors.setIcon(get_svg_icon("file-text"))
        self._btn_export_errors.setFixedHeight(26)
        self._btn_export_errors.setStyleSheet(self._s_small_btn())
        self._btn_export_errors.setEnabled(False)
        log_hdr.addWidget(self._btn_export_errors)
        cl.addLayout(log_hdr)

        # Log view có word wrap và thanh cuộn mượt
        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMinimumHeight(120)
        self._log_view.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self._log_view.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self._log_view.setStyleSheet(f"""
            QTextEdit {{
                background-color: {c['bg_input']};
                color: {c['text_primary']};
                border: 1px solid {c['bg_input_border']};
                border-radius: 6px;
                padding: 8px;
                font-family: "Cascadia Code", "Consolas", monospace;
                font-size: 11px;
                line-height: 1.5;
            }}
        """)
        cl.addWidget(self._log_view, 1)

        # ── Hàng nút điều khiển (Chỉ 1 nút Primary duy nhất) ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        self._btn_stop = QPushButton("Dừng tải")
        self._btn_stop.setIcon(get_svg_icon("stop", color=COLORS["status_error"]))
        self._btn_stop.setFixedHeight(40)
        self._btn_stop.setEnabled(False)
        self._btn_stop.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._btn_stop.setStyleSheet(btn_stop_style())
        btn_row.addWidget(self._btn_stop)

        self._btn_start = QPushButton("BẮT ĐẦU TẢI")
        self._btn_start.setIcon(get_svg_icon("play", color="#ffffff"))
        self._btn_start.setFixedHeight(40)
        self._btn_start.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._btn_start.setStyleSheet(btn_primary_style())
        self._btn_start.setEnabled(False)
        self._btn_start.setToolTip("Dán ít nhất một liên kết video để tải")
        btn_row.addWidget(self._btn_start)
        cl.addLayout(btn_row)

        # Aliases chuẩn cho các nút điều khiển chính
        self.btn_start = self._btn_start
        self.btn_stop = self._btn_stop

        layout.addWidget(card, 1)
        return panel

    # ══════════════════════════════════════════════════════════════════
    # STATUS BAR
    # ══════════════════════════════════════════════════════════════════

    def _build_statusbar(self) -> None:
        c = COLORS
        sb = QStatusBar()
        self.setStatusBar(sb)
        sb.setStyleSheet(f"""
            QStatusBar {{
                background-color: {c['bg_secondary']};
                color: {c['text_secondary']};
                border-top: 1px solid {c['border']};
                font-size: 12px;
                padding: 3px 10px;
            }}
        """)
        # Thông tin thư mục + lồng tiếng
        self._sb_label = QLabel("Lưu tại: —   |   Lồng tiếng: TẮT")
        self._sb_label.setStyleSheet(f"color:{c['text_muted']}; padding: 0 4px; font-size: 12px;")
        sb.addWidget(self._sb_label)

        # ── Nhãn bản quyền (bên phải StatusBar) ──
        self._sb_license_label = QLabel("")
        self._sb_license_label.setStyleSheet(
            f"color:{c['text_muted']}; padding: 0 8px; font-size: 11.5px; font-weight: 600;"
        )
        # Nút Nâng cấp (ẩn khi đã PRO)
        self._sb_upgrade_btn = QPushButton("Nâng cấp PRO")
        self._sb_upgrade_btn.setIcon(get_svg_icon("shield-check", color=c['status_warning']))
        self._sb_upgrade_btn.setFixedHeight(24)
        self._sb_upgrade_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['status_warning_bg']};
                color: {c['status_warning']};
                border: 1px solid {c['status_warning_border']};
                border-radius: 4px;
                font-size: 11.5px;
                font-weight: 600;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                background-color: rgba(245, 158, 11, 0.22);
            }}
        """)
        self._sb_upgrade_btn.clicked.connect(self._on_open_activation_dialog)
        sb.addPermanentWidget(self._sb_license_label)
        sb.addPermanentWidget(self._sb_upgrade_btn)

        self._status_bar = sb

    def _make_sb_sep(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        sep.setFixedHeight(20)
        return sep

    # ══════════════════════════════════════════════════════════════════
    # KẾT NỐI TÍN HIỆU
    # ══════════════════════════════════════════════════════════════════

    def _connect_signals(self) -> None:
        # URL input
        self._url_input.textChanged.connect(self._on_url_text_changed)

        # Table signals
        self._btn_scan.clicked.connect(self._on_scan_channel)
        self._btn_select_all.clicked.connect(self._on_select_all)
        self._btn_deselect_all.clicked.connect(self._on_deselect_all)
        self._btn_export_csv.clicked.connect(self._on_export_csv)
        self._result_table.itemChanged.connect(self._on_table_item_changed)

        # Main buttons & dynamic action switching
        self.btn_start.clicked.connect(self.on_btn_start_clicked)
        self.btn_stop.clicked.connect(self.on_btn_stop_clicked)
        self._btn_export_errors.clicked.connect(self._on_export_errors)
        self.stacked_widget.currentChanged.connect(self._on_stack_page_changed)
        self.update_action_buttons_state(self.stacked_widget.currentIndex())

    # ══════════════════════════════════════════════════════════════════
    # XỬ LÝ SỰ KIỆN — MENU TỆP
    # ══════════════════════════════════════════════════════════════════

    def _on_choose_output_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, "Chọn thư mục lưu video", self.output_dir
        )
        if d:
            self.output_dir = d
            try:
                os.makedirs(d, exist_ok=True)
            except OSError:
                pass
            self._save_settings()
            self._refresh_statusbar()
            self._append_log("HỆ THỐNG", f"Thư mục lưu đã đổi sang: {d}")

    def _on_choose_cookie(self) -> bool:
        f, _ = QFileDialog.getOpenFileName(
            self, "Chọn file Cookie (.txt)", "",
            "Cookie file (*.txt);;Tất cả file (*.*)"
        )
        if f:
            self.cookies_path = f
            if not getattr(self, "tiktok_cookies_path", ""):
                self.tiktok_cookies_path = f
            if not getattr(self, "youtube_cookies_path", ""):
                self.youtube_cookies_path = f
            self._save_settings()
            self._update_cookie_ui()
            self._append_log("HỆ THỐNG", f"Đã nạp cookie: {os.path.basename(f)}")
            QMessageBox.information(
                self, "Nạp Cookie thành công",
                f"File cookie đã được nạp thành công:\n{f}\n\nCookie sẽ được dùng cho tất cả các lần quét và tải tiếp theo."
            )
            return True
        return False

    def _on_clear_cookie(self) -> None:
        self.cookies_path = ""
        self._save_settings()
        self._update_cookie_ui()
        self._append_log("HỆ THỐNG", "Đã gỡ bỏ file cookie.")

    def _show_cookie_guide(self) -> None:
        dlg = CookieGuideDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_cookie_file:
            self.cookies_path = dlg.selected_cookie_file
            self._save_settings()
            self._update_cookie_ui()
            self._append_log("HỆ THỐNG", f"Đã nạp cookie: {os.path.basename(self.cookies_path)}")
            QMessageBox.information(
                self, "Nạp Cookie thành công",
                f"File cookie đã được nạp thành công:\n{self.cookies_path}\n\nCookie sẽ được dùng cho các lần quét tiếp theo."
            )

    def _on_import_file(self) -> None:
        f, _ = QFileDialog.getOpenFileName(
            self, "Nhập danh sách link từ file", "",
            "File văn bản (*.txt *.csv);;Tất cả file (*.*)"
        )
        if not f:
            return
        urls = read_urls_from_file(f)
        if not urls:
            QMessageBox.warning(self, "Thông báo", "Không tìm thấy liên kết hợp lệ nào.")
            return
        existing = self._url_input.toPlainText().strip()
        combined = (existing + "\n" if existing else "") + "\n".join(urls)
        self._url_input.setPlainText(combined)
        self._switch_page(self.PAGE_LINKS)
        self._append_log("HỆ THỐNG", f"Đã nhập {len(urls)} liên kết từ file: {os.path.basename(f)}")

    # ══════════════════════════════════════════════════════════════════
    # XỬ LÝ SỰ KIỆN — MENU CÔNG CỤ
    # ══════════════════════════════════════════════════════════════════

    def _on_open_dub_dialog(self) -> None:
        dlg = DubbingDialog(
            auto_dub=self.auto_dub,
            src_lang=self.dub_lang,
            voice=self.dub_voice,
            bg_volume=self.bg_volume,
            voice_volume=getattr(self, "voice_volume", 220),
            mute_original=getattr(self, "mute_original", False),
            whisper_model=self.whisper_model,
            gemini_api_key=self.gemini_api_key,
            auto_open_dubbed=self.auto_open_dubbed,
            parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.auto_dub = dlg.result_auto_dub
            self.auto_open_dubbed = dlg.result_auto_open_dubbed
            self.dub_lang = dlg.result_src_lang
            self.dub_voice = dlg.result_voice
            self.bg_volume = dlg.result_bg_volume
            self.voice_volume = dlg.result_voice_volume
            self.mute_original = dlg.result_mute_original
            self.whisper_model = dlg.result_whisper_model
            self.gemini_api_key = dlg.result_gemini_api_key
            if hasattr(self, "studio_widget") and hasattr(self.studio_widget, "set_audio_mix_settings"):
                self.studio_widget.set_audio_mix_settings(self.voice_volume, self.bg_volume, self.mute_original)
            self._save_settings()
            self._refresh_statusbar()
            status = "BẬT" if self.auto_dub else "TẮT"
            mute_str = " (Tắt tiếng gốc)" if self.mute_original else f" (Tiếng gốc: {self.bg_volume}%, Giọng đọc: {self.voice_volume}%)"
            api_info = "Gemini API: Đã có key" if self.gemini_api_key else "Gemini API: Chưa có key"
            self._append_log("LỒNG TIẾNG", f"Cài đặt đã lưu — Tự động lồng tiếng: {status}{mute_str} | {api_info}")

    def _on_open_audio_mix_dialog(self) -> None:
        """Mở popup tùy chỉnh tỷ lệ hòa âm từ Menu Công cụ."""
        from ui.dubbing_studio import AudioMixDialog
        dlg = AudioMixDialog(
            parent=self,
            voice_volume=getattr(self, "voice_volume", 220),
            bg_volume=getattr(self, "bg_volume", 10),
            mute_original=getattr(self, "mute_original", False),
        )
        if dlg.exec():
            v_vol, bg_vol, mute_orig = dlg.get_settings()
            self.voice_volume = v_vol
            self.bg_volume = bg_vol
            self.mute_original = mute_orig
            if hasattr(self, "studio_widget") and hasattr(self.studio_widget, "set_audio_mix_settings"):
                self.studio_widget.set_audio_mix_settings(v_vol, bg_vol, mute_orig)
            self._save_settings()
            mute_str = " (Đã tắt tiếng gốc)" if mute_orig else f" (Gốc: {bg_vol}%, Giọng đọc: {v_vol}%)"
            self._append_log("LỒNG TIẾNG", f"Đã cập nhật tỷ lệ hòa âm: Giọng đọc {v_vol}%, Tiếng gốc {bg_vol}%{mute_str}")

    def _on_studio_audio_mix_changed(self, v_vol: int, bg_vol: int, mute_orig: bool) -> None:
        """Đồng bộ cài đặt hòa âm từ Studio sang cấu hình MainWindow."""
        self.voice_volume = v_vol
        self.bg_volume = bg_vol
        self.mute_original = mute_orig
        self._save_settings()
        mute_str = " (Đã tắt tiếng gốc)" if mute_orig else f" (Gốc: {bg_vol}%, Giọng đọc: {v_vol}%)"
        self._append_log("LỒNG TIẾNG", f"Studio cập nhật hòa âm: Giọng đọc {v_vol}%, Tiếng gốc {bg_vol}%{mute_str}")

    def _on_choose_tiktok_cookie(self) -> None:
        f, _ = QFileDialog.getOpenFileName(
            self, "Chọn file Cookie TikTok", "",
            "Cookie files (*.txt *.json);;Tất cả file (*.*)"
        )
        if f and os.path.isfile(f):
            self.tiktok_cookies_path = f
            self._save_settings()
            self._append_log("TIKTOK AUTO", f"Đã nạp file Cookie TikTok: {os.path.basename(f)}")
            self._refresh_statusbar()
            QMessageBox.information(
                self, "Đã nạp Cookie TikTok",
                f"✅ Đã nạp thành công file Cookie TikTok:\n{f}\n\n"
                "Hệ thống đã sẵn sàng cho tính năng tự động đăng video lên TikTok!"
            )

    def _on_open_tiktok_dialog(self) -> None:
        from ui.tiktok_upload_dialog import TikTokUploadDialog
        dlg = TikTokUploadDialog(
            auto_upload=getattr(self, "auto_upload_tiktok", False),
            privacy=getattr(self, "tiktok_privacy", "public"),
            delay_minutes=getattr(self, "tiktok_delay_minutes", 45),
            cookies_path=getattr(self, "tiktok_cookies_path", ""),
            headless=getattr(self, "tiktok_headless", False),
            parent=self,
        )
        if dlg.exec():
            self.auto_upload_tiktok = dlg.result_auto_upload
            self.tiktok_privacy = dlg.result_privacy
            self.tiktok_delay_minutes = dlg.result_delay_minutes
            self.tiktok_cookies_path = dlg.result_cookies_path
            self.tiktok_headless = dlg.result_headless
            self._save_settings()
            self._refresh_statusbar()

            st = "BẬT" if self.auto_upload_tiktok else "TẮT"
            self._append_log(
                "TIKTOK AUTO",
                f"Cài đặt đã lưu — Tự động đăng TikTok: {st} | Chế độ: {self.tiktok_privacy} | Giãn cách: {self.tiktok_delay_minutes}p"
            )

    def _on_choose_youtube_cookies(self) -> None:
        f, _ = QFileDialog.getOpenFileName(
            self, "Chọn file Cookie YouTube (youtube_cookies.txt)", "",
            "Cookie files (*.txt *.json);;Tất cả file (*.*)"
        )
        if f and os.path.isfile(f):
            self.youtube_cookies_path = f
            self._save_settings()
            self._append_log("YOUTUBE AUTO", f"Đã nạp file Cookie YouTube: {os.path.basename(f)}")
            QMessageBox.information(
                self, "Đã nạp Cookie YouTube",
                f"✅ Đã nạp thành công file Cookie YouTube:\n{f}"
            )

    def _on_choose_youtube_secret(self) -> None:
        self._on_choose_youtube_cookies()

    def _on_open_youtube_dialog(self) -> None:
        from ui.youtube_upload_dialog import YouTubeUploadDialog
        sched_dt = None
        if getattr(self, "youtube_scheduled_time_str", ""):
            try:
                sched_dt = datetime.datetime.fromisoformat(self.youtube_scheduled_time_str)
            except Exception:
                sched_dt = None

        dlg = YouTubeUploadDialog(
            auto_upload=getattr(self, "auto_upload_youtube", False),
            privacy=getattr(self, "youtube_privacy", "public"),
            cookies_path=getattr(self, "youtube_cookies_path", "youtube_cookies.txt"),
            schedule_enabled=getattr(self, "youtube_schedule_enabled", False),
            schedule_date=getattr(self, "youtube_schedule_date", ""),
            schedule_time=getattr(self, "youtube_schedule_time", ""),
            scheduled_datetime=sched_dt,
            default_tags=getattr(self, "youtube_default_tags", "Shorts, AI, PhimHay, ReviewPhim"),
            parent=self,
        )
        if dlg.exec():
            self.auto_upload_youtube = dlg.result_auto_upload
            self.youtube_privacy = dlg.result_privacy
            self.youtube_cookies_path = dlg.result_cookies_path
            self.youtube_schedule_enabled = dlg.result_schedule_enabled
            self.youtube_schedule_date = dlg.result_schedule_date
            self.youtube_schedule_time = dlg.result_schedule_time
            if dlg.result_scheduled_datetime:
                self.youtube_scheduled_time_str = dlg.result_scheduled_datetime.isoformat()
            else:
                self.youtube_scheduled_time_str = ""
            self.youtube_default_tags = dlg.result_default_tags
            self._save_settings()
            self._refresh_statusbar()

            st = "BẬT" if self.auto_upload_youtube else "TẮT"
            sched_info = f" (Hẹn giờ: {self.youtube_schedule_date} {self.youtube_schedule_time})" if self.youtube_schedule_enabled else ""
            self._append_log(
                "YOUTUBE AUTO",
                f"Cài đặt đã lưu — Tự động đăng YouTube Shorts: {st} | Chế độ: {self.youtube_privacy}{sched_info}"
            )

    def _on_dub_manual(self) -> None:
        f, _ = QFileDialog.getOpenFileName(
            self, "Chọn video MP4 để lồng tiếng & soát kịch bản", "",
            "Video MP4 (*.mp4);;Tất cả file (*.*)"
        )
        if f:
            self.studio_widget.load_video(f)
            self._switch_page(self.PAGE_STUDIO)
            self._append_log("STUDIO", f"Đã nạp video vào Studio: {os.path.basename(f)}")

    def _on_studio_export_dubbing(self, video_path: str, custom_segments: list) -> None:
        """Xuất video lồng tiếng từ Studio với các câu thoại đã soát."""
        if self._is_dubbing:
            QMessageBox.warning(self, "Đang xử lý", "Hiện đang có tiến trình lồng tiếng đang chạy!")
            return
        voice_vol, bg_vol, mute_orig = None, None, None
        if hasattr(self, 'studio_widget') and hasattr(self.studio_widget, 'get_audio_mix_settings'):
            voice_vol, bg_vol, mute_orig = self.studio_widget.get_audio_mix_settings()
        self._start_dubbing(
            video_path,
            custom_segments=custom_segments,
            voice_volume=voice_vol,
            bg_volume=bg_vol,
            mute_original=mute_orig,
        )

    def _on_studio_status_message(self, msg: str) -> None:
        """Nhận thông báo trạng thái từ Studio và hiển thị tập trung tại panel bên phải."""
        if not hasattr(self, "_status_notify_label"):
            return

        if not msg or not msg.strip():
            self._status_notify_box.setVisible(False)
            self._status_notify_label.setText("")
            return

        self._status_notify_label.setText(msg)
        self._status_notify_box.setVisible(True)
        self._status_bar.showMessage(msg)

        # Ghi các thông điệp quan trọng vào realtime log
        if any(token in msg for token in ["[TIKTOK", "Whisper", "Gemini", "🎉", "❌", "🚀", "✨", "kịch bản", "lồng tiếng"]):
            platform = "TIKTOK" if "TIKTOK" in msg else ("LỒNG TIẾNG" if ("lồng tiếng" in msg.lower() or "gemini" in msg.lower()) else "STUDIO")
            clean_msg = msg
            if clean_msg.startswith("[TIKTOK AUTO]"):
                clean_msg = clean_msg.replace("[TIKTOK AUTO]", "").strip()
            self._append_log(platform, clean_msg)

    def _on_studio_progress_updated(self, val: int, detail: str) -> None:
        """Đồng bộ trạng thái thanh tiến trình bên phải theo tiến trình Studio."""
        if val < 0:
            # -1: Indeterminate (Đang chạy AI Whisper hoặc Upload TikTok)
            self._progress_bar.setRange(0, 0)
            if detail:
                self._progress_label.setText(f"Tiến độ: {detail}")
            elif not self._progress_label.text().startswith("Tiến độ: Đang"):
                self._progress_label.setText("Tiến độ: Đang xử lý...")
        elif val == 0:
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(0)
            if detail:
                self._progress_label.setText(f"Tiến độ: {detail}")
            else:
                self._progress_label.setText("Tiến độ: 0%")
        else:
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(min(100, max(0, val)))
            text = f"Tiến độ: {val}%"
            if detail:
                text += f" — {detail}"
            self._progress_label.setText(text)

    def _on_update_tools(self) -> None:
        reply = QMessageBox.question(
            self, "Cập nhật công cụ",
            "Bạn có muốn cập nhật yt-dlp & FFmpeg lên phiên bản mới nhất không?\n\n"
            "Quá trình sẽ mở terminal và có thể mất vài phút.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                subprocess.Popen(
                    [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                    if sys.platform == "win32" else 0,
                )
                QMessageBox.information(self, "Đang cập nhật",
                    "Quá trình cập nhật yt-dlp đã được khởi động trong terminal.")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể khởi động cập nhật:\n{e}")

    def _on_set_threads(self) -> None:
        from PyQt6.QtWidgets import QInputDialog
        val, ok = QInputDialog.getInt(
            self, "Số luồng tải đồng thời",
            "Nhập số luồng tải đồng thời (1–10):",
            self.max_workers, 1, 10
        )
        if ok:
            self.max_workers = val
            self._save_settings()
            self._append_log("HỆ THỐNG", f"Số luồng tải đồng thời đã đổi thành: {val}")

    # ══════════════════════════════════════════════════════════════════
    # XỬ LÝ SỰ KIỆN — BẢN QUYỀN
    # ══════════════════════════════════════════════════════════════════

    def _on_open_activation_dialog(self) -> None:
        """Mở dialog kích hoạt bản quyền."""
        dlg = ActivationDialog(
            parent=self,
            on_activated_callback=self._on_license_activated,
        )
        dlg.exec()

    def _on_license_activated(self) -> None:
        """Callback khi kích hoạt bản quyền thành công."""
        self._license_manager.invalidate_cache()
        self._update_license_statusbar()
        self._update_button_states()
        self._append_log(
            "HỆ THỐNG",
            "✅ Bản quyền PRO đã được kích hoạt thành công!"
        )

    def _update_license_statusbar(self) -> None:
        """Cập nhật nhãn bản quyền trên StatusBar."""
        c = COLORS
        is_licensed, status_text, expire_date, trial_remaining = \
            self._license_manager.get_status(use_cache=False)

        if is_licensed:
            self._sb_license_label.setText(status_text)
            self._sb_license_label.setStyleSheet(
                f"color: {c['status_success']}; padding: 0 8px; font-size: 11.5px; font-weight: 600;"
            )
            self._sb_upgrade_btn.setVisible(False)
        else:
            self._sb_license_label.setText(status_text)
            if trial_remaining <= 0:
                color = c['status_error']
            elif trial_remaining <= 3:
                color = c['status_warning']
            else:
                color = c['text_secondary']
            self._sb_license_label.setStyleSheet(
                f"color: {color}; padding: 0 8px; font-size: 11.5px; font-weight: 600;"
            )
            self._sb_upgrade_btn.setVisible(True)

    # ══════════════════════════════════════════════════════════════════
    # XỬ LÝ SỰ KIỆN — MENU TRỢ GIÚP
    # ══════════════════════════════════════════════════════════════════

    def _check_for_updates_automatically(self) -> None:
        self._start_update_check(manual=False)

    def _check_for_updates_manually(self) -> None:
        self._start_update_check(manual=True)

    def _start_update_check(self, manual: bool) -> None:
        if self._update_reply is not None:
            if manual:
                self._manual_update_check = True
            return

        request = QNetworkRequest(QUrl(GITHUB_RELEASE_API_URL))
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        request.setRawHeader(b"X-GitHub-Api-Version", b"2022-11-28")
        request.setRawHeader(b"User-Agent", b"OmniGrab-Updater")
        request.setTransferTimeout(10_000)
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
        )
        self._manual_update_check = manual
        self._update_reply = self._update_manager.get(request)
        self._update_reply.finished.connect(
            lambda reply=self._update_reply: self._on_update_check_finished(reply)
        )

    def _on_update_check_finished(self, reply: QNetworkReply) -> None:
        if reply is not self._update_reply:
            reply.deleteLater()
            return

        self._update_reply = None
        manual = self._manual_update_check
        self._manual_update_check = False
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                if manual:
                    QMessageBox.warning(
                        self,
                        "Không thể kiểm tra cập nhật",
                        f"Không kết nối được với GitHub:\n{reply.errorString()}",
                    )
                return

            payload = json.loads(bytes(reply.readAll()).decode("utf-8"))
            update = find_release_update(payload, APP_VERSION)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            if manual:
                QMessageBox.warning(
                    self,
                    "Không thể kiểm tra cập nhật",
                    f"Không đọc được thông tin phát hành:\n{exc}",
                )
            return
        finally:
            reply.deleteLater()

        if update is None:
            if manual:
                QMessageBox.information(
                    self,
                    "Kiểm tra cập nhật",
                    f"Bạn đang dùng phiên bản mới nhất (v{APP_VERSION}).",
                )
            return

        self._show_available_update(update)

    def _show_available_update(self, update: ReleaseUpdate) -> None:
        from ui.update_dialog import UpdateDialog

        dlg = UpdateDialog(update, parent=self)
        dlg.exec()

    def _on_about(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Thông tin OmniGrab")
        dlg.setWindowIcon(self.windowIcon())
        dlg.setFixedSize(520, 390)
        dlg.setStyleSheet("""
            QDialog { background: #0b0e14; color: #e2e8f0; }
            QLabel { color: #cbd5e1; }
            QLabel#appName { color: #f8fafc; font-size: 23px; font-weight: 700; }
            QLabel#versionBadge { color: #94a3b8; font-size: 12px; }
            QLabel#sectionTitle { color: #f8fafc; font-size: 14px; font-weight: 700; }
            QLabel#featureTitle { color: #e2e8f0; font-size: 12px; font-weight: 700; }
            QLabel#muted { color: #94a3b8; font-size: 11px; }
            QPushButton {
                background: #1e293b; color: #e2e8f0;
                border: 1px solid #334155; border-radius: 7px;
                padding: 7px 18px; min-width: 62px;
            }
            QPushButton:hover { background: #334155; }
        """)

        root = QVBoxLayout(dlg)
        root.setContentsMargins(22, 18, 22, 16)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(14)
        icon_label = QLabel()
        app_icon = self.windowIcon()
        if not app_icon.isNull():
            icon_label.setPixmap(app_icon.pixmap(52, 52))
        else:
            icon_label.setText("▶")
            icon_label.setStyleSheet("font-size: 30px; color: #22d3ee;")
        header.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

        title_stack = QVBoxLayout()
        title_row = QHBoxLayout()
        name = QLabel("OmniGrab Pro")
        name.setObjectName("appName")
        version = QLabel(f"v{APP_VERSION}")
        version.setObjectName("versionBadge")
        title_row.addWidget(name)
        title_row.addWidget(version, 0, Qt.AlignmentFlag.AlignVCenter)
        title_row.addStretch(1)
        title_stack.addLayout(title_row)

        summary = QLabel(
            "Công cụ desktop hỗ trợ tải video, quét danh sách kênh "
            "và xử lý phụ đề, lồng tiếng."
        )
        summary.setWordWrap(True)
        summary.setStyleSheet("color: #94a3b8; font-size: 12px;")
        title_stack.addWidget(summary)
        header.addLayout(title_stack, 1)
        root.addLayout(header)

        platforms = QLabel("TikTok   ·   Douyin   ·   Facebook   ·   YouTube")
        platforms.setStyleSheet(
            "color: #7dd3fc; font-size: 11px; font-weight: 600; padding-left: 2px;"
        )
        root.addWidget(platforms)

        section = QLabel("TÍNH NĂNG CHÍNH")
        section.setObjectName("sectionTitle")
        root.addWidget(section)

        features = QGridLayout()
        features.setHorizontalSpacing(26)
        features.setVerticalSpacing(12)
        feature_items = (
            ("Tải video", "Tải nhiều liên kết và theo dõi tiến trình."),
            ("Quét kênh", "Lọc danh sách theo dữ liệu video khả dụng."),
            ("Studio lồng tiếng", "Nhận dạng, dịch và xuất phụ đề hoặc video."),
            ("Xuất danh sách", "Lưu kết quả quét thành tệp CSV."),
        )
        for index, (feature_title, description) in enumerate(feature_items):
            item = QVBoxLayout()
            item.setSpacing(3)
            heading = QLabel(feature_title)
            heading.setObjectName("featureTitle")
            detail = QLabel(description)
            detail.setWordWrap(True)
            detail.setStyleSheet("color: #94a3b8; font-size: 11px;")
            item.addWidget(heading)
            item.addWidget(detail)
            features.addLayout(item, index // 2, index % 2)
        root.addLayout(features)

        tech_label = QLabel("CÔNG NGHỆ")
        tech_label.setObjectName("sectionTitle")
        root.addWidget(tech_label)
        tech = QLabel("PyQt6  ·  yt-dlp  ·  FFmpeg  ·  faster-whisper  ·  Edge-TTS")
        tech.setWordWrap(True)
        tech.setStyleSheet("color: #94a3b8; font-size: 11px;")
        root.addWidget(tech)

        footer = QHBoxLayout()
        footer.addStretch(1)
        close_button = QPushButton("Đóng")
        close_button.clicked.connect(dlg.accept)
        footer.addWidget(close_button, 0, Qt.AlignmentFlag.AlignRight)
        root.addLayout(footer)
        dlg.exec()

    def _on_guide(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Trung tâm trợ giúp OmniGrab")
        dlg.resize(860, 620)
        dlg.setMinimumSize(700, 500)
        dlg.setStyleSheet("""
            QDialog { background: #0b0e14; }
            QListWidget { background: #0f1724; border: 1px solid #1e293b; border-radius: 10px; padding: 6px; outline: 0; }
            QListWidget::item { color: #cbd5e1; padding: 12px 10px; border-radius: 7px; }
            QListWidget::item:selected { background: #172554; color: #bfdbfe; }
            QListWidget::item:hover:!selected { background: #172033; }
            QTextBrowser { background: #0f1724; border: 1px solid #1e293b; border-radius: 10px; padding: 18px; color: #e2e8f0; }
            QPushButton { background: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 7px; padding: 8px 22px; }
            QPushButton:hover { background: #334155; }
        """)
        root = QVBoxLayout(dlg)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        body = QHBoxLayout()
        body.setSpacing(8)
        nav = QListWidget(dlg)
        nav.setFixedWidth(190)
        pages = QTextBrowser(dlg)
        pages.setOpenExternalLinks(True)
        pages.setMinimumWidth(430)
        body.addWidget(nav)
        body.addWidget(pages, 1)
        root.addLayout(body, 1)

        sections = [
            ("Bắt đầu", "#06b6d4", """
                <p class='lead'>Bắt đầu nhanh</p><p>Chọn nơi lưu, nhập liên kết và theo dõi tiến trình ngay trong cửa sổ chính.</p>
                <div class='card'><b>1. Chọn thư mục</b><br>Mở <b>Tệp → Thư mục lưu video</b> và chọn ổ đĩa còn dung lượng.</div>
                <div class='card'><b>2. Chọn cách làm việc</b><br>Dán link video trên trang Tải theo link, hoặc mở <b>Chế độ tải → Quét Kênh</b> bằng <kbd>Ctrl+2</kbd>.</div>
                <div class='card'><b>3. Theo dõi và kiểm tra</b><br>Đợi ứng dụng báo hoàn tất, sau đó mở thư mục lưu để xem file. Không mở file khi tiến trình vẫn đang ghi.</div>
                <div class='note blue'><b>Mẹo:</b> Khi gặp lỗi lần đầu, thử một video/link đơn lẻ để dễ xác định vấn đề.</div>
            """),
            ("Tải video", "#3b82f6", """
                <p class='lead'>Tải theo liên kết</p><ol><li>Dán URL video đầy đủ vào ô nhập.</li><li>Có thể dán nhiều link, mỗi link một dòng; kiểm tra số link được nhận diện.</li><li>Chọn thư mục lưu rồi nhấn <b>BẮT ĐẦU TẢI</b>.</li></ol>
                <h3>Nếu link không hợp lệ</h3><ul><li>Mở video trong trình duyệt và sao chép URL trên thanh địa chỉ.</li><li>Không dùng link trang tìm kiếm, trang chủ hoặc link đã bị cắt.</li><li>Với link chia sẻ trong ứng dụng chat, mở link trong trình duyệt trước rồi sao chép địa chỉ sau khi chuyển hướng.</li></ul>
                <h3>Nếu tải đứng hoặc thất bại</h3><ol><li>Mở cùng video trong trình duyệt để kiểm tra Internet và quyền xem.</li><li>Thử một link riêng lẻ; nếu chạy nhiều link, giảm số luồng trong <b>Công cụ → Cài đặt số luồng tải đồng thời</b>.</li><li>Kiểm tra ổ đĩa còn chỗ trống. Dừng tác vụ, chờ dừng hẳn rồi mới thử lại.</li></ol>
                <div class='note amber'>Video riêng tư, bị xóa, giới hạn tuổi/khu vực hoặc yêu cầu đăng nhập có thể không tải được nếu tài khoản không có quyền xem.</div>
            """),
            ("Quét kênh", "#22c55e", """
                <p class='lead'>Quét, lọc và chọn video</p><ol><li>Mở <b>Quét Kênh</b> bằng <kbd>Ctrl+2</kbd>.</li><li>Dán URL hồ sơ, fanpage, kênh hoặc playlist phù hợp.</li><li>Chọn số lượng hoặc <b>All</b>, sau đó nhấn <b>Quét kênh</b>.</li><li>Chờ hoàn tất, tích video cần tải và nhấn <b>BẮT ĐẦU TẢI</b>.</li></ol>
                <h3>Kết quả ít hoặc danh sách trống</h3><ul><li>Tạm đặt lượt xem/lượt thích thành <b>Không lọc</b> và thời lượng/ngày đăng thành <b>Tất cả</b>; các bộ lọc kết hợp với nhau.</li><li>Thử URL tab Video/Reels chính thức thay URL trang chủ.</li><li>Mở URL trong trình duyệt để xác nhận trang công khai và tài khoản xem được.</li><li>Nạp cookie mới của đúng nền tảng nếu trang yêu cầu đăng nhập.</li></ul>
                <div class='note amber'><b>Về All:</b> All yêu cầu lấy toàn bộ mục scraper nhận được. Một số nền tảng chỉ gửi một phần danh sách, yêu cầu cuộn trang hoặc giới hạn truy cập; OmniGrab không thể lấy mục mà nền tảng không trả về.</div>
                <h3>Thiếu lượt thích, lượt xem, ngày hoặc thời lượng</h3><p>Nền tảng có thể ẩn metadata trong danh sách. Video vẫn có thể tải được; thử mở video trực tiếp để kiểm tra.</p>
            """),
            ("Cookie và 403", "#f59e0b", """
                <p class='lead'>Đăng nhập, cookie và lỗi 403</p><p>Cookie là phiên đăng nhập của bạn. Chỉ xuất và dùng cookie trên thiết bị tin cậy.</p>
                <ol><li>Đăng nhập đúng tài khoản trong trình duyệt và mở website cần dùng.</li><li>Nếu website yêu cầu CAPTCHA/xác minh, hoàn tất bằng trình duyệt.</li><li>Dùng extension xuất cookie dạng Netscape <code>.txt</code> khi đang ở đúng domain.</li><li>Trong OmniGrab chọn <b>Tệp → Nạp file Cookie</b>, sau đó thử một video.</li></ol>
                <div class='card'><b>Chọn đúng cookie</b><br>TikTok và Douyin là hai phiên riêng. Cookie tải video cũng không thay cookie upload.</div>
                <p>Nếu vẫn báo 403/login, đăng nhập lại, xuất cookie mới và thử sau vài phút. Cookie có thể hết hạn hoặc bị thu hồi.</p>
                <div class='note red'><b>Bảo vệ tài khoản:</b> Không gửi cookie, mật khẩu, token hay ảnh chụp có chứa những dữ liệu này. Nếu nghi cookie bị lộ, thu hồi phiên đăng nhập từ cài đặt tài khoản.</div>
            """),
            ("File tải về", "#a855f7", """
                <p class='lead'>Video tải xong nhưng không mở được</p><ol><li>Đợi ứng dụng báo hoàn tất hoàn toàn.</li><li>Kiểm tra kích thước file trong thư mục lưu. File 0 KB hoặc nhỏ bất thường thường là tải chưa xong.</li><li>Kiểm tra dung lượng ổ đĩa, xóa file tải lỗi và tải lại khi mạng ổn định.</li><li>Thử phát bằng VLC hoặc trình phát khác để loại trừ vấn đề codec.</li></ol>
                <h3>Video có hình nhưng thiếu tiếng</h3><p>Tải lại video. Một số nguồn gửi hình và tiếng ở hai luồng riêng; ứng dụng cần FFmpeg để ghép chúng.</p>
                <h3>Không tìm thấy FFmpeg</h3><p>Khởi động lại OmniGrab. Nếu thông báo vẫn còn, kiểm tra <code>ffmpeg.exe</code> trong thư mục cài đặt hoặc cài lại ứng dụng từ bộ cài đáng tin cậy.</p>
            """),
            ("Lồng tiếng AI", "#ec4899", """
                <p class='lead'>Phụ đề, dịch và lồng tiếng</p><ol><li>Mở video trong Studio và chọn đúng ngôn ngữ lời thoại gốc tại <b>Công cụ → Cài đặt Lồng tiếng AI</b>.</li><li>Bóc tách kịch bản, rà lại câu nhận dạng, bản dịch và mốc thời gian.</li><li>Xuất SRT để kiểm tra trước, hoặc xuất video lồng tiếng khi nội dung đã ổn.</li></ol>
                <div class='card'><b>Các dịch vụ cần kết nối</b><br>Bản cài đặt có sẵn mô hình Whisper base; nếu chọn mô hình khác, ứng dụng sẽ tải mô hình đó lần đầu. gTTS cần Internet. Gemini cần API key hợp lệ và còn hạn mức nếu bạn chọn dùng Gemini.</div>
                <h3>Whisper nhận sai hoặc không nghe thấy lời thoại</h3><p>Kiểm tra video có tiếng rõ, chọn đúng ngôn ngữ nguồn và rà lại kịch bản. Nhạc lớn, tiếng ồn hoặc nhiều người nói chồng nhau làm giảm độ chính xác.</p>
                <h3>Dịch/TTS không hoạt động</h3><p>Kiểm tra Internet; kiểm tra API key/quota Gemini nếu đang dùng. Thử lại sau vài phút hoặc thử video ngắn hơn.</p>
                <div class='note red'><b>“File âm thanh tiếng Việt bị rỗng”:</b> Các câu giọng đọc chưa ghép thành track hoàn chỉnh. Xem dòng <b>[AUDIO MIX]</b> ngay trước lỗi. Nếu ứng dụng báo giữ thư mục tạm, giữ nguyên thư mục đó và gửi đường dẫn cùng thông báo lỗi cho hỗ trợ; không gửi cookie/API key.</div>
            """),
            ("Đăng video", "#ef4444", """
                <p class='lead'>Đăng video lên TikTok hoặc YouTube</p><ol><li>Đăng nhập đúng tài khoản/kênh đích trong trình duyệt.</li><li>Nạp cookie upload riêng của nền tảng cần đăng.</li><li>Kiểm tra file, quyền riêng tư, tiêu đề, mô tả và lịch đăng.</li><li>Thử một video trước khi chạy nhiều video.</li></ol>
                <div class='note amber'>Nếu tiến trình dừng hoặc không rõ đã đăng chưa, vào trang kênh kiểm tra trước khi chạy lại để tránh đăng trùng. Nếu trình duyệt yêu cầu xác minh, hoàn tất trên trang rồi thử lại.</div>
            """),
            ("Nhờ hỗ trợ", "#06b6d4", """
                <p class='lead'>Chuẩn bị thông tin khi cần hỗ trợ</p><p>Để người hỗ trợ tìm đúng nguyên nhân, hãy gửi:</p><ul><li>Nền tảng và tính năng đang dùng.</li><li>Bước vừa thực hiện và thời điểm lỗi xảy ra.</li><li>Toàn bộ dòng lỗi liên quan trong nhật ký, đặc biệt các dòng ngay trước lỗi cuối.</li><li>URL công khai nếu bạn có quyền chia sẻ và đã bỏ thông tin riêng tư.</li><li>Các bước bạn đã thử và kết quả.</li></ul>
                <div class='note red'><b>Không gửi:</b> mật khẩu, cookie, token, Gemini API key hoặc ảnh màn hình có chứa các thông tin đó.</div>
            """),
        ]

        page_template = """<!doctype html><html><head><meta charset='utf-8'><style>
            body { font-family: 'Segoe UI', Arial, sans-serif; color: #cbd5e1; font-size: 14px; line-height: 1.65; }
            h1 { color: #f8fafc; font-size: 24px; margin: 0 0 8px; }
            h3 { color: #e2e8f0; font-size: 15px; margin: 22px 0 6px; }
            p { margin: 7px 0 12px; } .lead { color: ACCENT; font-size: 17px; font-weight: 700; margin-top: 0; }
            ol, ul { padding-left: 22px; } li { margin: 5px 0; }
            .card { background: #111827; border: 1px solid #263449; border-left: 3px solid ACCENT; border-radius: 8px; padding: 12px 14px; margin: 10px 0; }
            .note { border-radius: 8px; padding: 11px 14px; margin: 14px 0; background: #111827; }
            .blue { border: 1px solid #1d4ed8; } .amber { border: 1px solid #a16207; } .red { border: 1px solid #991b1b; }
            code, kbd { color: #bfdbfe; background: #172033; padding: 2px 5px; border-radius: 4px; }
        </style></head><body><h1>TITLE</h1>BODY</body></html>"""
        html_pages = []
        for title, accent, content in sections:
            nav.addItem(title)
            html_pages.append(page_template.replace("TITLE", title).replace("ACCENT", accent).replace("BODY", content))

        def show_section(index: int) -> None:
            if 0 <= index < len(html_pages):
                pages.setHtml(html_pages[index])

        nav.currentRowChanged.connect(show_section)
        nav.setCurrentRow(0)

        footer = QHBoxLayout()
        footer.addStretch(1)
        close_button = QPushButton("Đóng", dlg)
        close_button.clicked.connect(dlg.accept)
        footer.addWidget(close_button)
        root.addLayout(footer)
        dlg.exec()

    # ══════════════════════════════════════════════════════════════════
    # XỬ LÝ SỰ KIỆN — TRANG 0 (Link)
    # ══════════════════════════════════════════════════════════════════

    def _on_paste_clipboard(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            text = clipboard.text()
            if text.strip():
                current = self._url_input.toPlainText().strip()
                combined = (current + "\n" if current else "") + text
                self._url_input.setPlainText(combined)

    def _on_url_text_changed(self) -> None:
        raw = self._url_input.toPlainText()
        urls = extract_urls(raw)
        count = len(urls)
        self._url_count_label.setText(f"{count} liên kết phát hiện")
        if count > 0:
            self._url_count_label.setStyleSheet(
                f"color:{COLORS['accent_green']}; font-size:12px; font-weight:600;"
            )
        else:
            self._url_count_label.setStyleSheet(
                f"color:{COLORS['text_muted']}; font-size:12px;"
            )

    # ══════════════════════════════════════════════════════════════════
    # XỬ LÝ SỰ KIỆN — TRANG 1 (Quét Kênh)
    # ══════════════════════════════════════════════════════════════════

    def _on_scan_channel(self) -> None:
        url = self._channel_url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập URL kênh / trang cá nhân!")
            return
        if self._is_scanning:
            return

        limit_text = self._scan_limit_combo.currentText().strip()
        is_all = limit_text.casefold() == "all"
        if is_all:
            max_videos = 0
        elif limit_text.isdigit() and 0 < int(limit_text) <= 1000000:
            max_videos = int(limit_text)
        else:
            QMessageBox.warning(self, "Số lượng video không hợp lệ", "Nhập số nguyên từ 1 đến 1.000.000 hoặc chọn All.")
            return

        # Thử quét trước: Nếu đã nạp Cookie thì dùng, nếu chưa có thì quét trực tiếp
        # Chỉ khi nào quét không được mới hiện thông báo yêu cầu Cookie trong _on_scan_error
        if self.cookies_path:
            self._append_log("HỆ THỐNG", f"Đang quét kênh (sử dụng Cookie đã nạp): {url}")
        else:
            self._append_log("HỆ THỐNG", f"Đang thử quét kênh trực tiếp không Cookie: {url}")

        self._result_table.setRowCount(0)
        self._scanned_videos = []
        self._lbl_scan_count.setText("0 video")
        self._lbl_selected_count.setText("Đã chọn: 0 video")
        self._btn_export_csv.setEnabled(False)
        self._is_scanning = True
        self._btn_scan.setEnabled(False)
        self._btn_scan.setText("⏳ Đang quét...")
        self._scan_status_label.setText("Đang quét kênh, vui lòng chờ...")
        self._scan_status_label.setStyleSheet(
            f"color:{COLORS['accent_orange']}; font-size:12px; font-weight:600;"
        )

        min_views = self._filter_min_views.value()
        min_likes = self._filter_min_likes.value()
        duration_filter = self._filter_duration.currentText()
        date_filter = self._filter_date.currentText()

        self._scan_worker = ScanChannelWorker(
            channel_url=url,
            max_videos=max_videos,
            cookie_file=self.cookies_path,
            min_views=min_views,
            min_likes=min_likes,
            duration_filter=duration_filter,
            date_filter=date_filter,
            parent=self,
        )
        self._scan_worker.scan_progress.connect(self._on_scan_progress)
        self._scan_worker.video_found.connect(self._on_video_found)
        self._scan_worker.scan_finished.connect(self._on_scan_finished)
        self._scan_worker.scan_error.connect(self._on_scan_error)
        self._scan_worker.finished.connect(self._on_scan_worker_done)
        self._scan_worker.start()

        parts = []
        if min_views > 0:
            parts.append(f"xem>={min_views:,}")
        if min_likes > 0:
            parts.append(f"thích>={min_likes:,}")
        if duration_filter != "Tất cả":
            parts.append(duration_filter)
        if date_filter != "Tất cả":
            parts.append(date_filter)
        finfo = f" | Lọc: {', '.join(parts)}" if parts else ""
        limit_label = "All video khả dụng" if is_all else f"tối đa {max_videos} video"
        self._append_log("HỆ THỐNG", f"Quét kênh: {url} ({limit_label}{finfo})")

    def _on_scan_progress(self, message: str) -> None:
        self._scan_status_label.setText(message)
        self._status_bar.showMessage(f"Quét kênh: {message}")

    def _on_video_found(self, video: dict) -> None:
        self._scanned_videos.append(video)
        row = self._result_table.rowCount()
        self._result_table.blockSignals(True)
        self._result_table.insertRow(row)

        chk = QTableWidgetItem()
        chk.setCheckState(Qt.CheckState.Checked)
        chk.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        chk.setData(Qt.ItemDataRole.UserRole, video)
        self._result_table.setItem(row, 0, chk)

        ti = QTableWidgetItem(video.get("title", ""))
        ti.setToolTip(f"{video.get('title', '')}\n\n💡 Nhấp đúp chuột để mở xem video này trên trình duyệt.")
        self._result_table.setItem(row, 1, ti)

        vi = QTableWidgetItem(video.get("views", "--"))
        vi.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        vi.setForeground(QColor("#38bdf8"))
        if str(video.get("views", "")).startswith("~"):
            vi.setToolTip(
                f"Lượt xem ước tính: {video.get('views', '')}\n"
                f"(Douyin bảo mật và không công khai lượt xem gốc trên Web API).\n"
                f"💡 Con số này được tính tự động từ {video.get('likes_raw', 0):,} lượt thích với tỷ lệ tương tác chuẩn ~20x.\n"
                f"Bạn cũng có thể xem số lượt thích thực tế ở cột Lượt thích bên cạnh."
            )
        self._result_table.setItem(row, 2, vi)

        li = QTableWidgetItem(video.get("likes", "--"))
        li.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        li.setForeground(QColor("#f472b6"))
        self._result_table.setItem(row, 3, li)

        di = QTableWidgetItem(video.get("duration", "--:--"))
        di.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_table.setItem(row, 4, di)

        dai = QTableWidgetItem(video.get("upload_date", "--/--/----"))
        dai.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_table.setItem(row, 5, dai)

        ui = QTableWidgetItem(video.get("url", ""))
        ui_font = ui.font()
        ui_font.setUnderline(True)
        ui.setFont(ui_font)
        ui.setToolTip(
            f"🌐 Nhấp vào đây hoặc nhấp đúp để mở video. Với TikTok, ứng dụng thử trình phát nhúng chính thức trước.\n"
            f"Liên kết gốc: {video.get('url', '')}"
        )
        ui.setForeground(QColor(COLORS["accent_blue"]))
        self._result_table.setItem(row, 6, ui)

        self._result_table.setRowHeight(row, 32)
        self._result_table.blockSignals(False)
        self._lbl_scan_count.setText(f"{self._result_table.rowCount()} video")
        self._update_selected_count()

    def _on_scan_finished(self, videos: list) -> None:
        count = len(videos)
        self._scan_status_label.setText(f"✅ Quét hoàn tất! Tìm thấy {count} video.")
        self._scan_status_label.setStyleSheet(
            f"color:{COLORS['accent_green']}; font-size:12px; font-weight:600;"
        )
        self._append_log("HỆ THỐNG", f"Quét kênh hoàn tất: {count} video.")
        self._btn_export_csv.setEnabled(count > 0)
        self._update_selected_count()

    def _on_scan_error(self, error: str) -> None:
        self._scan_status_label.setText(f"❌ Lỗi: {error}")
        self._scan_status_label.setStyleSheet(
            f"color:{COLORS['accent_red']}; font-size:12px; font-weight:600;"
        )
        self._append_log("HỆ THỐNG", f"Lỗi quét kênh: {error}")

        # Kiểm tra nếu lỗi do thiếu thư viện phụ thuộc
        url_curr = self._channel_url_input.text().strip().lower()
        err_lower = (error or "").lower()

        is_missing_dep = (
            "chưa được cài đặt" in err_lower
            or "pip install" in err_lower
            or "modulenotfound" in err_lower
            or "importerror" in err_lower
        )
        is_cookie_block = (
            not is_missing_dep
            and (
                "cookie" in err_lower
                or "chặn" in err_lower
                or "đăng nhập" in err_lower
                or "truy cập" in err_lower
                or not self.cookies_path
            )
        )
        is_platform = (
            "tiktok.com" in url_curr
            or "facebook.com" in url_curr
            or "fb.com" in url_curr
        )

        if "unable to extract secondary user id" in err_lower or "tiktok:user" in err_lower:
            QMessageBox.warning(
                self,
                "TikTok chặn quét danh sách kênh",
                "⚠️ TikTok hiện đang bật tường lửa chống cào dữ liệu tự động (Anti-Scraping WAF) "
                "đối với trang cá nhân (@username), nên yt-dlp không thể tự động duyệt danh sách toàn bộ video của kênh này.\n\n"
                "💡 GIẢI PHÁP ĐƠN GIẢN:\n"
                "1. Bạn hãy copy đường link của các video cần tải trong kênh đó.\n"
                "2. Chuyển sang tab 'Tải theo danh sách link' (Ctrl+1) và dán link vào.\n"
                "3. Bấm 'Bắt đầu tải' — Tải trọn vẹn 100% Full HD không logo, không cần Cookie!"
            )
        elif is_cookie_block and is_platform:
            fail_dlg = CookieFailedDialog(error_message=error, parent=self)
            fail_dlg.exec()
            if fail_dlg.action_result == CookieFailedDialog.ACTION_LOAD_COOKIE:
                if self._on_choose_cookie():
                    # Đã nạp thành công, tự động quét lại ngay
                    QTimer.singleShot(250, self._on_scan_channel)
            elif fail_dlg.action_result == CookieFailedDialog.ACTION_SHOW_GUIDE:
                self._show_cookie_guide()
        else:
            QMessageBox.critical(self, "Lỗi quét kênh", f"Không thể lấy danh sách video:\n\n{error}")

    def _on_scan_worker_done(self) -> None:
        self._is_scanning = False
        self._btn_scan.setEnabled(True)
        self._btn_scan.setText("🔍  Quét kênh")
        self._scan_worker = None
        self._status_bar.showMessage("Trạng thái: Sẵn sàng")

    def _on_viral_filter_changed(self) -> None:
        """Lọc động tức thì danh sách video hiển thị trong bảng khi người dùng thay đổi bộ lọc Viral."""
        min_views = self._filter_min_views.value()
        min_likes = self._filter_min_likes.value()
        duration_filter = self._filter_duration.currentText()
        date_filter = self._filter_date.currentText()

        from datetime import date, timedelta
        days_map = {"3 ngày qua": 3, "7 ngày qua": 7, "30 ngày qua": 30}
        cutoff_date = (date.today() - timedelta(days=days_map[date_filter])) if date_filter in days_map else None

        total_rows = self._result_table.rowCount()
        if total_rows == 0:
            return

        from core.worker import ScanChannelWorker
        visible_count = 0
        self._result_table.blockSignals(True)
        for r in range(total_rows):
            chk = self._result_table.item(r, 0)
            if not chk:
                continue
            video = chk.data(Qt.ItemDataRole.UserRole)
            if not video and r < len(self._scanned_videos):
                video = self._scanned_videos[r]

            passes = True
            if video:
                # 1. Lượt xem
                if min_views > 0:
                    v_raw = video.get("views_raw", 0)
                    if not v_raw and video.get("view_count"):
                        v_raw = video.get("view_count")
                    if not v_raw and video.get("views"):
                        v_raw = ScanChannelWorker._parse_count_value(video.get("views"))
                    try:
                        v_raw = int(v_raw)
                    except Exception:
                        v_raw = 0
                    if v_raw < min_views:
                        passes = False

                # 2. Lượt thích
                if passes and min_likes > 0:
                    l_raw = video.get("likes_raw", 0)
                    if not l_raw and video.get("like_count"):
                        l_raw = video.get("like_count")
                    if not l_raw and video.get("likes"):
                        l_raw = ScanChannelWorker._parse_count_value(video.get("likes"))
                    try:
                        l_raw = int(l_raw)
                    except Exception:
                        l_raw = 0
                    if l_raw < min_likes:
                        passes = False

                # 3. Thời lượng
                if passes and duration_filter != "Tất cả":
                    dur_sec = ScanChannelWorker._parse_duration_seconds(video)
                    if duration_filter == "Dưới 60 giây (Shorts/Reels)":
                        if dur_sec is None or dur_sec >= 60:
                            passes = False
                    elif duration_filter == "Trên 60 giây":
                        if dur_sec is None or dur_sec < 60:
                            passes = False

                # 4. Ngày đăng
                if passes and cutoff_date is not None:
                    v_date = ScanChannelWorker._parse_upload_date(video)
                    if not v_date or v_date < cutoff_date:
                        passes = False

            self._result_table.setRowHidden(r, not passes)
            if passes:
                visible_count += 1
                chk.setCheckState(Qt.CheckState.Checked)
            else:
                chk.setCheckState(Qt.CheckState.Unchecked)

        self._result_table.blockSignals(False)
        if visible_count < total_rows:
            self._lbl_scan_count.setText(f"{visible_count}/{total_rows} video")
        else:
            self._lbl_scan_count.setText(f"{total_rows} video")

        active_conditions = 0
        if min_views > 0:
            active_conditions += 1
        if min_likes > 0:
            active_conditions += 1
        if duration_filter != "Tất cả":
            active_conditions += 1
        if date_filter != "Tất cả":
            active_conditions += 1

        if hasattr(self, "_filter_section"):
            if active_conditions > 0:
                self._filter_section.set_badge(f"Đang lọc ({active_conditions})", is_active=True)
            else:
                self._filter_section.set_badge("", is_active=False)

        self._update_selected_count()

    def _on_select_all(self) -> None:
        self._result_table.blockSignals(True)
        for r in range(self._result_table.rowCount()):
            if not self._result_table.isRowHidden(r):
                it = self._result_table.item(r, 0)
                if it:
                    it.setCheckState(Qt.CheckState.Checked)
        self._result_table.blockSignals(False)
        self._update_selected_count()

    def _on_deselect_all(self) -> None:
        self._result_table.blockSignals(True)
        for r in range(self._result_table.rowCount()):
            it = self._result_table.item(r, 0)
            if it:
                it.setCheckState(Qt.CheckState.Unchecked)
        self._result_table.blockSignals(False)
        self._update_selected_count()

    def _on_table_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() == 0:
            self._update_selected_count()

    def _on_table_cell_clicked(self, row: int, col: int) -> None:
        """Nhấp vào ô trong bảng. Nếu nhấp vào cột URL (cột 6) sẽ mở video ngay."""
        if col == 6:
            self._open_video_url_at_row(row)

    def _on_table_cell_double_clicked(self, row: int, col: int) -> None:
        """Nhấp đúp chuột vào bất kỳ ô nào trên dòng (trừ checkbox) để mở video kiểm tra."""
        if col != 0:
            self._open_video_url_at_row(row)

    def _open_video_url_at_row(self, row: int) -> None:
        """Mở video; với TikTok ưu tiên player nhúng chính thức, giữ URL gốc làm fallback."""
        chk = self._result_table.item(row, 0)
        url = ""
        video = None
        if chk:
            video = chk.data(Qt.ItemDataRole.UserRole)
            if video:
                url = video.get("url", "").strip()

        if not url:
            url_item = self._result_table.item(row, 6)
            if url_item:
                url = url_item.text().strip()

        if url and (url.startswith("http://") or url.startswith("https://")):
            player_url = self._get_tiktok_player_url(url, video or {})
            QDesktopServices.openUrl(QUrl(player_url))
            label = "trình phát TikTok" if player_url != url else "video trong trình duyệt"
            self._status_bar.showMessage(f"Đang mở {label}: {player_url}", 5000)

    @staticmethod
    def _get_tiktok_player_url(url: str, video: Optional[Dict[str, Any]] = None) -> str:
        """Tạo URL player nhúng chính thức cho TikTok; nền tảng khác giữ URL ban đầu."""
        if "tiktok.com" not in (url or "").lower():
            return url

        video_id = str((video or {}).get("id") or "").strip()
        if not video_id:
            path_parts = QUrl(url).path().rstrip("/").split("/")
            video_id = path_parts[-1] if path_parts else ""

        if video_id.isdigit():
            return f"https://www.tiktok.com/player/v1/{video_id}"
        return url

    def _on_table_context_menu(self, pos) -> None:
        """Menu chuột phải trên bảng kết quả để mở video hoặc sao chép thông tin."""
        item = self._result_table.itemAt(pos)
        if not item:
            return
        row = item.row()
        chk_item = self._result_table.item(row, 0)
        video = chk_item.data(Qt.ItemDataRole.UserRole) if chk_item else None
        url = (video.get("url") if video else "") or (self._result_table.item(row, 6).text().strip() if self._result_table.item(row, 6) else "")
        title = (video.get("title") if video else "") or (self._result_table.item(row, 1).text().strip() if self._result_table.item(row, 1) else "")

        menu = QMenu(self)
        act_open = menu.addAction("Mở video (Player nhúng)")
        act_open.setIcon(get_svg_icon("play"))
        act_open_original = menu.addAction("Mở URL gốc của video")
        act_open_original.setIcon(get_svg_icon("external-link"))
        menu.addSeparator()
        act_copy_url = menu.addAction("Sao chép liên kết URL")
        act_copy_url.setIcon(get_svg_icon("link"))
        act_copy_title = menu.addAction("Sao chép tiêu đề video")
        act_copy_title.setIcon(get_svg_icon("clipboard"))
        menu.addSeparator()
        is_checked = chk_item and chk_item.checkState() == Qt.CheckState.Checked
        act_toggle = menu.addAction("Bỏ chọn video này" if is_checked else "Tích chọn video này")
        act_toggle.setIcon(get_svg_icon("square" if is_checked else "check-square"))

        action = menu.exec(self._result_table.viewport().mapToGlobal(pos))
        if action == act_open:
            self._open_video_url_at_row(row)
        elif action == act_open_original and url:
            QDesktopServices.openUrl(QUrl(url))
            self._status_bar.showMessage(f"Đang mở URL gốc: {url}", 5000)
        elif action == act_copy_url and url:
            QApplication.clipboard().setText(url)
            self._status_bar.showMessage(f"Đã sao chép URL: {url}", 3000)
        elif action == act_copy_title and title:
            QApplication.clipboard().setText(title)
            self._status_bar.showMessage("Đã sao chép tiêu đề video", 3000)
        elif action == act_toggle and chk_item:
            new_state = Qt.CheckState.Unchecked if is_checked else Qt.CheckState.Checked
            chk_item.setCheckState(new_state)
            self._update_selected_count()

    def _update_selected_count(self) -> None:
        count = sum(
            1 for r in range(self._result_table.rowCount())
            if not self._result_table.isRowHidden(r)
            and self._result_table.item(r, 0)
            and self._result_table.item(r, 0).checkState() == Qt.CheckState.Checked
        )
        self._lbl_selected_count.setText(f"Đã chọn: {count} video")
        clr = COLORS["status_success"] if count > 0 else COLORS["text_muted"]
        self._lbl_selected_count.setStyleSheet(
            f"color:{clr}; font-size:12px;" + (" font-weight:600;" if count > 0 else "")
        )
        if hasattr(self, "_btn_export_csv"):
            self._btn_export_csv.setEnabled(count > 0)
        self._update_button_states()

    def _on_export_csv(self) -> None:
        export_videos = []
        for r in range(self._result_table.rowCount()):
            if not self._result_table.isRowHidden(r):
                chk = self._result_table.item(r, 0)
                if chk and chk.data(Qt.ItemDataRole.UserRole):
                    export_videos.append(chk.data(Qt.ItemDataRole.UserRole))
                elif r < len(self._scanned_videos):
                    export_videos.append(self._scanned_videos[r])

        if not export_videos:
            QMessageBox.warning(self, "Thông báo", "Không có dữ liệu video phù hợp để xuất.")
            return
        default = os.path.join(
            self.output_dir, f"omni_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Xuất danh sách sang CSV", default, "CSV (*.csv);;Tất cả (*.*)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(
                    f,
                    fieldnames=["title", "views", "likes", "duration", "upload_date", "url", "id"],
                    extrasaction="ignore",
                )
                w.writeheader()
                w.writerows(export_videos)
            self._append_log(
                "HỆ THỐNG",
                f"Xuất {len(export_videos)} video ra CSV: {os.path.basename(path)}"
            )
            QMessageBox.information(
                self, "Thành công", f"Đã xuất {len(export_videos)} video ra:\n{path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể ghi file CSV:\n{e}")

    # ══════════════════════════════════════════════════════════════════
    # XỬ LÝ SỰ KIỆN — TẢI VIDEO (Chung)
    # ══════════════════════════════════════════════════════════════════

    def _check_license_before_download(self) -> bool:
        """Kiểm tra bản quyền / lượt dùng thử trước khi tải."""
        is_licensed, _, _, trial_remaining = \
            self._license_manager.get_status(use_cache=False)
        if not is_licensed and trial_remaining <= 0:
            QMessageBox.warning(
                self,
                "Hết lượt dùng thử",
                "🔒 Bạn đã sử dụng hết 10 lượt tải miễn phí.\n\n"
                "Vui lòng kích hoạt bản quyền PRO để tiếp tục tải không giới hạn."
            )
            self._on_open_activation_dialog()
            return False
        return True

    def start_download(self) -> None:
        """Trang 0: Bắt đầu tải theo danh sách link dán trong ô nhập liệu."""
        if not self._check_license_before_download():
            return

        urls = extract_urls(self._url_input.toPlainText())
        if not urls:
            QMessageBox.warning(
                self, "Cảnh báo",
                "Không tìm thấy liên kết hợp lệ!\n\n"
                "Hãy dán ít nhất một liên kết TikTok, Douyin, Facebook hoặc YouTube."
            )
            return

        self._start_download_with_urls(urls)

    def start_channel_selected_download(self) -> None:
        """Trang 1: Bắt đầu tải các video đã tick chọn trong bảng Quét kênh."""
        if not self._check_license_before_download():
            return

        urls = []
        for r in range(self._result_table.rowCount()):
            if self._result_table.isRowHidden(r):
                continue
            chk = self._result_table.item(r, 0)
            url_item = self._result_table.item(r, 6)
            if chk and url_item and chk.checkState() == Qt.CheckState.Checked:
                u = url_item.text().strip()
                if u:
                    urls.append(u)
        if not urls:
            QMessageBox.warning(
                self, "Cảnh báo",
                "Chưa chọn video nào trong danh sách!\n"
                "Hãy tích checkbox ít nhất một video."
            )
            return

        self._start_download_with_urls(urls)

    def stop_download(self) -> None:
        """Dừng quá trình tải video đang chạy."""
        self._on_stop_download()

    def stop_dubbing(self) -> None:
        """Dừng tác vụ lồng tiếng AI nếu đang chạy."""
        if self._is_dubbing and self._dub_worker:
            reply = QMessageBox.question(
                self, "Xác nhận dừng lồng tiếng",
                "Bạn có chắc muốn dừng tiến trình lồng tiếng AI đang chạy không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

            self.btn_stop.setEnabled(False)
            self.btn_stop.setText("⏳ Đang dừng...")
            try:
                self._dub_worker.terminate()
                self._dub_worker.wait(1000)
            except Exception:
                pass
            self._is_dubbing = False
            self._dub_worker = None
            self.dubbing_worker = None
            self._append_log("LỒNG TIẾNG", "Đã dừng tiến trình lồng tiếng.")
            self._status_bar.showMessage("Đã dừng lồng tiếng")
            if hasattr(self, "_status_notify_label"):
                self._status_notify_label.setText("⏹ Đã dừng tiến trình lồng tiếng.")
                self._status_notify_box.setVisible(True)
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(0)
            self._progress_label.setText("Tiến độ: Đã dừng")
            self._update_button_states()

    def on_btn_start_clicked(self) -> None:
        """Thực thi hành động tương ứng với trang đang hiển thị."""
        current_index = self.stacked_widget.currentIndex()

        if current_index == 0:
            # Đang ở trang Tải link lẻ
            self.start_download()
        elif current_index == 1:
            # Đang ở trang Quét kênh -> Tải các video được tick chọn trong bảng
            self.start_channel_selected_download()
        elif current_index == 2:
            # Đang ở Studio Lồng tiếng -> Bắt đầu bóc tách, dịch và lồng tiếng video
            if hasattr(self, 'studio_widget'):
                self.studio_widget.start_dubbing_process()

    def on_btn_stop_clicked(self) -> None:
        """Dừng tác vụ tương ứng với trang đang hiển thị."""
        current_index = self.stacked_widget.currentIndex()

        if current_index == 2 and hasattr(self, 'studio_widget'):
            self.studio_widget.stop_dubbing_process()
            if hasattr(self, "_status_notify_label"):
                self._status_notify_label.setText("⏹ Đã dừng tác vụ Studio.")
                self._status_notify_box.setVisible(True)
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(0)
            self._progress_label.setText("Tiến độ: Đã dừng")
        else:
            self.stop_download()
            if hasattr(self, "_status_notify_label"):
                self._status_notify_label.setText("⏹ Đã dừng tiến trình tải.")
                self._status_notify_box.setVisible(True)
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(0)
            self._progress_label.setText("Tiến độ: Đã dừng")

    def _on_start_download(self) -> None:
        """Alias tương thích ngược."""
        self.on_btn_start_clicked()

    def _start_download_with_urls(self, urls: List[str]) -> None:
        if self._is_downloading:
            QMessageBox.information(self, "Thông báo", "Đang có tác vụ tải đang chạy.")
            return

        try:
            os.makedirs(self.output_dir, exist_ok=True)
        except OSError as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể tạo thư mục:\n{self.output_dir}\n{e}")
            return

        self._failed_urls = []
        self._total_urls = len(urls)
        self._success_count = 0
        self._fail_count = 0
        self._active_count = 0
        self._progress_bar.setValue(0)
        self._btn_export_errors.setEnabled(False)
        self._update_badges()

        self._worker = DownloadWorker(
            urls=urls,
            output_dir=self.output_dir,
            cookie_file=self.cookies_path,
            max_workers=self.max_workers,
            auto_dub=self.auto_dub,
            dub_lang=self.dub_lang,
            dub_voice=self.dub_voice,
            whisper_model=self.whisper_model,
            gemini_api_key=self.gemini_api_key,
            bg_volume=self.bg_volume / 100.0,
            voice_volume=getattr(self, "voice_volume", 220) / 100.0,
            mute_original=getattr(self, "mute_original", False),
            auto_upload_tiktok=getattr(self, "auto_upload_tiktok", False),
            tiktok_cookies_path=getattr(self, "tiktok_cookies_path", ""),
            tiktok_privacy=getattr(self, "tiktok_privacy", "public"),
            tiktok_delay_minutes=getattr(self, "tiktok_delay_minutes", 45),
            tiktok_headless=getattr(self, "tiktok_headless", False),
            auto_upload_youtube=getattr(self, "auto_upload_youtube", False),
            youtube_privacy=getattr(self, "youtube_privacy", "public"),
            youtube_cookies_path=getattr(self, "youtube_cookies_path", "youtube_cookies.txt"),
            youtube_schedule_enabled=getattr(self, "youtube_schedule_enabled", False),
            youtube_schedule_date=getattr(self, "youtube_schedule_date", ""),
            youtube_schedule_time=getattr(self, "youtube_schedule_time", ""),
            youtube_default_tags=getattr(self, "youtube_default_tags", "Shorts, AI, PhimHay, ReviewPhim"),
            parent=self,
        )
        self._worker.status_updated.connect(self._on_status_updated)
        self._worker.progress_updated.connect(self._on_progress_updated)
        self._worker.item_finished.connect(self._on_item_finished)
        self._worker.log_message.connect(self._on_log_message)
        self._worker.batch_finished.connect(self._on_batch_finished)
        self._worker.finished.connect(self._on_worker_done)

        self._is_downloading = True
        self._active_count = min(self.max_workers, len(urls))
        self._update_button_states()
        self._update_badges()
        self._worker.start()

        self._append_log(
            "HỆ THỐNG",
            f"Bắt đầu tải {len(urls)} video với {self.max_workers} luồng → {self.output_dir}"
        )
        self._status_bar.showMessage(
            f"Đang tải 0/{self._total_urls} video... → {self.output_dir}"
        )

    def _on_stop_download(self) -> None:
        if not (self._worker and self._is_downloading):
            return
        reply = QMessageBox.question(
            self, "Xác nhận dừng tải",
            "Dừng quá trình tải?\nCác video đang tải dở sẽ được chờ hoàn tất.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._btn_stop.setEnabled(False)
            self._btn_stop.setText("⏳ Đang dừng...")
            self._worker.request_stop()
            self._append_log("HỆ THỐNG", "Đã gửi yêu cầu dừng tải...")

    def _on_export_errors(self) -> None:
        if not self._failed_urls:
            return
        default = os.path.join(
            self.output_dir, f"failed_urls_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu file lỗi", default, "File văn bản (*.txt);;Tất cả (*.*)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# Danh sách link lỗi - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Tổng: {len(self._failed_urls)} link\n\n")
                f.writelines(u + "\n" for u in self._failed_urls)
            self._append_log("HỆ THỐNG", f"Đã xuất {len(self._failed_urls)} link lỗi: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể ghi file:\n{e}")

    # ══════════════════════════════════════════════════════════════════
    # MODULE LỒNG TIẾNG AI
    # ══════════════════════════════════════════════════════════════════

    def _get_dub_config(
        self,
        voice_volume: Optional[float] = None,
        bg_volume: Optional[float] = None,
        mute_original: Optional[bool] = None,
    ) -> DubConfig:
        v_vol = voice_volume if voice_volume is not None else getattr(self, "voice_volume", 220) / 100.0
        b_vol = bg_volume if bg_volume is not None else getattr(self, "bg_volume", 10) / 100.0
        m_orig = mute_original if mute_original is not None else getattr(self, "mute_original", False)
        return DubConfig(
            source_lang=self.dub_lang,
            voice=self.dub_voice,
            bg_volume=b_vol,
            voice_volume=v_vol,
            mute_original=m_orig,
            whisper_model=self.whisper_model,
            gemini_api_key=self.gemini_api_key,
        )

    def _start_dubbing(
        self,
        video_path: str,
        custom_segments: Optional[List[DubSegment]] = None,
        voice_volume: Optional[float] = None,
        bg_volume: Optional[float] = None,
        mute_original: Optional[bool] = None,
    ) -> None:
        if self._is_dubbing:
            self._append_log("LỒNG TIẾNG", f"Bỏ qua {Path(video_path).name} — đang bận lồng tiếng.")
            return

        if not custom_segments and not self.gemini_api_key.strip():
            reply = QMessageBox.question(
                self,
                "Cần cấu hình Gemini API Key",
                "Module Lồng tiếng AI điện ảnh sử dụng Gemini Flash API (Miễn phí 0đ từ Google AI Studio) để dịch thoại chuẩn ngữ cảnh và đúng tên họ Hán-Việt.\n\n"
                "Bạn có muốn mở Cài đặt để nhập API Key ngay bây giờ không?\n(Chỉ mất 30 giây để lấy key miễn phí)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._on_open_dub_dialog()
                if not self.gemini_api_key.strip():
                    self._append_log("LỒNG TIẾNG", "Chưa nhập Gemini API Key. Đã hủy tiến trình lồng tiếng.")
                    return
            else:
                self._append_log("LỒNG TIẾNG", "Chưa cấu hình Gemini API Key. Đã hủy tiến trình lồng tiếng.")
                return

        config = self._get_dub_config(voice_volume, bg_volume, mute_original)
        config.custom_segments = custom_segments
        self._dub_worker = DubWorker(
            input_video=video_path, config=config, parent=self
        )
        self.dubbing_worker = self._dub_worker

        # Nạp video vào Studio và kết nối các tín hiệu thời gian thực lên bảng
        if hasattr(self, 'studio_widget'):
            self.studio_widget.load_video_to_studio(video_path)
            self.dubbing_worker.sig_segment_discovered.connect(self.studio_widget.on_segment_discovered)
            self.dubbing_worker.sig_segments_loaded.connect(self.studio_widget.on_segments_loaded)
            self.dubbing_worker.sig_sentence_translated.connect(self.studio_widget.on_sentence_translated)
            self.dubbing_worker.sig_sentence_completed.connect(self.studio_widget.on_sentence_completed)
            if hasattr(self.studio_widget, 'on_all_finished'):
                self.dubbing_worker.sig_all_finished.connect(self.studio_widget.on_all_finished)
            if hasattr(self.studio_widget, 'update_progress_status'):
                self.dubbing_worker.log_message.connect(self.studio_widget.update_progress_status)

        self._dub_worker.log_message.connect(lambda m: self._append_log("LỒNG TIẾNG", m))
        self._dub_worker.dub_progress.connect(self._on_dub_progress)
        self._dub_worker.dub_finished.connect(self._on_dub_finished)
        self._dub_worker.dub_error.connect(self._on_dub_error)
        self._dub_worker.finished.connect(self._on_dub_worker_done)
        self._is_dubbing = True
        self._append_log("LỒNG TIẾNG", f"Bắt đầu lồng tiếng: {Path(video_path).name}")
        self._status_bar.showMessage(f"Lồng tiếng AI: {Path(video_path).name}")
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_label.setText("Tiến độ: 0%  — Chuẩn bị lồng tiếng...")
        if hasattr(self, "_status_notify_label"):
            self._status_notify_label.setText(f"🎙 Bắt đầu lồng tiếng: {Path(video_path).name}")
            self._status_notify_box.setVisible(True)
        self._update_button_states()
        self._dub_worker.start()

    def _on_dub_progress(self, current: int, total: int) -> None:
        pct = int(current / total * 100) if total > 0 else 0
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(pct)
        self._progress_label.setText(f"Tiến độ: {pct}%  (Lồng tiếng câu {current}/{total})")
        self._status_bar.showMessage(f"Lồng tiếng AI: câu {current}/{total} ({pct}%)")
        if hasattr(self, "_status_notify_label"):
            self._status_notify_label.setText(f"🎙️ Đang lồng tiếng câu {current}/{total} ({pct}%)...")
            self._status_notify_box.setVisible(True)

    def _on_dub_finished(self, output_path: str) -> None:
        file_name = Path(output_path).name if output_path else ""
        self._append_log("LỒNG TIẾNG", f"✅ Hoàn tất lồng tiếng! → {file_name}")
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(100)
        self._progress_label.setText("Tiến độ: 100%  (Hoàn tất lồng tiếng)")
        if hasattr(self, "_status_notify_label"):
            self._status_notify_label.setText(f"🎉 Hoàn tất lồng tiếng video: {file_name}")
            self._status_notify_box.setVisible(True)

        # 1. Tự động nạp video đã dịch vào Studio Widget
        if hasattr(self, "studio_widget") and output_path and os.path.isfile(output_path):
            try:
                # pyrefly: ignore [unexpected-keyword]
                self.studio_widget.load_video_to_studio(output_path, preserve_table=True)
            except Exception:
                pass

        # 2. Tự động mở video đã dịch lên bằng trình phát video mặc định của hệ điều hành
        if getattr(self, "auto_open_dubbed", True) and output_path and os.path.isfile(output_path):
            try:
                if sys.platform == "win32":
                    os.startfile(os.path.abspath(output_path))
                else:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(output_path)))
                self._append_log("LỒNG TIẾNG", f"🎬 Đã mở video: {file_name}")
            except Exception as e:
                self._append_log("LỒNG TIẾNG", f"⚠ Không thể tự động mở video: {e}")

        # Hàm kích hoạt đăng YouTube Shorts tự động
        def _trigger_auto_youtube_upload():
            if getattr(self, "auto_upload_youtube", False) and output_path and os.path.isfile(output_path):
                self._append_log("YOUTUBE AUTO", f"🎬 Bắt đầu quy trình tự động đăng YouTube Shorts cho: {file_name}")
                try:
                    from core.youtube_uploader import YouTubeUploadWorker, generate_youtube_metadata
                    v_title = Path(output_path).stem
                    yt_title, yt_desc, yt_tags = generate_youtube_metadata(
                        script_content=v_title,
                        api_key=self.gemini_api_key,
                        video_title=v_title,
                    )
                    extra_tags = [t.strip() for t in getattr(self, "youtube_default_tags", "").split(",") if t.strip()]
                    for et in extra_tags:
                        if et not in yt_tags:
                            yt_tags.append(et)

                    sched_date = getattr(self, "youtube_schedule_date", None) if getattr(self, "youtube_schedule_enabled", False) else None
                    sched_time = getattr(self, "youtube_schedule_time", None) if getattr(self, "youtube_schedule_enabled", False) else None
                    sched_msg = f" | Hẹn giờ: {sched_date} lúc {sched_time}" if (sched_date and sched_time) else ""
                    self._append_log("YOUTUBE AUTO", f"Tiêu đề: {yt_title}")
                    self._append_log("YOUTUBE AUTO", f"Đang đăng lên YouTube Studio (Chế độ: {self.youtube_privacy}{sched_msg})...")

                    self._yt_standalone_worker = YouTubeUploadWorker(
                        video_path=output_path,
                        title=yt_title,
                        description=yt_desc,
                        tags=yt_tags,
                        privacy_status=getattr(self, "youtube_privacy", "public"),
                        schedule_date=sched_date,
                        schedule_time=sched_time,
                        cookies_file_path=getattr(self, "youtube_cookies_path", "youtube_cookies.txt"),
                        parent=self,
                    )
                    self._yt_standalone_worker.log_message.connect(lambda m: self._append_log("YOUTUBE AUTO", m))

                    def _on_yt_standalone_done(v, ok, msg, v_url):
                        if ok:
                            self._append_log("YOUTUBE AUTO", f"✅ Đã đăng thành công video lên YouTube Shorts: {Path(v).name} → {v_url}")
                        else:
                            self._append_log("YOUTUBE AUTO", f"⚠ Đăng YouTube Shorts thất bại: {msg}")

                    self._yt_standalone_worker.upload_finished.connect(_on_yt_standalone_done)
                    self._yt_standalone_worker.start()
                except Exception as yt_err:
                    self._append_log("YOUTUBE AUTO", f"⚠ Lỗi khởi chạy đăng YouTube: {yt_err}")

        # 3. Tự động đăng TikTok và YouTube theo chuỗi lần lượt
        has_tiktok = getattr(self, "auto_upload_tiktok", False) and output_path and os.path.isfile(output_path)
        if has_tiktok:
            self._append_log("TIKTOK AUTO", f"🎬 Bắt đầu quy trình tự động đăng TikTok cho: {file_name}")
            try:
                from core.tiktok_uploader import TikTokUploadWorker, generate_tiktok_caption
                v_title = Path(output_path).stem
                caption = generate_tiktok_caption(
                    script_content=v_title,
                    api_key=self.gemini_api_key,
                    video_title=v_title,
                )
                self._append_log("TIKTOK AUTO", f"Tiêu đề tạo bởi AI: {caption}")
                self._append_log("TIKTOK AUTO", f"Đang tự động upload lên kênh TikTok (Chế độ: {self.tiktok_privacy})...")

                self._tt_standalone_worker = TikTokUploadWorker(
                    video_path=output_path,
                    caption=caption,
                    cookies_path=self.tiktok_cookies_path,
                    privacy=self.tiktok_privacy,
                    headless=self.tiktok_headless,
                    parent=self,
                )
                self._tt_standalone_worker.log_message.connect(lambda m: self._append_log("TIKTOK AUTO", m))

                def _on_standalone_done(v, ok, msg):
                    if ok:
                        self._append_log("TIKTOK AUTO", f"✅ Đã đăng thành công video lên kênh TikTok: {Path(v).name}")
                        if hasattr(self, "studio_widget") and hasattr(self.studio_widget, "on_tiktok_posted"):
                            self.studio_widget.on_tiktok_posted()
                    else:
                        self._append_log("TIKTOK AUTO", f"⚠ Đăng TikTok thất bại: {msg}")

                    # Gọi tiếp tục YouTube Shorts sau khi TikTok hoàn thành
                    _trigger_auto_youtube_upload()

                self._tt_standalone_worker.upload_finished.connect(_on_standalone_done)
                self._tt_standalone_worker.start()
            except Exception as tt_err:
                self._append_log("TIKTOK AUTO", f"⚠ Lỗi khởi chạy đăng TikTok: {tt_err}")
                # Nếu TikTok bị lỗi thì vẫn gọi YouTube Shorts
                _trigger_auto_youtube_upload()
        else:
            # Nếu không bật TikTok, trực tiếp gọi YouTube Shorts
            _trigger_auto_youtube_upload()

        # 3. Hộp thoại thông báo hoàn tất với các nút thao tác tiện lợi
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Lồng tiếng AI hoàn tất")
        msg_box.setText(f"🎉 Đã lồng tiếng Tiếng Việt thành công!\n\n📁 File: {output_path}")
        msg_box.setIcon(QMessageBox.Icon.Information)

        btn_play = msg_box.addButton("▶  Mở video", QMessageBox.ButtonRole.ActionRole)
        btn_folder = msg_box.addButton("📁  Mở thư mục", QMessageBox.ButtonRole.ActionRole)
        btn_close = msg_box.addButton("Đóng", QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(btn_close)

        msg_box.exec()

        if msg_box.clickedButton() == btn_play:
            if output_path and os.path.isfile(output_path):
                try:
                    if sys.platform == "win32":
                        os.startfile(os.path.abspath(output_path))
                    else:
                        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(output_path)))
                except Exception:
                    pass
        elif msg_box.clickedButton() == btn_folder:
            if output_path and os.path.exists(output_path):
                try:
                    if sys.platform == "win32":
                        subprocess.Popen(f'explorer /select,"{os.path.abspath(output_path)}"')
                    else:
                        folder = os.path.dirname(os.path.abspath(output_path))
                        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
                except Exception:
                    pass

    def _on_dub_error(self, error_msg: str) -> None:
        self._append_log("LỒNG TIẾNG", f"❌ Lỗi lồng tiếng: {error_msg}")
        QMessageBox.warning(self, "Lỗi lồng tiếng AI", f"Tiến trình gặp lỗi:\n\n{error_msg}")

    def _on_dub_worker_done(self) -> None:
        self._is_dubbing = False
        self._dub_worker = None
        self.dubbing_worker = None
        self._status_bar.showMessage("Trạng thái: Sẵn sàng")
        self._update_button_states()

    # ══════════════════════════════════════════════════════════════════
    # CALLBACKS DOWNLOAD WORKER
    # ══════════════════════════════════════════════════════════════════

    def _on_status_updated(self, message: str) -> None:
        self._status_bar.showMessage(f"Trạng thái: {message}")

    def _on_progress_updated(self, percent: float, detail: str) -> None:
        completed = self._success_count + self._fail_count
        overall = (completed / self._total_urls * 100.0) if self._total_urls > 0 else 0.0
        val = min(100, max(0, int(overall)))
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(val)
        self._progress_label.setText(
            f"Tiến độ: {val}%  ({completed}/{self._total_urls} video) — {detail}"
        )
        if hasattr(self, "_status_notify_label") and detail:
            self._status_notify_label.setText(f"📥 Đang tải {completed}/{self._total_urls}: {detail}")
            self._status_notify_box.setVisible(True)
        self._update_badges()
        self._status_bar.showMessage(
            f"Đang tải {completed}/{self._total_urls}... → {self.output_dir}"
        )

    def _on_item_finished(self, url: str, success: bool, error: str) -> None:
        if success:
            self._success_count += 1
            file_path = error
            if hasattr(self, 'studio_widget') and file_path and os.path.isfile(file_path) and file_path.lower().endswith(".mp4"):
                if not getattr(self.studio_widget, 'current_video_path', None):
                    self.studio_widget.load_video_to_studio(file_path)

            # ── Trừ lượt dùng thử (nếu đang ở chế độ Trial) ──
            is_licensed, _, _, _ = self._license_manager.get_status(use_cache=True)
            if not is_licensed:
                remaining = self._license_manager.consume_trial()
                self._update_license_statusbar()
                self._append_log(
                    "HỆ THỐNG",
                    f"🎁 Lượt dùng thử còn lại: {remaining}/10"
                )
                if remaining == 0:
                    self._append_log(
                        "HỆ THỐNG",
                        "⚠ Đã hết lượt dùng thử. Vui lòng kích hoạt bản quyền PRO."
                    )

        else:
            self._fail_count += 1
            self._failed_urls.append(url)
        self._update_badges()

    def _on_log_message(self, message: str) -> None:
        platform = self._detect_platform(message)
        clean = message
        if clean.startswith("["):
            end = clean.find("]")
            if end > 0:
                tag = clean[:end + 1]
                body = clean[end + 1:].strip()
                self._append_log_raw(tag, platform, body)
                if hasattr(self, "_status_notify_label"):
                    self._status_notify_label.setText(message)
                    self._status_notify_box.setVisible(True)
                return
        self._append_log(platform, clean)
        if hasattr(self, "_status_notify_label") and any(k in clean for k in ["Đang tải", "Hoàn tất", "Lỗi", "🚀", "🎉", "TIKTOK"]):
            self._status_notify_label.setText(clean)
            self._status_notify_box.setVisible(True)

    def _on_batch_finished(self, success_count: int, fail_count: int) -> None:
        self._success_count = success_count
        self._fail_count = fail_count
        self._active_count = 0
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(100)
        self._progress_label.setText("Tiến độ: 100%")
        if hasattr(self, "_status_notify_label"):
            self._status_notify_label.setText(f"🎉 Hoàn tất danh sách! Đã tải: {success_count}, Thất bại: {fail_count}")
            self._status_notify_box.setVisible(True)
        self._update_badges()
        if self._failed_urls:
            self._btn_export_errors.setEnabled(True)
        if fail_count == 0:
            QMessageBox.information(
                self, "Hoàn tất tải",
                f"🎉 Tải thành công tất cả {success_count} video!\n\n📁 {self.output_dir}"
            )
        else:
            QMessageBox.warning(
                self, "Hoàn tất tải",
                f"Kết quả {success_count + fail_count} video:\n\n"
                f"  ✅ Thành công: {success_count}\n"
                f"  ❌ Thất bại: {fail_count}\n\n"
                "Nhấn 'Xuất file lỗi' để lưu danh sách link hỏng."
            )

    def _on_worker_done(self) -> None:
        self._is_downloading = False
        self._worker = None
        self._active_count = 0
        self._update_button_states()
        self._update_badges()
        self._status_bar.showMessage("Trạng thái: Sẵn sàng")

    # ══════════════════════════════════════════════════════════════════
    # TIỆN ÍCH NỘI BỘ
    # ══════════════════════════════════════════════════════════════════

    def _switch_page(self, index: int) -> None:
        if 0 <= index < self._stack.count():
            self._stack.setCurrentIndex(index)
            self.active_page = index
            self.update_action_buttons_state(index)
            self._save_settings()

    def _on_stack_page_changed(self, index: int) -> None:
        """Đồng bộ khi người dùng chuyển trang bằng bất kỳ phương thức nào."""
        self.active_page = index
        self.update_action_buttons_state(index)
        self._save_settings()

    def _on_studio_video_loaded(self, video_path: str) -> None:
        """Ghi nhớ video đang nạp trong Studio."""
        self.studio_last_video = video_path
        self._save_settings()

    def _restore_active_page(self) -> None:
        """Khôi phục màn hình làm việc (chế độ tải/studio) và video studio từ phiên trước."""
        target_page = getattr(self, "active_page", self.PAGE_LINKS)
        if not isinstance(target_page, int) or target_page < 0 or target_page >= self._stack.count():
            target_page = self.PAGE_LINKS

        self._switch_page(target_page)

        # Nếu mở lại ở Studio và có video đã lưu trước đó, tự động nạp lại video
        if target_page == self.PAGE_STUDIO and hasattr(self, "studio_widget"):
            saved_vid = getattr(self, "studio_last_video", "")
            if saved_vid and os.path.isfile(saved_vid) and os.path.getsize(saved_vid) > 1024:
                try:
                    self.studio_widget.load_video(saved_vid)
                    self._append_log("STUDIO", f"Đã khôi phục video: {os.path.basename(saved_vid)}")
                except Exception:
                    pass

    def _refresh_statusbar(self) -> None:
        dir_disp = self.output_dir if self.output_dir else "Chưa chọn"
        dub_disp = "BẬT" if self.auto_dub else "TẮT"
        if getattr(self, "auto_upload_tiktok", False):
            delay = getattr(self, "tiktok_delay_minutes", 45)
            tt_disp = f"BẬT (Cách {delay}p)"
        else:
            tt_disp = "TẮT"
        self._sb_label.setText(f"Thư mục: {dir_disp}  │  Lồng tiếng: {dub_disp}  │  Auto TikTok: {tt_disp}")

    def update_action_buttons_state(self, index: Optional[int] = None) -> None:
        """Tự động đổi nhãn và trạng thái nút bấm theo màn hình đang mở.
        Vô hiệu hóa nút Tải khi chưa có link hoặc chưa chọn video nào.
        """
        if index is None or not isinstance(index, int):
            index = self.stacked_widget.currentIndex()

        is_busy = bool(self._is_downloading or self._is_dubbing)
        can_start = False
        tooltip_msg = ""

        if index == 0:
            # Trang 0: Tải theo danh sách link lẻ
            self.btn_start.setText("Bắt đầu tải")
            self.btn_start.setIcon(get_svg_icon("download", "#ffffff"))
            self.btn_stop.setText("Dừng tải")
            self.btn_stop.setIcon(get_svg_icon("stop", COLORS["danger"]))
            has_urls = bool(hasattr(self, "_url_input") and self._url_input.toPlainText().strip())
            can_start = (not is_busy) and has_urls
            if not has_urls:
                tooltip_msg = "Vui lòng nhập ít nhất một liên kết video để tải"
        elif index == 1:
            # Trang 1: Quét Kênh / Hồ sơ
            self.btn_start.setText("Tải video đã chọn")
            self.btn_start.setIcon(get_svg_icon("download", "#ffffff"))
            self.btn_stop.setText("Dừng tải")
            self.btn_stop.setIcon(get_svg_icon("stop", COLORS["danger"]))
            selected_count = 0
            if hasattr(self, "_result_table"):
                for row in range(self._result_table.rowCount()):
                    chk = self._result_table.cellWidget(row, 0)
                    if isinstance(chk, QCheckBox) and chk.isChecked():
                        selected_count += 1
            can_start = (not is_busy) and (selected_count > 0)
            if selected_count == 0:
                tooltip_msg = "Vui lòng chọn ít nhất một video trong bảng để tải"
            else:
                self.btn_start.setText(f"Tải video đã chọn ({selected_count})")
        elif index == 2:
            # Trang 2: Studio Lồng tiếng & Soát kịch bản
            self.btn_start.setText("Bắt đầu lồng tiếng")
            self.btn_start.setIcon(get_svg_icon("mic", "#ffffff"))
            self.btn_stop.setText("Dừng lồng tiếng")
            self.btn_stop.setIcon(get_svg_icon("stop", COLORS["danger"]))
            has_video = bool(hasattr(self, "dubbing_studio") and getattr(self.dubbing_studio, "current_video_path", None))
            can_start = (not is_busy) and has_video
            if not has_video:
                tooltip_msg = "Vui lòng tải hoặc chọn video trong Studio để bắt đầu lồng tiếng"

        if is_busy and self.btn_stop.text().startswith("Đang dừng"):
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(False)
        else:
            self.btn_start.setEnabled(can_start)
            self.btn_stop.setEnabled(is_busy)
            self.btn_start.setToolTip(tooltip_msg if not can_start else "")

    def _update_button_states(self) -> None:
        self.update_action_buttons_state(self.stacked_widget.currentIndex())

    def _update_badges(self) -> None:
        self._badge_total.setText(f"  Tổng: {self._total_urls} video  ")
        self._badge_success.setText(f"  Đã tải: {self._success_count}  ")
        self._badge_active.setText(f"  Đang tải: {self._active_count}  ")
        self._badge_error.setText(f"  Lỗi: {self._fail_count}  ")

    def _append_log(self, tag: str, message: str) -> None:
        msg = str(message).strip()
        # Nếu message đã bị kèm timestamp ở đầu định dạng [HH:MM:SS], bóc tách ra để tránh bị hiển thị 2 lần
        if len(msg) >= 10 and msg.startswith("[") and msg[9] == "]":
            parts = msg[1:9].split(":")
            if len(parts) == 3 and all(p.isdigit() for p in parts):
                ts = msg[:10]
                msg = msg[10:].strip()
                self._append_log_raw(ts, tag, msg)
                return
        ts = datetime.now().strftime("[%H:%M:%S]")
        self._append_log_raw(ts, tag, msg)

    def _append_log_raw(self, timestamp: str, tag: str, message: str) -> None:
        tag_color = PLATFORM_COLORS.get(tag, COLORS["text_muted"])
        html = (
            f'<p style="margin:2px 0; white-space:pre-wrap; word-break:break-word; line-height:1.4;">'
            f'<span style="color:{COLORS["text_muted"]}; font-size:11px;">{timestamp}</span>'
            f'&nbsp;&nbsp;'
            f'<span style="color:{tag_color}; font-weight:700; font-size:11px;">[{tag}]</span>'
            f'&nbsp;&nbsp;'
            f'<span style="color:{COLORS["text_secondary"]}; font-size:11px;">{message}</span>'
            f'</p>'
        )
        self._log_view.append(html)
        cur = self._log_view.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        self._log_view.setTextCursor(cur)

    def _detect_platform(self, message: str) -> str:
        m = message.lower()
        if "tiktok" in m:
            return "TIKTOK"
        if "douyin" in m or "抖音" in m:
            return "DOUYIN"
        if "facebook" in m or "fb.watch" in m:
            return "FACEBOOK"
        if "youtube" in m or "youtu.be" in m:
            return "YOUTUBE"
        if "lồng tiếng" in m or "whisper" in m or "gtts" in m:
            return "LỒNG TIẾNG"
        return "HỆ THỐNG"

    # ── Widget factories ──

    def _make_card(self) -> QWidget:
        w = QWidget()
        w.setObjectName("card")
        w.setStyleSheet(f"""
            QWidget#card {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
        """)
        return w

    def _make_badge(self, text: str, bg: str, border: str) -> QLabel:
        b = QLabel(f"  {text}  ")
        b.setAlignment(Qt.AlignmentFlag.AlignCenter)
        b.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 6px;
                color: {COLORS['text_primary']};
                font-size: 12px;
                font-weight: 600;
                padding: 5px 10px;
            }}
        """)
        return b

    def _page_titlebar(
        self,
        title: str,
        hint: str,
        icon_name: str | None = None,
        extra_btn: QWidget | None = None,
    ) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        if icon_name:
            ic_lbl = QLabel()
            ic_lbl.setPixmap(get_svg_pixmap(icon_name, size=18, color=COLORS["brand"]))
            row.addWidget(ic_lbl)
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"font-size:14px; font-weight:700; color:{COLORS['text_primary']};"
        )
        row.addWidget(lbl)
        row.addStretch()
        if extra_btn:
            row.addWidget(extra_btn)
        h = QLabel(hint)
        h.setStyleSheet(f"color:{COLORS['text_muted']}; font-size:11px;")
        row.addWidget(h)
        return row

    def _s_small_btn(self) -> str:
        c = COLORS
        return f"""
            QPushButton {{
                background-color: {c['btn_secondary_bg']};
                color: {c['text_secondary']};
                border: 1px solid {c['btn_outline_border']};
                border-radius: 5px;
                font-size: 12px;
                padding: 2px 12px;
            }}
            QPushButton:hover {{
                background-color: {c['btn_secondary_hover']};
                color: {c['text_primary']};
            }}
        """

    # ══════════════════════════════════════════════════════════════════
    # THƯ VIỆN & XEM VIDEO ĐÃ TẢI XUỐNG (GALLERY PLAYER)
    # ══════════════════════════════════════════════════════════════════

    def open_downloaded_videos_gallery(self, select_video_path: Optional[str] = None) -> None:
        """Mở màn hình phát video đã tải xuống (YouTube-style player & 2 tabs)."""
        if not hasattr(self, "_gallery_dialog") or self._gallery_dialog is None:
            self._gallery_dialog = VideoGalleryDialog(
                downloads_dir=self.output_dir,
                initial_video_path=select_video_path,
                parent=self,
            )
        else:
            self._gallery_dialog.downloads_dir = self.output_dir
            self._gallery_dialog.refresh_videos(select_path=select_video_path)

        self._gallery_dialog.show()
        self._gallery_dialog.raise_()
        self._gallery_dialog.activateWindow()

    # ══════════════════════════════════════════════════════════════════
    # CLOSE EVENT
    # ══════════════════════════════════════════════════════════════════

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._is_downloading:
            reply = QMessageBox.question(
                self, "Xác nhận thoát",
                "Đang có video đang tải. Bạn có chắc muốn thoát?\n"
                "Các video đang tải dở sẽ bị hủy.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            if self._worker:
                self._worker.request_stop()
                self._worker.wait(3000)

        if self._is_scanning and self._scan_worker:
            self._scan_worker.terminate()
            self._scan_worker.wait(1000)

        if self._is_dubbing and self._dub_worker:
            self._dub_worker.terminate()
            self._dub_worker.wait(1000)

        self._save_settings()
        event.accept()
