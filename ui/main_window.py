"""
ui/main_window.py - Giao diện chính PyQt6 cho ứng dụng tải video hàng loạt.

Layout 2 cột:
  - Cột trái: Danh sách liên kết + Cấu hình tải
  - Cột phải: Tiến trình + Nhật ký hệ thống

Toàn bộ giao diện hiển thị bằng Tiếng Việt.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# pyrefly: ignore [missing-import]
from PyQt6.QtCore import Qt
# pyrefly: ignore [missing-import]
from PyQt6.QtGui import QFont, QTextCursor, QColor, QSyntaxHighlighter, QTextCharFormat
# pyrefly: ignore [missing-import]
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QTextEdit,
    QPlainTextEdit,
    QLineEdit,
    QPushButton,
    QLabel,
    QSpinBox,
    QProgressBar,
    QStatusBar,
    QGroupBox,
    QFileDialog,
    QMessageBox,
    QSplitter,
    QFrame,
    QCheckBox,
    QSizePolicy,
)

from core.parser import extract_urls, read_urls_from_file
from core.worker import DownloadWorker
from ui.styles import COLORS, PLATFORM_COLORS


class MainWindow(QMainWindow):
    """Cửa sổ giao diện chính - layout 2 cột."""

    def __init__(self) -> None:
        super().__init__()
        self._worker: Optional[DownloadWorker] = None
        self._failed_urls: List[str] = []
        self._is_downloading = False
        self._total_urls = 0
        self._success_count = 0
        self._fail_count = 0
        self._active_count = 0

        self._setup_window()
        self._build_ui()
        self._connect_signals()
        self._update_button_states()
        self._append_log("HỆ THỐNG", "Ứng dụng OmniGrab đã sẵn sàng. Dán liên kết video và nhấn BẮT ĐẦU TẢI.")

    # ═══════════════════════ THIẾT LẬP CỬA SỔ ═══════════════════════

    def _setup_window(self) -> None:
        self.setWindowTitle("OmniGrab — Công Cụ Tải Video Hàng Loạt | TikTok · Douyin · Facebook")
        self.setMinimumSize(1060, 640)
        self.resize(1160, 720)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Trạng thái: Sẵn sàng")

    # ═══════════════════════ XÂY DỰNG GIAO DIỆN ═══════════════════════

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(12, 10, 12, 6)
        root.setSpacing(12)

        # ─── Cột trái ───
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        left_layout.addWidget(self._build_url_section())
        left_layout.addWidget(self._build_settings_section())

        # ─── Cột phải ───
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        right_layout.addWidget(self._build_progress_section())

        # ─── Nút điều khiển (dưới cùng cột phải) ───
        btn_row = self._build_action_buttons()
        right_layout.addLayout(btn_row)

        # ─── Splitter ngang ───
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([460, 620])

        root.addWidget(splitter)

    # ──────────────── 1. Danh sách liên kết ────────────────

    def _build_url_section(self) -> QWidget:
        card = self._make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        title = QLabel("1. Danh sách liên kết cần tải (Mỗi dòng 1 link)")
        title.setStyleSheet(f"font-weight:700; font-size:13px; color:{COLORS['text_primary']};")
        header.addWidget(title)
        header.addStretch()

        self._btn_import = QPushButton("📂 Nhập từ file")
        self._btn_import.setFixedHeight(28)
        self._btn_import.setStyleSheet(self._small_btn_style())
        header.addWidget(self._btn_import)

        self._btn_clear_input = QPushButton("✕ Xóa hết")
        self._btn_clear_input.setFixedHeight(28)
        self._btn_clear_input.setStyleSheet(self._small_btn_style())
        header.addWidget(self._btn_clear_input)

        layout.addLayout(header)

        # URL text area
        self._url_input = QPlainTextEdit()
        self._url_input.setPlaceholderText(
            "Dán danh sách liên kết TikTok, Douyin, Facebook vào đây...\n\n"
            "Hỗ trợ cả văn bản chia sẻ kèm link, ví dụ:\n"
            '  7.12 复制打开抖音 https://v.douyin.com/xxxxx/\n'
            '  https://www.tiktok.com/@user/video/1234567890'
        )
        self._url_input.setMinimumHeight(160)
        self._url_input.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {COLORS['bg_input']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['bg_input_border']};
                border-radius: 6px;
                padding: 8px 8px 8px 8px;
                font-family: "Cascadia Code", "Consolas", monospace;
                font-size: 12px;
            }}
        """)
        layout.addWidget(self._url_input, 1)

        # Footer: đếm URL
        self._url_count_label = QLabel("Tổng cộng: 0 liên kết phát hiện")
        self._url_count_label.setStyleSheet(f"color:{COLORS['text_muted']}; font-size:12px;")
        layout.addWidget(self._url_count_label)

        return card

    # ──────────────── 2. Cấu hình tải & Lưu trữ ────────────────

    def _build_settings_section(self) -> QWidget:
        card = self._make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(10)

        title = QLabel("2. Cấu hình tải & Lưu trữ:")
        title.setStyleSheet(f"font-weight:700; font-size:13px; color:{COLORS['text_primary']};")
        layout.addWidget(title)

        # ── Thư mục lưu ──
        lbl_dir = QLabel("Thư mục lưu video:")
        lbl_dir.setStyleSheet(f"color:{COLORS['text_secondary']}; font-size:12px;")
        layout.addWidget(lbl_dir)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(8)
        self._output_dir_input = QLineEdit()
        self._output_dir_input.setReadOnly(True)
        default_dir = str(Path.home() / "Videos" / "OmniGrab_Downloads")
        try:
            os.makedirs(default_dir, exist_ok=True)
        except OSError:
            default_dir = str(Path.home() / "Downloads")
        self._output_dir_input.setText(default_dir)
        dir_row.addWidget(self._output_dir_input, 1)

        self._btn_browse_dir = QPushButton("Duyệt...")
        self._btn_browse_dir.setFixedWidth(80)
        self._btn_browse_dir.setStyleSheet(self._action_btn_style())
        dir_row.addWidget(self._btn_browse_dir)
        layout.addLayout(dir_row)

        # ── Cookie ──
        lbl_cookie = QLabel("File Cookie Facebook / Douyin (.txt - Tùy chọn):")
        lbl_cookie.setStyleSheet(f"color:{COLORS['text_secondary']}; font-size:12px;")
        layout.addWidget(lbl_cookie)

        cookie_row = QHBoxLayout()
        cookie_row.setSpacing(8)
        self._cookie_file_input = QLineEdit()
        self._cookie_file_input.setReadOnly(True)
        self._cookie_file_input.setPlaceholderText("")
        cookie_row.addWidget(self._cookie_file_input, 1)

        self._btn_browse_cookie = QPushButton("Chọn...")
        self._btn_browse_cookie.setFixedWidth(80)
        self._btn_browse_cookie.setStyleSheet(self._action_btn_style())
        cookie_row.addWidget(self._btn_browse_cookie)
        layout.addLayout(cookie_row)

        # ── Số luồng ──
        thread_row = QHBoxLayout()
        thread_row.setSpacing(8)
        lbl_threads = QLabel("Số luồng tải đồng thời:")
        lbl_threads.setStyleSheet(f"color:{COLORS['text_secondary']}; font-size:12px;")
        thread_row.addWidget(lbl_threads)

        self._thread_spinbox = QSpinBox()
        self._thread_spinbox.setRange(1, 5)
        self._thread_spinbox.setValue(3)
        self._thread_spinbox.setFixedWidth(80)
        thread_row.addWidget(self._thread_spinbox)
        thread_row.addStretch()
        layout.addLayout(thread_row)

        # ── Separator ──
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color:{COLORS['border']}; max-height:1px;")
        layout.addWidget(sep)

        # ── Checkboxes ──
        self._chk_no_watermark = QCheckBox("Tự động trích xuất video gốc KHÔNG logo / watermark")
        self._chk_no_watermark.setChecked(True)
        layout.addWidget(self._chk_no_watermark)

        self._chk_ffmpeg_merge = QCheckBox("Tự động ghép âm thanh & video độ phân giải cao nhất (FFmpeg)")
        self._chk_ffmpeg_merge.setChecked(True)
        layout.addWidget(self._chk_ffmpeg_merge)

        self._chk_skip_existing = QCheckBox("Bỏ qua các video đã tải trước đó trong thư mục")
        self._chk_skip_existing.setChecked(True)
        layout.addWidget(self._chk_skip_existing)

        return card

    # ──────────────── 3. Tiến trình & Nhật ký ────────────────

    def _build_progress_section(self) -> QWidget:
        card = self._make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        title = QLabel("3. Tiến trình tải & Nhật ký hệ thống:")
        title.setStyleSheet(f"font-weight:700; font-size:13px; color:{COLORS['text_primary']};")
        layout.addWidget(title)

        # ── Stat badges ──
        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)

        self._badge_total = self._make_badge("Tổng: 0 video", COLORS["badge_total_bg"], COLORS["border"])
        self._badge_success = self._make_badge("Đã tải: 0 video", COLORS["badge_success_bg"], COLORS["badge_success_border"])
        self._badge_active = self._make_badge("Đang tải: 0", COLORS["badge_active_bg"], COLORS["badge_active_border"])
        self._badge_error = self._make_badge("Lỗi: 0", COLORS["badge_error_bg"], COLORS["badge_error_border"])

        badge_row.addWidget(self._badge_total)
        badge_row.addWidget(self._badge_success)
        badge_row.addWidget(self._badge_active)
        badge_row.addWidget(self._badge_error)
        badge_row.addStretch()
        layout.addLayout(badge_row)

        # ── Progress bar ──
        self._progress_label = QLabel("Tiến độ tổng thể: 0%")
        self._progress_label.setStyleSheet(f"color:{COLORS['text_secondary']}; font-size:12px;")
        layout.addWidget(self._progress_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)

        # ── Log header ──
        log_header = QHBoxLayout()
        log_title = QLabel("NHẬT KÝ HOẠT ĐỘNG (REALTIME LOGS)")
        log_title.setStyleSheet(f"color:{COLORS['text_muted']}; font-size:11px; font-weight:600; letter-spacing:0.5px;")
        log_header.addWidget(log_title)
        log_header.addStretch()

        self._btn_export_errors = QPushButton("📤 Xuất file lỗi (.txt)")
        self._btn_export_errors.setFixedHeight(26)
        self._btn_export_errors.setStyleSheet(self._small_btn_style())
        self._btn_export_errors.setEnabled(False)
        log_header.addWidget(self._btn_export_errors)

        layout.addLayout(log_header)

        # ── Log view ──
        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMinimumHeight(80)
        self._log_view.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['bg_input']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['bg_input_border']};
                border-radius: 6px;
                padding: 8px;
                font-family: "Cascadia Code", "Consolas", monospace;
                font-size: 11px;
                line-height: 1.6;
            }}
        """)
        layout.addWidget(self._log_view, 1)

        return card

    # ──────────────── Nút điều khiển ────────────────

    def _build_action_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()

        # Dừng tải (outline) — width vừa chữ
        self._btn_stop = QPushButton("⏸  Dừng tải")
        self._btn_stop.setFixedHeight(44)
        self._btn_stop.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._btn_stop.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['text_secondary']};
                border: 1.5px solid {COLORS['btn_outline_border']};
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
                padding: 0 22px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['btn_outline_hover']};
                border-color: {COLORS['text_secondary']};
                color: {COLORS['text_primary']};
            }}
            QPushButton:disabled {{
                color: {COLORS['text_placeholder']};
                border-color: {COLORS['border']};
            }}
        """)
        row.addWidget(self._btn_stop)

        # BẮT ĐẦU TẢI (solid green) — width vừa chữ
        self._btn_start = QPushButton("▶  BẮT ĐẦU TẢI")
        self._btn_start.setFixedHeight(44)
        self._btn_start.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._btn_start.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['btn_green_bg']};
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 700;
                padding: 10px 28px;
                letter-spacing: 0.5px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['btn_green_hover']};
            }}
            QPushButton:pressed {{
                background-color: #15803d;
            }}
            QPushButton:disabled {{
                background-color: {COLORS['border']};
                color: {COLORS['text_placeholder']};
            }}
        """)
        row.addWidget(self._btn_start)

        return row

    # ═══════════════════════ KẾT NỐI TÍN HIỆU ═══════════════════════

    def _connect_signals(self) -> None:
        self._btn_import.clicked.connect(self._on_import_file)
        self._btn_clear_input.clicked.connect(self._on_clear_input)
        self._btn_browse_dir.clicked.connect(self._on_browse_dir)
        self._btn_browse_cookie.clicked.connect(self._on_browse_cookie)
        self._btn_start.clicked.connect(self._on_start_download)
        self._btn_stop.clicked.connect(self._on_stop_download)
        self._btn_export_errors.clicked.connect(self._on_export_errors)
        self._url_input.textChanged.connect(self._on_url_text_changed)

    # ═══════════════════════ XỬ LÝ SỰ KIỆN ═══════════════════════

    def _on_import_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file chứa danh sách liên kết", str(Path.home()),
            "File văn bản (*.txt *.csv);;Tất cả file (*.*)",
        )
        if not file_path:
            return

        try:
            urls = read_urls_from_file(file_path)
            if urls:
                existing = self._url_input.toPlainText().strip()
                new_text = "\n".join(urls)
                self._url_input.setPlainText(
                    (existing + "\n" + new_text) if existing else new_text
                )
                self._append_log("HỆ THỐNG", f"Đã nhập {len(urls)} liên kết từ file: {os.path.basename(file_path)}")
            else:
                QMessageBox.warning(
                    self, "Cảnh báo",
                    f"Không tìm thấy liên kết hợp lệ nào trong file:\n{file_path}",
                )
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể đọc file:\n{str(e)}")

    def _on_clear_input(self) -> None:
        if self._url_input.toPlainText().strip():
            reply = QMessageBox.question(
                self, "Xác nhận", "Bạn có chắc muốn xóa toàn bộ danh sách liên kết?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._url_input.clear()

    def _on_browse_dir(self) -> None:
        current = self._output_dir_input.text() or str(Path.home())
        dir_path = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu video tải xuống", current)
        if dir_path:
            self._output_dir_input.setText(dir_path)
            self._append_log("HỆ THỐNG", f"Đã chọn thư mục lưu: {dir_path}")

    def _on_browse_cookie(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file Cookie xác thực (.txt)", str(Path.home()),
            "File Cookie (*.txt);;Tất cả file (*.*)",
        )
        if file_path:
            self._cookie_file_input.setText(file_path)
            self._append_log("HỆ THỐNG", f"Nạp thành công session cookie từ {os.path.basename(file_path)}")

    def _on_url_text_changed(self) -> None:
        raw = self._url_input.toPlainText()
        urls = extract_urls(raw)
        count = len(urls)
        self._url_count_label.setText(f"Tổng cộng: {count} liên kết phát hiện")
        if count > 0:
            self._url_count_label.setStyleSheet(f"color:{COLORS['accent_green']}; font-size:12px; font-weight:600;")
        else:
            self._url_count_label.setStyleSheet(f"color:{COLORS['text_muted']}; font-size:12px;")

    def _on_start_download(self) -> None:
        raw = self._url_input.toPlainText()
        urls = extract_urls(raw)

        if not urls:
            QMessageBox.warning(self, "Cảnh báo",
                "Không tìm thấy liên kết hợp lệ nào!\n\n"
                "Hãy dán ít nhất một liên kết TikTok, Douyin hoặc Facebook.")
            return

        output_dir = self._output_dir_input.text().strip()
        if not output_dir:
            QMessageBox.warning(self, "Cảnh báo", "Chưa chọn thư mục lưu video!")
            return

        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể tạo thư mục:\n{output_dir}\n\n{str(e)}")
            return

        # Reset
        self._failed_urls = []
        self._total_urls = len(urls)
        self._success_count = 0
        self._fail_count = 0
        self._active_count = 0
        self._progress_bar.setValue(0)
        self._btn_export_errors.setEnabled(False)
        self._update_badges()

        cookie_file = self._cookie_file_input.text().strip()
        max_workers = self._thread_spinbox.value()

        self._worker = DownloadWorker(
            urls=urls, output_dir=output_dir,
            cookie_file=cookie_file, max_workers=max_workers,
            parent=self,
        )

        self._worker.status_updated.connect(self._on_status_updated)
        self._worker.progress_updated.connect(self._on_progress_updated)
        self._worker.item_finished.connect(self._on_item_finished)
        self._worker.log_message.connect(self._on_log_message)
        self._worker.batch_finished.connect(self._on_batch_finished)
        self._worker.finished.connect(self._on_worker_finished)

        self._is_downloading = True
        self._active_count = min(max_workers, len(urls))
        self._update_button_states()
        self._update_badges()
        self._worker.start()

        self._append_log("HỆ THỐNG", f"Đã khởi tạo công cụ tải đa luồng ({max_workers} workers)")
        self._status_bar.showMessage(f"Trạng thái: Đang tải video 0/{self._total_urls}... (Tự động lưu vào {output_dir})")

    def _on_stop_download(self) -> None:
        if self._worker and self._is_downloading:
            reply = QMessageBox.question(
                self, "Xác nhận dừng tải",
                "Bạn có chắc muốn dừng quá trình tải?\nCác video đang tải dở sẽ được chờ hoàn tất.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._worker.request_stop()
                self._btn_stop.setEnabled(False)
                self._btn_stop.setText("⏳  Đang dừng...")
                self._status_bar.showMessage("Trạng thái: Đang dừng tải an toàn...")

    def _on_export_errors(self) -> None:
        if not self._failed_urls:
            QMessageBox.information(self, "Thông báo", "Không có liên kết lỗi nào để xuất!")
            return

        default_path = os.path.join(
            self._output_dir_input.text() or str(Path.home()), "danh_sach_loi.txt"
        )
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Lưu danh sách liên kết lỗi", default_path,
            "File văn bản (*.txt);;Tất cả file (*.*)",
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# Danh sách liên kết tải thất bại - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Tổng số: {len(self._failed_urls)} liên kết\n\n")
                for url in self._failed_urls:
                    f.write(url + "\n")
            self._append_log("HỆ THỐNG", f"Đã xuất {len(self._failed_urls)} liên kết lỗi ra file: {os.path.basename(file_path)}")
            QMessageBox.information(self, "Thông báo",
                f"Đã lưu {len(self._failed_urls)} liên kết lỗi vào:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể ghi file:\n{str(e)}")

    # ═══════════════════════ TÍN HIỆU WORKER ═══════════════════════

    def _on_status_updated(self, message: str) -> None:
        self._status_bar.showMessage(f"Trạng thái: {message}")

    def _on_progress_updated(self, percent: float, detail: str) -> None:
        val = int(percent)
        self._progress_bar.setValue(val)
        completed = self._success_count + self._fail_count
        self._active_count = max(0, min(self._thread_spinbox.value(), self._total_urls - completed))
        self._progress_label.setText(f"Tiến độ tổng thể: {val}%")
        self._update_badges()
        self._status_bar.showMessage(
            f"Trạng thái: Đang tải video {completed}/{self._total_urls}... "
            f"(Tự động lưu vào {self._output_dir_input.text()})"
        )

    def _on_item_finished(self, url: str, success: bool, error: str) -> None:
        if success:
            self._success_count += 1
        else:
            self._fail_count += 1
            self._failed_urls.append(url)
        self._update_badges()

    def _on_log_message(self, message: str) -> None:
        # Phát hiện platform tag từ message
        platform = self._detect_platform(message)
        # Loại bỏ timestamp prefix nếu worker đã gắn
        clean = message
        if clean.startswith("["):
            bracket_end = clean.find("]")
            if bracket_end > 0:
                timestamp_part = clean[:bracket_end + 1]
                rest = clean[bracket_end + 1:].strip()
                self._append_log_raw(timestamp_part, platform, rest)
                return
        self._append_log(platform, clean)

    def _on_batch_finished(self, success_count: int, fail_count: int) -> None:
        self._success_count = success_count
        self._fail_count = fail_count
        self._active_count = 0
        self._progress_bar.setValue(100)
        self._progress_label.setText("Tiến độ tổng thể: 100%")
        self._update_badges()

        if self._failed_urls:
            self._btn_export_errors.setEnabled(True)

        if fail_count == 0:
            QMessageBox.information(self, "Hoàn tất quá trình tải",
                f"🎉 Tải thành công tất cả {success_count} video!\n\n"
                f"📁 Thư mục lưu: {self._output_dir_input.text()}")
        else:
            QMessageBox.warning(self, "Hoàn tất quá trình tải",
                f"Kết quả tải {success_count + fail_count} video:\n\n"
                f"  ✅  Thành công: {success_count}\n"
                f"  ❌  Thất bại: {fail_count}\n\n"
                f"Nhấn 'Xuất file lỗi (.txt)' để lưu danh sách link hỏng.")

    def _on_worker_finished(self) -> None:
        self._is_downloading = False
        self._worker = None
        self._active_count = 0
        self._update_button_states()
        self._update_badges()
        self._status_bar.showMessage("Trạng thái: Sẵn sàng")

    # ═══════════════════════ TIỆN ÍCH NỘI BỘ ═══════════════════════

    def _update_button_states(self) -> None:
        self._btn_start.setEnabled(not self._is_downloading)
        self._btn_stop.setEnabled(self._is_downloading)
        self._btn_stop.setText("⏸  Dừng tải")
        self._url_input.setReadOnly(self._is_downloading)
        self._btn_import.setEnabled(not self._is_downloading)
        self._btn_browse_dir.setEnabled(not self._is_downloading)
        self._btn_browse_cookie.setEnabled(not self._is_downloading)
        self._thread_spinbox.setEnabled(not self._is_downloading)

    def _update_badges(self) -> None:
        self._badge_total.setText(f"  Tổng: {self._total_urls} video  ")
        self._badge_success.setText(f"  Đã tải: {self._success_count} video  ")
        self._badge_active.setText(f"  Đang tải: {self._active_count}  ")
        self._badge_error.setText(f"  Lỗi: {self._fail_count}  ")

    def _append_log(self, tag: str, message: str) -> None:
        """Thêm dòng log có tag platform + timestamp."""
        ts = datetime.now().strftime("[%H:%M:%S]")
        self._append_log_raw(ts, tag, message)

    def _append_log_raw(self, timestamp: str, tag: str, message: str) -> None:
        """Thêm dòng log đã format sẵn timestamp."""
        tag_color = PLATFORM_COLORS.get(tag, COLORS["text_muted"])
        ts_color = COLORS["text_placeholder"]
        msg_color = COLORS["text_secondary"]

        html = (
            f'<p style="margin:1px 0; white-space:pre;">'
            f'<span style="color:{ts_color}; font-size:11px;">{timestamp}</span>'
            f'&nbsp;&nbsp;'
            f'<span style="color:{tag_color}; font-weight:700; font-size:11px;">[{tag}]</span>'
            f'&nbsp;&nbsp;'
            f'<span style="color:{msg_color}; font-size:11px;">{message}</span>'
            f'</p>'
        )
        self._log_view.append(html)

        cursor = self._log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._log_view.setTextCursor(cursor)

    def _detect_platform(self, message: str) -> str:
        """Nhận diện nền tảng từ nội dung log."""
        msg_lower = message.lower()
        if "tiktok" in msg_lower:
            return "TIKTOK"
        elif "douyin" in msg_lower or "抖音" in msg_lower:
            return "DOUYIN"
        elif "facebook" in msg_lower or "fb.watch" in msg_lower:
            return "FACEBOOK"
        elif "tiến độ" in msg_lower or "tốc độ" in msg_lower or "percent" in msg_lower:
            return "TIẾN ĐỘ"
        elif any(k in msg_lower for k in ("khởi", "sẵn sàng", "hoàn tất", "dừng", "hệ thống")):
            return "HỆ THỐNG"
        return "HỆ THỐNG"

    # ═══════════════════════ WIDGET FACTORY ═══════════════════════

    def _make_card(self) -> QWidget:
        """Tạo widget card bo góc với viền tinh tế."""
        card = QWidget()
        card.setObjectName("card")
        card.setStyleSheet(f"""
            QWidget#card {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
        """)
        return card

    def _make_badge(self, text: str, bg: str, border: str) -> QLabel:
        """Tạo badge hiển thị số liệu."""
        badge = QLabel(f"  {text}  ")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 6px;
                color: {COLORS['text_primary']};
                font-size: 12px;
                font-weight: 600;
                padding: 5px 12px;
            }}
        """)
        return badge

    def _small_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {COLORS['btn_secondary_bg']};
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['btn_outline_border']};
                border-radius: 5px;
                font-size: 12px;
                padding: 2px 12px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['btn_secondary_hover']};
                color: {COLORS['text_primary']};
            }}
        """

    def _action_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {COLORS['accent_blue']};
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                background-color: #60a5fa;
            }}
        """

    def closeEvent(self, event) -> None:
        if self._is_downloading:
            reply = QMessageBox.question(
                self, "Xác nhận thoát",
                "Đang có video đang tải. Bạn có chắc muốn thoát?\nCác video đang tải dở sẽ bị hủy.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            if self._worker:
                self._worker.request_stop()
                self._worker.wait(3000)
        event.accept()
