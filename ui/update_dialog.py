"""
ui/update_dialog.py - Hộp thoại Cập nhật Tự động OmniGrab chuẩn Desktop Hiện Đại.

Tính năng:
- Hiển thị phiên bản hiện tại vs phiên bản mới nhất, dung lượng tải và nhật ký phát hành (Changelog).
- Tải bản cập nhật trực tiếp trong ứng dụng với thanh tiến trình mượt mà (MB, %, tốc độ tải, thời gian còn lại).
- Tự động thực thi Silent Installer (/SILENT) và khởi động lại ứng dụng chỉ với 1 cú click.
- Tự động nhận diện nếu bản cài đặt đã được tải xong trước đó để không bắt tải lại.
- Tùy chọn mở tải thủ công qua trình duyệt dành cho người dùng muốn lưu trữ file bộ cài.
"""

from __future__ import annotations

from typing import Optional
from pathlib import Path

# pyrefly: ignore [missing-import]
from PyQt6.QtCore import Qt, QTimer, QUrl
# pyrefly: ignore [missing-import]
from PyQt6.QtGui import QDesktopServices, QFont
# pyrefly: ignore [missing-import]
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.auto_updater import (
    UpdateDownloadWorker,
    format_size,
    format_speed,
    get_cached_installer_path,
    is_installer_downloaded,
    launch_silent_update_and_restart,
)
from core.update_checker import ReleaseUpdate
from core.version import APP_VERSION
from ui.styles import COLORS


class UpdateDialog(QDialog):
    """
    Hộp thoại cập nhật phiên bản mới tự động, hiện đại và không làm gián đoạn người dùng.
    """

    def __init__(self, update: ReleaseUpdate, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.update_info = update
        self._worker: Optional[UpdateDownloadWorker] = None
        self._countdown_seconds = 5
        self._countdown_timer: Optional[QTimer] = None
        self._downloaded_installer_path: Optional[str] = None

        self.setWindowTitle(f"Cập nhật OmniGrab v{self.update_info.version}")
        self.setFixedWidth(560)
        self.setModal(True)

        self._build_ui()
        self._apply_styles()
        self._check_initial_state()

    def _build_ui(self) -> None:
        c = COLORS

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(16)

        # ── 1. HEADER ──
        hdr_layout = QHBoxLayout()
        hdr_layout.setSpacing(14)

        icon_lbl = QLabel("🚀")
        icon_lbl.setStyleSheet("font-size: 36px;")
        hdr_layout.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(3)
        self.lbl_title = QLabel("Đã có phiên bản OmniGrab mới!")
        self.lbl_title.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {c['text_primary']};")

        self.lbl_subtitle = QLabel("Tự động tải & cài đặt phiên bản mới chỉ với 1 thao tác.")
        self.lbl_subtitle.setStyleSheet(f"font-size: 12px; color: {c['text_secondary']};")
        title_vbox.addWidget(self.lbl_title)
        title_vbox.addWidget(self.lbl_subtitle)
        hdr_layout.addLayout(title_vbox, 1)

        layout.addLayout(hdr_layout)

        # ── 2. VERSION BADGES CARD ──
        vcard = QFrame()
        vcard.setObjectName("versionCard")
        vcard_layout = QHBoxLayout(vcard)
        vcard_layout.setContentsMargins(16, 12, 16, 12)
        vcard_layout.setSpacing(12)

        cur_v_lbl = QLabel(f"Hiện tại: v{APP_VERSION}")
        cur_v_lbl.setStyleSheet(f"color: {c['text_muted']}; font-size: 12px; font-weight: 600;")

        arrow_lbl = QLabel("➔")
        arrow_lbl.setStyleSheet(f"color: {c['accent_primary']}; font-size: 14px; font-weight: 700;")

        new_v_lbl = QLabel(f"Mới nhất: v{self.update_info.version}")
        new_v_lbl.setStyleSheet(f"color: {c['status_success']}; font-size: 13px; font-weight: 700;")

        vcard_layout.addWidget(cur_v_lbl)
        vcard_layout.addWidget(arrow_lbl)
        vcard_layout.addWidget(new_v_lbl)
        vcard_layout.addStretch(1)

        if self.update_info.size > 0:
            size_badge = QLabel(f"Dung lượng: ~{format_size(self.update_info.size)}")
            size_badge.setStyleSheet(f"color: {c['text_secondary']}; font-size: 11px;")
            vcard_layout.addWidget(size_badge)

        layout.addWidget(vcard)

        # ── 3. CHANGELOG AREA ──
        notes_hdr = QLabel("Nội dung cập nhật (Release Notes):")
        notes_hdr.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {c['text_secondary']};")
        layout.addWidget(notes_hdr)

        self.notes_box = QTextEdit()
        self.notes_box.setReadOnly(True)
        self.notes_box.setFixedHeight(130)
        notes_text = self.update_info.notes.strip()
        if not notes_text:
            notes_text = "• Nâng cấp hiệu năng và tối ưu hóa hệ thống.\n• Vá lỗi và cập nhật bộ thư viện phân tích media mới nhất."
        self.notes_box.setPlainText(notes_text)
        layout.addWidget(self.notes_box)

        # ── 4. PROGRESS CARD (Hidden ban đầu) ──
        self.progress_card = QFrame()
        self.progress_card.setObjectName("progressCard")
        self.progress_card.setVisible(False)
        pcard_layout = QVBoxLayout(self.progress_card)
        pcard_layout.setContentsMargins(14, 12, 14, 12)
        pcard_layout.setSpacing(8)

        self.lbl_progress_status = QLabel("Đang chuẩn bị tải...")
        self.lbl_progress_status.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {c['text_primary']};")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(12)

        self.lbl_progress_details = QLabel("0 MB / 0 MB • 0 MB/s • Còn lại: --")
        self.lbl_progress_details.setStyleSheet(f"font-size: 11px; color: {c['text_muted']};")

        pcard_layout.addWidget(self.lbl_progress_status)
        pcard_layout.addWidget(self.progress_bar)
        pcard_layout.addWidget(self.lbl_progress_details)
        layout.addWidget(self.progress_card)

        # ── 5. READY / SUCCESS BANNER (Hidden ban đầu) ──
        self.ready_banner = QFrame()
        self.ready_banner.setObjectName("readyBanner")
        self.ready_banner.setVisible(False)
        rb_layout = QHBoxLayout(self.ready_banner)
        rb_layout.setContentsMargins(14, 10, 14, 10)
        rb_layout.setSpacing(10)

        rb_icon = QLabel("✔")
        rb_icon.setStyleSheet(f"color: {c['status_success']}; font-size: 18px; font-weight: bold;")
        self.lbl_ready_text = QLabel(
            "Đã tải xong bản cập nhật! OmniGrab sẽ tự động cài đặt ngầm và khởi động lại ngay."
        )
        self.lbl_ready_text.setWordWrap(True)
        self.lbl_ready_text.setStyleSheet(f"color: {c['text_primary']}; font-size: 12px; font-weight: 500;")
        rb_layout.addWidget(rb_icon)
        rb_layout.addWidget(self.lbl_ready_text, 1)
        layout.addWidget(self.ready_banner)

        # ── 6. BUTTON BAR ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        # Nút phụ: Mở trình duyệt tải thủ công
        self.btn_browser = QPushButton("🌐 Tải thủ công")
        self.btn_browser.setObjectName("btnSecondary")
        self.btn_browser.setToolTip("Mở trang GitHub để tải file cài đặt thủ công qua trình duyệt")
        self.btn_browser.clicked.connect(self._on_open_browser)
        btn_layout.addWidget(self.btn_browser)

        btn_layout.addStretch(1)

        # Nút Đóng / Để sau / Hủy
        self.btn_cancel = QPushButton("Để sau")
        self.btn_cancel.setObjectName("btnGhost")
        self.btn_cancel.clicked.connect(self._on_cancel_or_close)
        btn_layout.addWidget(self.btn_cancel)

        # Nút Chính: Cập nhật tự động / Cài đặt ngay
        self.btn_primary = QPushButton("⚡ Cập nhật tự động")
        self.btn_primary.setObjectName("btnPrimary")
        self.btn_primary.clicked.connect(self._on_primary_action)
        btn_layout.addWidget(self.btn_primary)

        layout.addLayout(btn_layout)

    def _apply_styles(self) -> None:
        c = COLORS
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c['bg_primary']};
                color: {c['text_primary']};
            }}
            QFrame#versionCard {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border']};
                border-radius: 8px;
            }}
            QFrame#progressCard {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border_focus']};
                border-radius: 8px;
            }}
            QFrame#readyBanner {{
                background-color: {c['status_success_bg']};
                border: 1px solid {c['status_success_border']};
                border-radius: 8px;
            }}
            QTextEdit {{
                background-color: {c['bg_input']};
                border: 1px solid {c['border']};
                border-radius: 6px;
                color: {c['text_secondary']};
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-size: 12px;
                padding: 8px;
            }}
            QProgressBar {{
                background-color: {c['progress_bg']};
                border: 1px solid {c['border']};
                border-radius: 6px;
                text-align: center;
                color: #ffffff;
                font-size: 10px;
                font-weight: bold;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {c['progress_chunk_start']},
                    stop:1 {c['progress_chunk_end']}
                );
                border-radius: 5px;
            }}
            QPushButton#btnPrimary {{
                background-color: {c['btn_primary_bg']};
                color: {c['btn_primary_text']};
                font-weight: 700;
                font-size: 13px;
                border: none;
                border-radius: 7px;
                padding: 8px 18px;
                min-width: 140px;
            }}
            QPushButton#btnPrimary:hover {{
                background-color: {c['btn_primary_hover']};
            }}
            QPushButton#btnPrimary:pressed {{
                background-color: {c['btn_primary_active']};
            }}
            QPushButton#btnSuccess {{
                background-color: {c['status_success']};
                color: #ffffff;
                font-weight: 700;
                font-size: 13px;
                border: none;
                border-radius: 7px;
                padding: 8px 18px;
                min-width: 160px;
            }}
            QPushButton#btnSuccess:hover {{
                background-color: #059669;
            }}
            QPushButton#btnSecondary {{
                background-color: {c['btn_secondary_bg']};
                color: {c['text_secondary']};
                font-size: 12px;
                border: 1px solid {c['border_light']};
                border-radius: 7px;
                padding: 8px 14px;
            }}
            QPushButton#btnSecondary:hover {{
                background-color: {c['btn_secondary_hover']};
                color: {c['text_primary']};
            }}
            QPushButton#btnGhost {{
                background: transparent;
                color: {c['text_muted']};
                font-size: 12px;
                border: 1px solid transparent;
                border-radius: 7px;
                padding: 8px 14px;
            }}
            QPushButton#btnGhost:hover {{
                background-color: {c['btn_secondary_bg']};
                color: {c['text_secondary']};
            }}
        """)

    def _check_initial_state(self) -> None:
        """Nếu bộ cài đặt phiên bản mới đã nằm trong máy, chuyển thẳng sang trạng thái Sẵn sàng."""
        if is_installer_downloaded(self.update_info.version, self.update_info.size):
            cached_path = get_cached_installer_path(self.update_info.version)
            self._downloaded_installer_path = str(cached_path)
            self._show_ready_state(auto_countdown=False)

    def _on_primary_action(self) -> None:
        """Hành động khi nhấn nút chính (Tải tự động HOẶC Cài đặt & Khởi động lại)."""
        if self._downloaded_installer_path:
            # Đang ở trạng thái đã tải xong -> Bắt đầu cài đặt ngay
            self._apply_update_and_restart()
        else:
            # Chưa tải -> Bắt đầu tải bản cập nhật
            self._start_download()

    def _start_download(self) -> None:
        """Bắt đầu tải bộ cài đặt bằng luồng chạy ngầm."""
        self.progress_card.setVisible(True)
        self.ready_banner.setVisible(False)
        self.btn_primary.setEnabled(False)
        self.btn_primary.setText("Đang tải xuống...")
        self.btn_cancel.setText("Hủy tải")

        self._worker = UpdateDownloadWorker(
            download_url=self.update_info.download_url,
            version=self.update_info.version,
            expected_size=self.update_info.size,
            parent=self,
        )
        self._worker.progress.connect(self._on_download_progress)
        self._worker.finished.connect(self._on_download_finished)
        self._worker.error.connect(self._on_download_error)
        self._worker.cancelled.connect(self._on_download_cancelled)
        self._worker.start()

    def _on_download_progress(
        self,
        downloaded: int,
        total: int,
        speed_bps: float,
        eta_text: str,
    ) -> None:
        percent = int((downloaded / total * 100)) if total > 0 else 0
        percent = max(0, min(100, percent))
        self.progress_bar.setValue(percent)

        self.lbl_progress_status.setText(f"Đang tải bản cập nhật: {percent}%")
        self.lbl_progress_details.setText(
            f"{format_size(downloaded)} / {format_size(total)} • {format_speed(speed_bps)} • Còn lại: {eta_text}"
        )

    def _on_download_finished(self, installer_path: str) -> None:
        self._downloaded_installer_path = installer_path
        self._show_ready_state(auto_countdown=True)

    def _show_ready_state(self, auto_countdown: bool = True) -> None:
        """Hiển thị trạng thái đã tải xong, sẵn sàng cài đặt."""
        self.progress_card.setVisible(False)
        self.ready_banner.setVisible(True)

        self.btn_primary.setEnabled(True)
        self.btn_primary.setObjectName("btnSuccess")
        self._apply_styles()  # Áp dụng màu xanh lá cho nút Cài đặt

        self.btn_cancel.setText("Để sau")

        if auto_countdown:
            self._countdown_seconds = 5
            self._update_countdown_label()
            self._countdown_timer = QTimer(self)
            self._countdown_timer.timeout.connect(self._on_countdown_tick)
            self._countdown_timer.start(1000)
        else:
            self.lbl_ready_text.setText(
                "Bản cài đặt đã được tải sẵn trên máy tính. Bạn có thể cài đặt và khởi động lại ngay."
            )
            self.btn_primary.setText("🚀 Cài đặt & Khởi động lại ngay")

    def _update_countdown_label(self) -> None:
        self.btn_primary.setText(f"🚀 Cài đặt & Khởi động lại ({self._countdown_seconds}s)")
        self.lbl_ready_text.setText(
            f"Đã tải xong! Ứng dụng sẽ tự động đóng và khởi động lại sau {self._countdown_seconds} giây..."
        )

    def _on_countdown_tick(self) -> None:
        self._countdown_seconds -= 1
        if self._countdown_seconds <= 0:
            if self._countdown_timer:
                self._countdown_timer.stop()
            self._apply_update_and_restart()
        else:
            self._update_countdown_label()

    def _on_download_error(self, message: str) -> None:
        self.progress_card.setVisible(False)
        self.btn_primary.setEnabled(True)
        self.btn_primary.setText("🔄 Thử lại")
        self.btn_cancel.setText("Để sau")

        QMessageBox.warning(
            self,
            "Lỗi tải cập nhật",
            f"Không thể tải bản cập nhật tự động:\n{message}\n\n"
            "Bạn có thể bấm 'Tải thủ công' để mở trình duyệt hoặc bấm 'Thử lại'.",
        )

    def _on_download_cancelled(self) -> None:
        self.progress_card.setVisible(False)
        self.btn_primary.setEnabled(True)
        self.btn_primary.setText("⚡ Cập nhật tự động")
        self.btn_cancel.setText("Để sau")

    def _apply_update_and_restart(self) -> None:
        """Dừng timer và thực thi silent updater."""
        if self._countdown_timer:
            self._countdown_timer.stop()

        if not self._downloaded_installer_path:
            return

        # Kiểm tra nếu cửa sổ chính đang có video tải dở
        parent_w = self.parent()
        if parent_w and getattr(parent_w, "_is_downloading", False):
            reply = QMessageBox.question(
                self,
                "Đang có tác vụ tải video",
                "Hiện đang có video đang tải dở. Bạn có chắc chắn muốn dừng tác vụ để cập nhật và khởi động lại ngay không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return

        # Thực thi bộ cài đặt và khởi động lại ứng dụng
        ok = launch_silent_update_and_restart(self._downloaded_installer_path)
        if not ok:
            QMessageBox.critical(
                self,
                "Lỗi cập nhật",
                "Không thể khởi chạy bộ cài đặt tự động. Vui lòng mở file cài đặt thủ công trong thư mục:",
            )
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self._downloaded_installer_path).parent)))

    def _on_open_browser(self) -> None:
        """Mở trang tải GitHub trực tiếp bằng trình duyệt."""
        if not QDesktopServices.openUrl(QUrl(self.update_info.download_url)):
            QDesktopServices.openUrl(QUrl(self.update_info.release_url))

    def _on_cancel_or_close(self) -> None:
        """Hủy tải hoặc đóng hộp thoại."""
        if self._countdown_timer:
            self._countdown_timer.stop()

        if self._worker and self._worker.isRunning():
            self._worker.cancel()
        else:
            self.reject()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._countdown_timer:
            self._countdown_timer.stop()
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
        event.accept()

