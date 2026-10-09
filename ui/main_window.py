"""
ui/main_window.py — OmniGrab v4.0 Desktop
Giao diện hiện đại chuẩn VS Code với Menu Bar, QStackedWidget & DubbingDialog popup.

Layout:
  Cột trái  : QStackedWidget (Trang 0: Dán link | Trang 1: Quét kênh)
  Cột phải  : Tiến trình + Realtime Log
  Bottom     : QStatusBar với tóm tắt + nút BẮT ĐẦU TẢI

Ngôn ngữ giao diện: 100% Tiếng Việt.
"""

from __future__ import annotations

import csv
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# pyrefly: ignore [missing-import]
from PyQt6.QtCore import Qt, QTimer
# pyrefly: ignore [missing-import]
from PyQt6.QtGui import QAction, QFont, QTextCursor, QColor, QKeySequence
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
    QMainWindow,
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
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)

from core.dubber import DubConfig, check_dub_dependencies
from core.dub_worker import DubWorker
from core.parser import extract_urls, read_urls_from_file
from core.worker import DownloadWorker, ScanChannelWorker
from ui.cookie_dialog import CookieFailedDialog, CookieGuideDialog, CookiePromptDialog
from ui.styles import COLORS, PLATFORM_COLORS


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
        whisper_model: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cài đặt & Lồng tiếng AI Tiếng Việt")
        self.setMinimumWidth(560)
        self.setModal(True)

        # Lưu giá trị trả về
        self.result_auto_dub = auto_dub
        self.result_src_lang = src_lang
        self.result_voice = voice
        self.result_bg_volume = bg_volume
        self.result_whisper_model = whisper_model

        self._build_ui(auto_dub, src_lang, voice, bg_volume, whisper_model)

    # ─────────────── Build UI ───────────────

    def _build_ui(
        self,
        auto_dub: bool,
        src_lang: str,
        voice: str,
        bg_volume: int,
        whisper_model: str,
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
            QComboBox, QSpinBox {{
                background-color: {c['bg_input']};
                color: {c['text_primary']};
                border: 1px solid {c['bg_input_border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QComboBox:focus, QSpinBox:focus {{
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
        lbl_header = QLabel("🎙 Cài đặt Module Lồng tiếng AI Tiếng Việt")
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

        # ── Grid cài đặt ──
        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(12)

        # Ngôn ngữ gốc
        grid.addWidget(self._lbl("Ngôn ngữ video gốc:"), 0, 0)
        self._combo_lang = QComboBox()
        self._combo_lang.addItem("🇨🇳  Tiếng Trung (Douyin)", "zh-CN")
        self._combo_lang.addItem("🇬🇧  Tiếng Anh (TikTok / Facebook)", "en")
        self._combo_lang.addItem("🇯🇵  Tiếng Nhật", "ja")
        self._combo_lang.addItem("🇰🇷  Tiếng Hàn", "ko")
        # Chọn ngôn ngữ hiện tại
        idx = self._combo_lang.findData(src_lang)
        if idx < 0 and src_lang in ("zh", "zh-TW", "zh-CN"):
            idx = self._combo_lang.findData("zh-CN")
        if idx >= 0:
            self._combo_lang.setCurrentIndex(idx)
        grid.addWidget(self._combo_lang, 0, 1)

        # Giọng đọc
        grid.addWidget(self._lbl("Giọng đọc AI (Edge-TTS):"), 1, 0)
        self._combo_voice = QComboBox()
        self._combo_voice.addItem("👩  Nữ — Hoài My (Truyền cảm)", "vi-VN-HoaiMyNeural")
        self._combo_voice.addItem("👨  Nam — Nam Minh (Tin tức)", "vi-VN-NamMinhNeural")
        idx_v = self._combo_voice.findData(voice)
        if idx_v >= 0:
            self._combo_voice.setCurrentIndex(idx_v)
        grid.addWidget(self._combo_voice, 1, 1)

        # Whisper model
        grid.addWidget(self._lbl("Độ chính xác nhận diện:"), 2, 0)
        self._combo_model = QComboBox()
        self._combo_model.addItem("⚡  tiny — Nhanh nhất", "tiny")
        self._combo_model.addItem("🎯  base — Cân bằng (khuyến nghị)", "base")
        self._combo_model.addItem("🔬  small — Chính xác nhất (chậm hơn)", "small")
        idx_m = self._combo_model.findData(whisper_model)
        if idx_m >= 0:
            self._combo_model.setCurrentIndex(idx_m)
        grid.addWidget(self._combo_model, 2, 1)

        # Âm lượng nhạc nền
        grid.addWidget(self._lbl("Âm lượng nhạc nền (Ducking):"), 3, 0)
        vol_row = QHBoxLayout()
        self._slider_vol = QSlider(Qt.Orientation.Horizontal)
        self._slider_vol.setRange(0, 30)
        self._slider_vol.setValue(bg_volume)
        self._slider_vol.setToolTip("0% = tắt nhạc nền | 12% = mặc định | 30% = nền rõ")
        self._lbl_vol = QLabel(f"{bg_volume}%")
        self._lbl_vol.setStyleSheet(
            f"color:{c['accent_blue']}; font-weight:700; min-width:40px;"
        )
        self._slider_vol.valueChanged.connect(
            lambda v: self._lbl_vol.setText(f"{v}%")
        )
        vol_row.addWidget(self._slider_vol)
        vol_row.addWidget(self._lbl_vol)
        vol_w = QWidget()
        vol_w.setLayout(vol_row)
        grid.addWidget(vol_w, 3, 1)

        grid.setColumnStretch(1, 1)
        root.addLayout(grid)

        # ── Trạng thái thư viện ──
        sep2 = self._make_sep()
        root.addWidget(sep2)
        self._lbl_dep_status = QLabel("🔄 Đang kiểm tra thư viện...")
        self._lbl_dep_status.setStyleSheet(
            f"color:{c['text_muted']}; font-size:12px;"
        )
        root.addWidget(self._lbl_dep_status)
        QTimer.singleShot(100, self._check_deps)

        # ── Nút Lưu & Áp dụng ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("Hủy bỏ")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_save = QPushButton("💾  Lưu & Áp dụng")
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['btn_green_bg']};
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {c['btn_green_hover']};
            }}
        """)
        btn_save.clicked.connect(self._save_and_accept)
        btn_row.addWidget(btn_save)
        root.addLayout(btn_row)

    # ─────────────── Helpers ───────────────

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
                self._lbl_dep_status.setText("✅ Tất cả thư viện sẵn sàng — có thể lồng tiếng ngay")
                self._lbl_dep_status.setStyleSheet(
                    f"color:{c['accent_green']}; font-size:12px; font-weight:600;"
                )
            else:
                self._lbl_dep_status.setText(
                    f"⚠ Chưa cài: {', '.join(missing)}. "
                    "Chạy: pip install faster-whisper edge-tts deep-translator"
                )
                self._lbl_dep_status.setStyleSheet(
                    f"color:{c['accent_orange']}; font-size:12px; font-weight:600;"
                )
        except Exception:
            self._lbl_dep_status.setText("⚠ Không kiểm tra được thư viện")

    def _save_and_accept(self) -> None:
        self.result_auto_dub = self._chk_auto.isChecked()
        self.result_src_lang = self._combo_lang.currentData() or "zh-CN"
        self.result_voice = self._combo_voice.currentData() or "vi-VN-HoaiMyNeural"
        self.result_bg_volume = self._slider_vol.value()
        self.result_whisper_model = self._combo_model.currentData() or "base"
        self.accept()


# ══════════════════════════════════════════════════════════════════════
# CỬA SỔ CHÍNH
# ══════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    """Cửa sổ giao diện chính OmniGrab v4.0 — layout chuẩn VS Code."""

    # ────────── Trang QStackedWidget ──────────
    PAGE_LINKS = 0
    PAGE_CHANNEL = 1

    def __init__(self) -> None:
        super().__init__()

        # ── Trạng thái hệ thống ──
        self._worker: Optional[DownloadWorker] = None
        self._scan_worker: Optional[ScanChannelWorker] = None
        self._dub_worker: Optional[DubWorker] = None

        self._is_downloading = False
        self._is_scanning = False
        self._is_dubbing = False

        self._total_urls = 0
        self._success_count = 0
        self._fail_count = 0
        self._active_count = 0
        self._failed_urls: List[str] = []
        self._scanned_videos: List[Dict[str, Any]] = []

        # ── Cấu hình người dùng (đồng bộ với DubbingDialog) ──
        self.output_dir: str = str(Path.home() / "Videos" / "OmniGrab_Downloads")
        self.cookies_path: str = ""
        self.auto_dub: bool = False
        self.dub_lang: str = "zh-CN"
        self.dub_voice: str = "vi-VN-HoaiMyNeural"
        self.bg_volume: int = 12              # % (0-30)
        self.whisper_model: str = "base"
        self.max_workers: int = 3

        # Tạo thư mục mặc định
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
        self._update_cookie_ui()
        self._append_log(
            "HỆ THỐNG",
            "OmniGrab v4.0 sẵn sàng. Dán link vào ô nhập hoặc vào Chế độ tải → Quét kênh.",
        )

    # ══════════════════════════════════════════════════════════════════
    # THIẾT LẬP CỬA SỔ
    # ══════════════════════════════════════════════════════════════════

    def _setup_window(self) -> None:
        self.setWindowTitle(
            "OmniGrab v4.0 — Tải & Lồng tiếng AI Tiếng Việt"
            " | TikTok · Douyin · Facebook · YouTube"
        )
        self.setMinimumSize(1100, 660)
        self.resize(1280, 760)

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

        act_output = QAction("📁  Thư mục lưu video...", self)
        act_output.triggered.connect(self._on_choose_output_dir)
        menu_file.addAction(act_output)

        act_cookie = QAction("🍪  Nạp file Cookie (.txt)...", self)
        act_cookie.triggered.connect(self._on_choose_cookie)
        menu_file.addAction(act_cookie)

        act_import = QAction("📋  Nhập danh sách link từ file...", self)
        act_import.triggered.connect(self._on_import_file)
        menu_file.addAction(act_import)

        menu_file.addSeparator()

        act_quit = QAction("🚪  Thoát", self)
        act_quit.setShortcut(QKeySequence("Alt+F4"))
        act_quit.triggered.connect(self.close)
        menu_file.addAction(act_quit)

        # ── 2. Chế độ tải ──
        menu_mode = bar.addMenu("Chế độ tải")

        act_links = QAction("🔗  Tải theo danh sách liên kết", self)
        act_links.setShortcut(QKeySequence("Ctrl+1"))
        act_links.triggered.connect(lambda: self._switch_page(self.PAGE_LINKS))
        menu_mode.addAction(act_links)

        act_channel = QAction("📡  Quét & Tải theo Kênh / Hồ sơ", self)
        act_channel.setShortcut(QKeySequence("Ctrl+2"))
        act_channel.triggered.connect(lambda: self._switch_page(self.PAGE_CHANNEL))
        menu_mode.addAction(act_channel)

        menu_mode.addSeparator()

        act_threads = QAction("⚙  Cài đặt số luồng tải đồng thời...", self)
        act_threads.triggered.connect(self._on_set_threads)
        menu_mode.addAction(act_threads)

        # ── 3. Công cụ ──
        menu_tools = bar.addMenu("Công cụ")

        act_dub_settings = QAction("🎙  Cài đặt Lồng tiếng AI...", self)
        act_dub_settings.setShortcut(QKeySequence("Ctrl+L"))
        act_dub_settings.triggered.connect(self._on_open_dub_dialog)
        menu_tools.addAction(act_dub_settings)

        act_dub_file = QAction("🎬  Lồng tiếng file MP4 có sẵn trên máy...", self)
        act_dub_file.triggered.connect(self._on_dub_manual)
        menu_tools.addAction(act_dub_file)

        menu_tools.addSeparator()

        act_update = QAction("🔄  Cập nhật lõi yt-dlp & FFmpeg", self)
        act_update.triggered.connect(self._on_update_tools)
        menu_tools.addAction(act_update)

        # ── 4. Trợ giúp ──
        menu_help = bar.addMenu("Trợ giúp")

        act_about = QAction("ℹ  Thông tin phần mềm (About)", self)
        act_about.triggered.connect(self._on_about)
        menu_help.addAction(act_about)

        act_guide = QAction("📖  Hướng dẫn sử dụng", self)
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
        self._stack.addWidget(self._build_page_links())    # 0
        self._stack.addWidget(self._build_page_channel())  # 1
        self._stack.setCurrentIndex(self.PAGE_LINKS)

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
        bar = self._page_titlebar("🔗  Tải theo danh sách liên kết", "Ctrl+1 để chuyển trang")
        layout.addLayout(bar)

        # ── Card ô nhập URL ──
        card = self._make_card()
        card_l = QVBoxLayout(card)
        card_l.setContentsMargins(14, 10, 14, 10)
        card_l.setSpacing(8)

        # Header với nút hỗ trợ
        hdr = QHBoxLayout()
        lbl = QLabel("Dán danh sách liên kết vào đây (mỗi dòng 1 link):")
        lbl.setStyleSheet(f"color:{COLORS['text_secondary']}; font-size:12px;")
        hdr.addWidget(lbl)
        hdr.addStretch()

        btn_paste = QPushButton("📋 Dán clipboard")
        btn_paste.setFixedHeight(27)
        btn_paste.setStyleSheet(self._s_small_btn())
        btn_paste.clicked.connect(self._on_paste_clipboard)
        hdr.addWidget(btn_paste)

        btn_clear = QPushButton("🗑 Xóa hết")
        btn_clear.setFixedHeight(27)
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
        bar = self._page_titlebar("📡  Quét & Tải theo Kênh / Hồ sơ", "Ctrl+2 để chuyển trang")
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
            "https://www.tiktok.com/@username   |   https://www.douyin.com/user/xxx   |   https://www.facebook.com/pagename"
        )
        url_row.addWidget(self._channel_url_input, 1)

        lbl_max = QLabel("Tối đa:")
        lbl_max.setStyleSheet(f"color:{COLORS['text_secondary']}; font-size:12px;")
        url_row.addWidget(lbl_max)

        self._max_videos_spinbox = QSpinBox()
        self._max_videos_spinbox.setRange(1, 1000)
        self._max_videos_spinbox.setValue(50)
        self._max_videos_spinbox.setFixedWidth(80)
        url_row.addWidget(self._max_videos_spinbox)

        lbl_vid = QLabel("video")
        lbl_vid.setStyleSheet(f"color:{COLORS['text_secondary']}; font-size:12px;")
        url_row.addWidget(lbl_vid)

        self._btn_scan = QPushButton("🔍  Quét kênh")
        self._btn_scan.setFixedHeight(34)
        self._btn_scan.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent_cyan']};
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 700;
                padding: 0 18px;
            }}
            QPushButton:hover {{ background-color: #22d3ee; }}
            QPushButton:disabled {{
                background-color: {COLORS['border']};
                color: {COLORS['text_placeholder']};
            }}
        """)
        url_row.addWidget(self._btn_scan)
        tl.addLayout(url_row)

        # ── Banner trạng thái Cookie trực quan ──
        tl.addWidget(self._build_cookie_banner())

        # Bộ lọc Viral
        tl.addWidget(self._build_filter_section())

        # Status
        self._scan_status_label = QLabel("Nhập URL kênh rồi nhấn 🔍 Quét kênh để bắt đầu.")
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
            "✓", "Tiêu đề video", "Lượt xem", "Lượt thích", "Thời lượng", "Ngày đăng", "URL"
        ])
        h = self._result_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self._result_table.setColumnWidth(0, 34)
        self._result_table.setColumnWidth(2, 85)
        self._result_table.setColumnWidth(3, 85)
        self._result_table.setColumnWidth(4, 78)
        self._result_table.setColumnWidth(5, 92)
        self._result_table.verticalHeader().setVisible(False)
        self._result_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._result_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._result_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._result_table.setAlternatingRowColors(True)
        rl.addWidget(self._result_table, 1)

        # Nút chọn + xuất
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(8)
        self._btn_select_all = QPushButton("☑ Chọn tất cả")
        self._btn_select_all.setFixedHeight(30)
        self._btn_select_all.setStyleSheet(self._s_small_btn())
        btn_bar.addWidget(self._btn_select_all)

        self._btn_deselect_all = QPushButton("☐ Bỏ chọn tất cả")
        self._btn_deselect_all.setFixedHeight(30)
        self._btn_deselect_all.setStyleSheet(self._s_small_btn())
        btn_bar.addWidget(self._btn_deselect_all)

        self._btn_export_csv = QPushButton("📊 Xuất CSV")
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

        hint = QLabel("▶ Nhấn BẮT ĐẦU TẢI ở dưới để tải")
        hint.setStyleSheet(
            f"color:{COLORS['accent_cyan']}; font-size:11px; font-weight:600;"
        )
        btn_bar.addWidget(hint)
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

        self._cookie_status_icon = QLabel("🍪")
        self._cookie_status_icon.setStyleSheet("font-size: 14px;")
        layout.addWidget(self._cookie_status_icon)

        self._cookie_status_text = QLabel("Cookie: Chưa nạp (TikTok / Douyin yêu cầu Cookie để quét toàn bộ kênh)")
        self._cookie_status_text.setStyleSheet(f"color: {c['accent_orange']}; font-size: 12px; font-weight: 500;")
        layout.addWidget(self._cookie_status_text, 1)

        self._btn_banner_load_cookie = QPushButton("🍪 Nạp Cookie (.txt)")
        self._btn_banner_load_cookie.setFixedHeight(27)
        self._btn_banner_load_cookie.setStyleSheet(self._s_small_btn())
        self._btn_banner_load_cookie.clicked.connect(self._on_choose_cookie)
        layout.addWidget(self._btn_banner_load_cookie)

        self._btn_banner_guide_cookie = QPushButton("❓ Hướng dẫn lấy Cookie")
        self._btn_banner_guide_cookie.setFixedHeight(27)
        self._btn_banner_guide_cookie.setStyleSheet(self._s_small_btn())
        self._btn_banner_guide_cookie.clicked.connect(self._show_cookie_guide)
        layout.addWidget(self._btn_banner_guide_cookie)

        self._btn_banner_clear_cookie = QPushButton("✕ Bỏ")
        self._btn_banner_clear_cookie.setFixedHeight(27)
        self._btn_banner_clear_cookie.setStyleSheet(self._s_small_btn())
        self._btn_banner_clear_cookie.clicked.connect(self._on_clear_cookie)
        self._btn_banner_clear_cookie.setVisible(False)
        layout.addWidget(self._btn_banner_clear_cookie)

        self._cookie_banner.setStyleSheet(f"""
            QFrame#cookie_banner {{
                background-color: rgba(245, 158, 11, 0.12);
                border: 1px solid rgba(245, 158, 11, 0.35);
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
            self._cookie_status_icon.setText("✅")
            self._cookie_status_text.setText(
                f"Cookie: Đã nạp ({filename}) — Sẵn sàng quét kênh TikTok / Douyin / Facebook"
            )
            self._cookie_status_text.setStyleSheet(
                f"color: {c['accent_green']}; font-size: 12px; font-weight: 600;"
            )
            self._cookie_banner.setStyleSheet(f"""
                QFrame#cookie_banner {{
                    background-color: rgba(34, 197, 94, 0.12);
                    border: 1px solid rgba(34, 197, 94, 0.35);
                    border-radius: 6px;
                }}
            """)
            self._btn_banner_load_cookie.setText("🔄 Đổi Cookie")
            self._btn_banner_clear_cookie.setVisible(True)
        else:
            self._cookie_status_icon.setText("🍪")
            self._cookie_status_text.setText(
                "Cookie: Chưa nạp (TikTok & Douyin yêu cầu Cookie để quét toàn bộ kênh)"
            )
            self._cookie_status_text.setStyleSheet(
                f"color: {c['accent_orange']}; font-size: 12px; font-weight: 500;"
            )
            self._cookie_banner.setStyleSheet(f"""
                QFrame#cookie_banner {{
                    background-color: rgba(245, 158, 11, 0.12);
                    border: 1px solid rgba(245, 158, 11, 0.35);
                    border-radius: 6px;
                }}
            """)
            self._btn_banner_load_cookie.setText("🍪 Nạp Cookie (.txt)")
            self._btn_banner_clear_cookie.setVisible(False)

    def _build_filter_section(self) -> QGroupBox:
        c = COLORS
        grp = QGroupBox("🏆  Bộ lọc video Viral (Tùy chọn)")
        grp.setStyleSheet(f"""
            QGroupBox {{
                color: {c['accent_orange']};
                font-size: 12px;
                font-weight: 700;
                border: 1px solid {c['border']};
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 14px;
                background-color: {c['bg_card']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                left: 12px;
            }}
        """)
        layout = QGridLayout(grp)
        layout.setContentsMargins(12, 14, 12, 10)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(8)

        def flbl(t: str) -> QLabel:
            lbl = QLabel(t)
            lbl.setStyleSheet(f"color:{c['text_secondary']}; font-size:12px;")
            return lbl

        layout.addWidget(flbl("👁 Lượt xem tối thiểu:"), 0, 0)
        self._filter_min_views = QSpinBox()
        self._filter_min_views.setRange(0, 10_000_000)
        self._filter_min_views.setSingleStep(1000)
        self._filter_min_views.setSpecialValueText("Không lọc")
        self._filter_min_views.setMinimumWidth(110)
        layout.addWidget(self._filter_min_views, 0, 1)

        layout.addWidget(flbl("♥ Lượt thích tối thiểu:"), 0, 2)
        self._filter_min_likes = QSpinBox()
        self._filter_min_likes.setRange(0, 1_000_000)
        self._filter_min_likes.setSingleStep(100)
        self._filter_min_likes.setSpecialValueText("Không lọc")
        self._filter_min_likes.setMinimumWidth(110)
        layout.addWidget(self._filter_min_likes, 0, 3)

        layout.addWidget(flbl("⏱ Thời lượng:"), 1, 0)
        self._filter_duration = QComboBox()
        self._filter_duration.addItems(["Tất cả", "Dưới 60 giây (Shorts/Reels)", "Trên 60 giây"])
        self._filter_duration.setMinimumWidth(150)
        layout.addWidget(self._filter_duration, 1, 1)

        layout.addWidget(flbl("📅 Ngày đăng:"), 1, 2)
        self._filter_date = QComboBox()
        self._filter_date.addItems(["Tất cả", "3 ngày qua", "7 ngày qua", "30 ngày qua"])
        self._filter_date.setMinimumWidth(150)
        layout.addWidget(self._filter_date, 1, 3)

        layout.setColumnStretch(4, 1)
        return grp

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

        # Log header
        log_hdr = QHBoxLayout()
        lbl_log = QLabel("NHẬT KÝ HOẠT ĐỘNG (REALTIME)")
        lbl_log.setStyleSheet(
            f"color:{c['text_muted']}; font-size:11px; font-weight:600; letter-spacing:0.5px;"
        )
        log_hdr.addWidget(lbl_log)
        log_hdr.addStretch()

        self._btn_export_errors = QPushButton("📤 Xuất file lỗi (.txt)")
        self._btn_export_errors.setFixedHeight(26)
        self._btn_export_errors.setStyleSheet(self._s_small_btn())
        self._btn_export_errors.setEnabled(False)
        log_hdr.addWidget(self._btn_export_errors)
        cl.addLayout(log_hdr)

        # Log view
        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMinimumHeight(120)
        self._log_view.setStyleSheet(f"""
            QTextEdit {{
                background-color: {c['bg_input']};
                color: {c['text_primary']};
                border: 1px solid {c['bg_input_border']};
                border-radius: 6px;
                padding: 8px;
                font-family: "Cascadia Code", "Consolas", monospace;
                font-size: 11px;
                line-height: 1.6;
            }}
        """)
        cl.addWidget(self._log_view, 1)

        # ── Hàng nút điều khiển ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        self._btn_stop = QPushButton("⏹  Dừng tải")
        self._btn_stop.setFixedHeight(44)
        self._btn_stop.setEnabled(False)
        self._btn_stop.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._btn_stop.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {c['text_secondary']};
                border: 1.5px solid {c['btn_outline_border']};
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
                padding: 0 22px;
            }}
            QPushButton:hover {{
                background-color: {c['btn_outline_hover']};
                border-color: {c['text_secondary']};
                color: {c['text_primary']};
            }}
            QPushButton:disabled {{
                color: {c['text_placeholder']};
                border-color: {c['border']};
            }}
        """)
        btn_row.addWidget(self._btn_stop)

        self._btn_start = QPushButton("▶  BẮt ĐẦU TẢI")
        self._btn_start.setFixedHeight(44)
        self._btn_start.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._btn_start.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['btn_green_bg']};
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 700;
                padding: 10px 28px;
                letter-spacing: 0.5px;
            }}
            QPushButton:hover {{
                background-color: {c['btn_green_hover']};
            }}
            QPushButton:pressed {{
                background-color: #15803d;
            }}
            QPushButton:disabled {{
                background-color: {c['border']};
                color: {c['text_placeholder']};
            }}
        """)
        btn_row.addWidget(self._btn_start)
        cl.addLayout(btn_row)

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
                padding: 2px 8px;
            }}
        """)
        # Chỉ hiển thị text tóm tắt — nút đặt trong right panel
        self._sb_label = QLabel("📁 Lưu tại: —  |  🎙 Lồng tiếng: TắT")
        self._sb_label.setStyleSheet(f"color:{c['text_muted']}; padding: 0 4px;")
        sb.addWidget(self._sb_label)
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

        # Main buttons
        self._btn_start.clicked.connect(self._on_start_download)
        self._btn_stop.clicked.connect(self._on_stop_download)
        self._btn_export_errors.clicked.connect(self._on_export_errors)

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
            self._refresh_statusbar()
            self._append_log("HỆ THỐNG", f"Thư mục lưu đã đổi sang: {d}")

    def _on_choose_cookie(self) -> bool:
        f, _ = QFileDialog.getOpenFileName(
            self, "Chọn file Cookie (.txt)", "",
            "Cookie file (*.txt);;Tất cả file (*.*)"
        )
        if f:
            self.cookies_path = f
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
        self._update_cookie_ui()
        self._append_log("HỆ THỐNG", "Đã gỡ bỏ file cookie.")

    def _show_cookie_guide(self) -> None:
        dlg = CookieGuideDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_cookie_file:
            self.cookies_path = dlg.selected_cookie_file
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
            whisper_model=self.whisper_model,
            parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.auto_dub = dlg.result_auto_dub
            self.dub_lang = dlg.result_src_lang
            self.dub_voice = dlg.result_voice
            self.bg_volume = dlg.result_bg_volume
            self.whisper_model = dlg.result_whisper_model
            self._refresh_statusbar()
            status = "BẬT" if self.auto_dub else "TẮT"
            self._append_log("LỒNG TIẾNG", f"Cài đặt đã lưu — Tự động lồng tiếng: {status}")

    def _on_dub_manual(self) -> None:
        if self._is_dubbing:
            QMessageBox.warning(self, "Đang xử lý", "Hiện đang có tiến trình lồng tiếng đang chạy!")
            return
        f, _ = QFileDialog.getOpenFileName(
            self, "Chọn video MP4 để lồng tiếng", "",
            "Video MP4 (*.mp4);;Tất cả file (*.*)"
        )
        if f:
            self._start_dubbing(f)

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
            self._append_log("HỆ THỐNG", f"Số luồng tải đồng thời đã đổi thành: {val}")

    # ══════════════════════════════════════════════════════════════════
    # XỬ LÝ SỰ KIỆN — MENU TRỢ GIÚP
    # ══════════════════════════════════════════════════════════════════

    def _on_about(self) -> None:
        QMessageBox.information(
            self, "Thông tin phần mềm",
            "OmniGrab Pro v4.0\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Tải video hàng loạt từ TikTok, Douyin,\n"
            "Facebook, YouTube — không watermark.\n\n"
            "Tính năng mới v4.0:\n"
            "  • Lồng tiếng AI Tiếng Việt (Edge-TTS)\n"
            "  • Quét kênh + Bộ lọc Viral\n"
            "  • Xuất CSV danh sách video\n\n"
            "Bản quyền Creator Việt Nam 2024\n"
            "Động cơ: yt-dlp · FFmpeg · faster-whisper",
        )

    def _on_guide(self) -> None:
        QMessageBox.information(
            self, "Hướng dẫn sử dụng",
            "HƯỚNG DẪN NHANH OMNIGRAB v4.0\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "① Chọn thư mục lưu qua menu Tệp → Thư mục lưu video.\n\n"
            "② TẢI THEO LINK:\n"
            "   • Dán link TikTok / Douyin / Facebook / YouTube vào ô nhập.\n"
            "   • Nhấn BẮT ĐẦU TẢI.\n\n"
            "③ QUÉT KÊNH:\n"
            "   • Vào Chế độ tải → Quét Kênh (Ctrl+2).\n"
            "   • Dán URL trang cá nhân / fanpage.\n"
            "   • Đặt bộ lọc Viral nếu muốn.\n"
            "   • Nhấn Quét kênh → tích chọn video → BẮT ĐẦU TẢI.\n\n"
            "④ COOKIE FACEBOOK / DOUYIN:\n"
            "   • Xuất cookie qua Extension 'Get cookies.txt LOCALLY'.\n"
            "   • Vào menu Tệp → Nạp file Cookie để nạp vào phần mềm.\n\n"
            "⑤ LỒNG TIẾNG AI:\n"
            "   • Vào Công cụ → Cài đặt Lồng tiếng AI (Ctrl+L).\n"
            "   • Cài đặt xong, bật 'Tự động lồng tiếng' → video tải xong\n"
            "     sẽ được lồng tiếng Tiếng Việt tự động."
        )

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

        max_videos = self._max_videos_spinbox.value()
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
        self._append_log("HỆ THỐNG", f"Quét kênh: {url} (max {max_videos} video{finfo})")

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
        self._result_table.setItem(row, 0, chk)

        ti = QTableWidgetItem(video.get("title", ""))
        ti.setToolTip(video.get("title", ""))
        self._result_table.setItem(row, 1, ti)

        vi = QTableWidgetItem(video.get("views", "--"))
        vi.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        vi.setForeground(QColor("#38bdf8"))
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
        ui.setToolTip(video.get("url", ""))
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

        # Kiểm tra nếu lỗi liên quan đến bảo mật Cookie hoặc bị chặn
        url_curr = self._channel_url_input.text().strip().lower()
        err_lower = error.lower()
        is_cookie_block = (
            "cookie" in err_lower
            or "chặn" in err_lower
            or "đăng nhập" in err_lower
            or "truy cập" in err_lower
            or not self.cookies_path
        )
        is_platform = (
            "tiktok.com" in url_curr
            or "douyin.com" in url_curr
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

    def _on_select_all(self) -> None:
        self._result_table.blockSignals(True)
        for r in range(self._result_table.rowCount()):
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

    def _update_selected_count(self) -> None:
        count = sum(
            1 for r in range(self._result_table.rowCount())
            if self._result_table.item(r, 0)
            and self._result_table.item(r, 0).checkState() == Qt.CheckState.Checked
        )
        self._lbl_selected_count.setText(f"Đã chọn: {count} video")
        clr = COLORS["accent_green"] if count > 0 else COLORS["text_muted"]
        self._lbl_selected_count.setStyleSheet(
            f"color:{clr}; font-size:12px;" + (" font-weight:600;" if count > 0 else "")
        )

    def _on_export_csv(self) -> None:
        if not self._scanned_videos:
            QMessageBox.warning(self, "Thông báo", "Không có dữ liệu. Hãy quét kênh trước.")
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
                w.writerows(self._scanned_videos)
            self._append_log(
                "HỆ THỐNG",
                f"Xuất {len(self._scanned_videos)} video ra CSV: {os.path.basename(path)}"
            )
            QMessageBox.information(
                self, "Thành công", f"Đã xuất {len(self._scanned_videos)} video ra:\n{path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể ghi file CSV:\n{e}")

    # ══════════════════════════════════════════════════════════════════
    # XỬ LÝ SỰ KIỆN — TẢI VIDEO (Chung)
    # ══════════════════════════════════════════════════════════════════

    def _on_start_download(self) -> None:
        if self._stack.currentIndex() == self.PAGE_LINKS:
            urls = extract_urls(self._url_input.toPlainText())
            if not urls:
                QMessageBox.warning(
                    self, "Cảnh báo",
                    "Không tìm thấy liên kết hợp lệ!\n\n"
                    "Hãy dán ít nhất một liên kết TikTok, Douyin, Facebook hoặc YouTube."
                )
                return
        else:
            urls = []
            for r in range(self._result_table.rowCount()):
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

    def _get_dub_config(self) -> DubConfig:
        return DubConfig(
            source_lang=self.dub_lang,
            voice=self.dub_voice,
            bg_volume=self.bg_volume / 100.0,
            whisper_model=self.whisper_model,
        )

    def _start_dubbing(self, video_path: str) -> None:
        if self._is_dubbing:
            self._append_log("LỒNG TIẾNG", f"Bỏ qua {Path(video_path).name} — đang bận lồng tiếng.")
            return
        config = self._get_dub_config()
        self._dub_worker = DubWorker(
            input_video=video_path, config=config, parent=self
        )
        self._dub_worker.log_message.connect(lambda m: self._append_log("LỒNG TIẾNG", m))
        self._dub_worker.dub_progress.connect(self._on_dub_progress)
        self._dub_worker.dub_finished.connect(self._on_dub_finished)
        self._dub_worker.dub_error.connect(self._on_dub_error)
        self._dub_worker.finished.connect(self._on_dub_worker_done)
        self._is_dubbing = True
        self._append_log("LỒNG TIẾNG", f"Bắt đầu lồng tiếng: {Path(video_path).name}")
        self._status_bar.showMessage(f"Lồng tiếng AI: {Path(video_path).name}")
        self._dub_worker.start()

    def _on_dub_progress(self, current: int, total: int) -> None:
        pct = int(current / total * 100) if total > 0 else 0
        self._status_bar.showMessage(f"Lồng tiếng AI: câu {current}/{total} ({pct}%)")

    def _on_dub_finished(self, output_path: str) -> None:
        self._append_log("LỒNG TIẾNG", f"✅ Hoàn tất lồng tiếng! → {Path(output_path).name}")
        QMessageBox.information(
            self, "Lồng tiếng AI hoàn tất",
            f"🎉 Đã lồng tiếng Tiếng Việt thành công!\n\n📁 File: {output_path}",
        )

    def _on_dub_error(self, error_msg: str) -> None:
        self._append_log("LỒNG TIẾNG", f"❌ Lỗi lồng tiếng: {error_msg}")
        QMessageBox.warning(self, "Lỗi lồng tiếng AI", f"Tiến trình gặp lỗi:\n\n{error_msg}")

    def _on_dub_worker_done(self) -> None:
        self._is_dubbing = False
        self._dub_worker = None
        self._status_bar.showMessage("Trạng thái: Sẵn sàng")

    # ══════════════════════════════════════════════════════════════════
    # CALLBACKS DOWNLOAD WORKER
    # ══════════════════════════════════════════════════════════════════

    def _on_status_updated(self, message: str) -> None:
        self._status_bar.showMessage(f"Trạng thái: {message}")

    def _on_progress_updated(self, percent: float, detail: str) -> None:
        completed = self._success_count + self._fail_count
        overall = (completed / self._total_urls * 100.0) if self._total_urls > 0 else 0.0
        val = min(100, max(0, int(overall)))
        self._progress_bar.setValue(val)
        self._progress_label.setText(
            f"Tiến độ: {val}%  ({completed}/{self._total_urls} video) — {detail}"
        )
        self._update_badges()
        self._status_bar.showMessage(
            f"Đang tải {completed}/{self._total_urls}... → {self.output_dir}"
        )

    def _on_item_finished(self, url: str, success: bool, error: str) -> None:
        if success:
            self._success_count += 1
            # Tự động lồng tiếng nếu bật
            if self.auto_dub and not self._is_dubbing:
                try:
                    mp4s = sorted(
                        Path(self.output_dir).glob("*.mp4"),
                        key=os.path.getmtime, reverse=True
                    )
                    for f in mp4s:
                        if not f.name.endswith("_dubbed.mp4"):
                            self._append_log(
                                "LỒNG TIẾNG",
                                f"Phát hiện video mới: {f.name} → Lồng tiếng tự động..."
                            )
                            self._start_dubbing(str(f))
                            break
                except Exception as ex:
                    self._append_log("LỒNG TIẾNG", f"Không kích hoạt được tự động: {ex}")
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
                self._append_log_raw(clean[:end + 1], platform, clean[end + 1:].strip())
                return
        self._append_log(platform, clean)

    def _on_batch_finished(self, success_count: int, fail_count: int) -> None:
        self._success_count = success_count
        self._fail_count = fail_count
        self._active_count = 0
        self._progress_bar.setValue(100)
        self._progress_label.setText("Tiến độ: 100%")
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
        self._stack.setCurrentIndex(index)

    def _refresh_statusbar(self) -> None:
        dir_disp = self.output_dir if self.output_dir else "Chưa chọn"
        dub_disp = "BẬT" if self.auto_dub else "TẮT"
        self._sb_label.setText(f"📁 {dir_disp}  |  🎙 Lồng tiếng: {dub_disp}")

    def _update_button_states(self) -> None:
        self._btn_start.setEnabled(not self._is_downloading)
        self._btn_stop.setEnabled(self._is_downloading)
        self._btn_stop.setText("⏹  Dừng tải")

    def _update_badges(self) -> None:
        self._badge_total.setText(f"  Tổng: {self._total_urls} video  ")
        self._badge_success.setText(f"  Đã tải: {self._success_count}  ")
        self._badge_active.setText(f"  Đang tải: {self._active_count}  ")
        self._badge_error.setText(f"  Lỗi: {self._fail_count}  ")

    def _append_log(self, tag: str, message: str) -> None:
        ts = datetime.now().strftime("[%H:%M:%S]")
        self._append_log_raw(ts, tag, message)

    def _append_log_raw(self, timestamp: str, tag: str, message: str) -> None:
        tag_color = PLATFORM_COLORS.get(tag, COLORS["text_muted"])
        html = (
            f'<p style="margin:1px 0; white-space:pre;">'
            f'<span style="color:{COLORS["text_placeholder"]}; font-size:11px;">{timestamp}</span>'
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
        if "lồng tiếng" in m or "whisper" in m or "edge-tts" in m:
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

    def _page_titlebar(self, title: str, hint: str) -> QHBoxLayout:
        row = QHBoxLayout()
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"font-size:14px; font-weight:700; color:{COLORS['text_primary']};"
        )
        row.addWidget(lbl)
        row.addStretch()
        h = QLabel(hint)
        h.setStyleSheet(f"color:{COLORS['text_placeholder']}; font-size:11px;")
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

        event.accept()
