"""
ui/tiktok_upload_dialog.py — Hộp thoại Cài đặt Tự động Đăng Video lên TikTok.
Đồng bộ thiết kế Dark Theme với DubbingDialog và hệ thống OmniGrab.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.styles import COLORS


def _resolve_icon_path(rel_path: str) -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target = os.path.join(base, rel_path)
    return target if os.path.exists(target) else rel_path


class TikTokUploadDialog(QDialog):
    """
    Popup cài đặt Tự động Đăng TikTok (Auto TikTok Upload).
    Mở qua Menu Công cụ ➔ Cài đặt Tự động Đăng TikTok...
    """

    def __init__(
        self,
        auto_upload: bool = False,
        privacy: str = "public",
        delay_minutes: int = 45,
        cookies_path: str = "",
        headless: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cài đặt Tự động Đăng Video lên TikTok")
        tt_icon_p = _resolve_icon_path("assets/icon/titktok.png")
        if os.path.exists(tt_icon_p):
            self.setWindowIcon(QIcon(tt_icon_p))
        self.setMinimumWidth(580)
        self.setModal(True)

        self.result_auto_upload = auto_upload
        self.result_privacy = privacy
        self.result_delay_minutes = delay_minutes
        self.result_cookies_path = cookies_path
        self.result_headless = headless

        self._build_ui()

    def _build_ui(self) -> None:
        c = COLORS
        ck_p = _resolve_icon_path("assets/checkmark.png").replace("\\", "/")
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c['bg_secondary']};
            }}
            QLabel {{
                color: {c['text_primary']};
                background: transparent;
            }}
            QCheckBox {{
                color: {c['text_primary']};
                font-size: 13px;
                spacing: 10px;
                background: transparent;
            }}
            QCheckBox:checked {{
                color: #ffffff;
                font-weight: 600;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid #64748b;
                background-color: {c['bg_input']};
            }}
            QCheckBox::indicator:hover {{
                border-color: #22c55e;
            }}
            QCheckBox::indicator:checked {{
                border: 2px solid #22c55e;
                background-color: #22c55e;
                image: url({ck_p});
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
            QPushButton {{
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # ── 1. Tiêu đề ──
        h_box = QHBoxLayout()
        lbl_icon = QLabel()
        tt_icon_p = _resolve_icon_path("assets/icon/titktok.png")
        if os.path.exists(tt_icon_p):
            pix = QPixmap(tt_icon_p).scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl_icon.setPixmap(pix)
        else:
            lbl_icon.setText("🎵")
            lbl_icon.setStyleSheet(f"font-size: 20px; color: {c['platform_tiktok']};")

        lbl_header = QLabel("Tự động Đăng TikTok (Auto TikTok Uploader)")
        lbl_header.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {c['platform_tiktok']};"
        )
        h_box.addWidget(lbl_icon)
        h_box.addWidget(lbl_header)
        h_box.addStretch(1)
        root.addLayout(h_box)

        lbl_desc = QLabel(
            "Tự động hóa 1-chạm: Sau khi lồng tiếng xong, Gemini sẽ tự tạo Caption & Hashtag "
            "chuẩn SEO và Playwright tự động đăng lên kênh TikTok của bạn."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(f"font-size: 12px; color: {c['text_secondary']};")
        root.addWidget(lbl_desc)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {c['border']};")
        root.addWidget(sep)

        # ── 2. Checkbox kích hoạt ──
        self._chk_auto = QCheckBox("Tự động đăng lên kênh TikTok sau khi lồng tiếng xong")
        self._chk_auto.setChecked(self.result_auto_upload)
        root.addWidget(self._chk_auto)

        # ── 3. Grid thông số cấu hình ──
        grid_frame = QFrame()
        grid_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border']};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        grid = QGridLayout(grid_frame)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)

        # Chế độ hiển thị
        lbl_priv = QLabel("Chế độ hiển thị video:")
        lbl_priv.setStyleSheet(f"font-weight: 500; color: {c['text_primary']};")
        grid.addWidget(lbl_priv, 0, 0)

        self._combo_privacy = QComboBox()
        self._combo_privacy.addItem("🌍  Công khai (Public)", "public")
        self._combo_privacy.addItem("🔒  Riêng tư / Bản nháp (Private/Draft)", "private")
        idx_p = self._combo_privacy.findData(self.result_privacy)
        if idx_p >= 0:
            self._combo_privacy.setCurrentIndex(idx_p)
        grid.addWidget(self._combo_privacy, 0, 1)

        # Giãn cách an toàn
        lbl_delay = QLabel("Giãn cách đăng an toàn:")
        lbl_delay.setStyleSheet(f"font-weight: 500; color: {c['text_primary']};")
        grid.addWidget(lbl_delay, 1, 0)

        delay_layout = QHBoxLayout()
        self._spin_delay = QSpinBox()
        self._spin_delay.setRange(1, 180)
        self._spin_delay.setValue(self.result_delay_minutes)
        self._spin_delay.setSuffix("  phút / video")
        delay_layout.addWidget(self._spin_delay)

        lbl_delay_tip = QLabel("(Tránh bị bóp 0 view hoặc đánh spam)")
        lbl_delay_tip.setStyleSheet(f"font-size: 11px; color: {c['accent_orange']};")
        delay_layout.addWidget(lbl_delay_tip)
        grid.addLayout(delay_layout, 1, 1)

        # Chạy ẩn danh
        self._chk_headless = QCheckBox("Chạy trình duyệt ẩn ngầm trong nền (Bỏ tick để mở trình duyệt quan sát trực tiếp)")
        self._chk_headless.setChecked(self.result_headless)
        grid.addWidget(self._chk_headless, 2, 0, 1, 2)

        root.addWidget(grid_frame)

        # ── 4. Quản lý Cookie TikTok ──
        cookie_frame = QFrame()
        cookie_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border']};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        cookie_layout = QVBoxLayout(cookie_frame)
        cookie_layout.setSpacing(8)

        lbl_cookie_title = QLabel("🍪 Trạng thái Cookie TikTok:")
        lbl_cookie_title.setStyleSheet("font-weight: 600; font-size: 13px;")
        cookie_layout.addWidget(lbl_cookie_title)

        c_row = QHBoxLayout()
        self._lbl_cookie_status = QLabel("")
        self._update_cookie_label()
        c_row.addWidget(self._lbl_cookie_status, 1)

        btn_browse_cookie = QPushButton("Chọn file Cookie (.txt)...")
        btn_browse_cookie.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['btn_secondary_bg']};
                color: {c['text_primary']};
                border: 1px solid {c['btn_outline_border']};
            }}
            QPushButton:hover {{
                background-color: {c['btn_secondary_hover']};
            }}
        """)
        btn_browse_cookie.clicked.connect(self._on_choose_cookie_file)
        c_row.addWidget(btn_browse_cookie)
        cookie_layout.addLayout(c_row)

        lbl_cookie_guide = QLabel(
            "💡 Hướng dẫn: Đăng nhập tiktok.com trên trình duyệt ➔ Dùng tiện ích mở rộng "
            "(như 'Get cookies.txt LOCALLY' trên Chrome/Edge) để xuất file cookies.txt."
        )
        lbl_cookie_guide.setWordWrap(True)
        lbl_cookie_guide.setStyleSheet(f"font-size: 11px; color: {c['text_secondary']};")
        cookie_layout.addWidget(lbl_cookie_guide)

        root.addWidget(cookie_frame)

        root.addStretch(1)

        # ── 5. Nút bấm Footer ──
        footer = QHBoxLayout()
        footer.addStretch(1)

        btn_cancel = QPushButton("Hủy bỏ")
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['btn_secondary_bg']};
                color: {c['text_primary']};
                border: 1px solid {c['btn_outline_border']};
            }}
            QPushButton:hover {{
                background-color: {c['btn_secondary_hover']};
            }}
        """)
        btn_cancel.clicked.connect(self.reject)
        footer.addWidget(btn_cancel)

        btn_save = QPushButton("💾  Lưu cài đặt")
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['platform_tiktok']};
                color: #ffffff;
                font-weight: 600;
                border: none;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
        btn_save.clicked.connect(self._on_save)
        footer.addWidget(btn_save)

        root.addLayout(footer)

    def _update_cookie_label(self) -> None:
        c = COLORS
        if self.result_cookies_path and os.path.isfile(self.result_cookies_path):
            fname = os.path.basename(self.result_cookies_path)
            self._lbl_cookie_status.setText(f"✅ Đã nạp: {fname}")
            self._lbl_cookie_status.setStyleSheet(f"color: {c['badge_success_border']}; font-weight: 500;")
        else:
            self._lbl_cookie_status.setText("⚠️ Chưa nạp file Cookie TikTok (Cần file .txt)")
            self._lbl_cookie_status.setStyleSheet(f"color: {c['accent_orange']};")

    def _on_choose_cookie_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file Cookie TikTok",
            "",
            "Cookie files (*.txt *.json);;Tất cả file (*.*)",
        )
        if file_path and os.path.isfile(file_path):
            self.result_cookies_path = file_path
            self._update_cookie_label()

    def _on_save(self) -> None:
        self.result_auto_upload = self._chk_auto.isChecked()
        self.result_privacy = str(self._combo_privacy.currentData() or "public")
        self.result_delay_minutes = int(self._spin_delay.value())
        self.result_headless = self._chk_headless.isChecked()
        self.accept()
