"""
ui/cookie_dialog.py — Hộp thoại thông báo & hướng dẫn Cookie cho TikTok, Douyin, Facebook.

Cung cấp:
- CookieGuideDialog: Hướng dẫn chi tiết từng bước cách lấy file cookies.txt.
- CookiePromptDialog: Cảnh báo thông minh trước khi quét kênh nếu chưa có Cookie.
- CookieFailedDialog: Hộp thoại báo lỗi kèm giải pháp nạp Cookie ngay khi quét bị chặn.
"""

from __future__ import annotations

import os
from typing import Optional

# pyrefly: ignore [missing-import]
from PyQt6.QtCore import Qt, QUrl
# pyrefly: ignore [missing-import]
from PyQt6.QtGui import QDesktopServices, QFont
# pyrefly: ignore [missing-import]
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.styles import COLORS

CHROME_EXTENSION_URL = (
    "https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc"
)


class CookieGuideDialog(QDialog):
    """
    Cửa sổ hướng dẫn chi tiết cách lấy file cookies.txt từ trình duyệt.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("🍪 Hướng dẫn lấy Cookie (TikTok · Douyin · Facebook)")
        self.setMinimumWidth(600)
        self.setModal(True)
        self.selected_cookie_file: str = ""
        self._build_ui()

    def _build_ui(self) -> None:
        c = COLORS
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c['bg_primary']};
                color: {c['text_primary']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # ── Header ──
        hdr_layout = QHBoxLayout()
        hdr_layout.setSpacing(12)

        icon_lbl = QLabel("🍪")
        icon_lbl.setStyleSheet("font-size: 32px;")
        hdr_layout.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(4)
        title_lbl = QLabel("Cách lấy file Cookie từ trình duyệt")
        title_lbl.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {c['text_primary']};")
        sub_lbl = QLabel(
            "TikTok, Douyin & Facebook chặn các công cụ quét tự động. "
            "Nạp Cookie (chỉ mất 1 phút làm 1 lần) giúp phần mềm quét & tải trọn vẹn mọi video!"
        )
        sub_lbl.setWordWrap(True)
        sub_lbl.setStyleSheet(f"font-size: 12px; color: {c['text_secondary']}; line-height: 1.4;")
        title_vbox.addWidget(title_lbl)
        title_vbox.addWidget(sub_lbl)
        hdr_layout.addLayout(title_vbox, 1)
        layout.addLayout(hdr_layout)

        # ── Hộp các bước thực hiện ──
        steps_card = QFrame()
        steps_card.setStyleSheet(f"""
            QFrame {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border']};
                border-radius: 8px;
            }}
        """)
        steps_layout = QVBoxLayout(steps_card)
        steps_layout.setContentsMargins(18, 16, 18, 16)
        steps_layout.setSpacing(14)

        # Bước 1
        b1_box = QHBoxLayout()
        b1_box.setSpacing(10)
        b1_badge = QLabel("1")
        b1_badge.setFixedSize(24, 24)
        b1_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        b1_badge.setStyleSheet(f"""
            background-color: {c['accent_cyan']};
            color: #ffffff;
            font-weight: 700;
            font-size: 12px;
            border-radius: 12px;
        """)
        b1_box.addWidget(b1_badge)

        b1_text = QVBoxLayout()
        b1_title = QLabel("Cài tiện ích mở rộng 'Get cookies.txt LOCALLY'")
        b1_title.setStyleSheet(f"font-weight: 600; font-size: 13px; color: {c['text_primary']};")
        b1_sub = QLabel("Tiện ích miễn phí, an toàn trên Chrome Web Store (dùng được cho cả Chrome, Edge, Cốc Cốc, Brave).")
        b1_sub.setStyleSheet(f"font-size: 11px; color: {c['text_secondary']};")
        b1_sub.setWordWrap(True)
        b1_text.addWidget(b1_title)
        b1_text.addWidget(b1_sub)
        b1_box.addLayout(b1_text, 1)

        btn_store = QPushButton("🌐 Mở Chrome Web Store")
        btn_store.setFixedHeight(30)
        btn_store.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['accent_blue']};
                color: #ffffff;
                font-weight: 600;
                font-size: 11px;
                border: none;
                border-radius: 5px;
                padding: 0 12px;
            }}
            QPushButton:hover {{ background-color: #2563eb; }}
        """)
        btn_store.clicked.connect(self._open_chrome_store)
        b1_box.addWidget(btn_store)
        steps_layout.addLayout(b1_box)

        # Bước 2
        b2_box = QHBoxLayout()
        b2_box.setSpacing(10)
        b2_badge = QLabel("2")
        b2_badge.setFixedSize(24, 24)
        b2_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        b2_badge.setStyleSheet(f"""
            background-color: {c['accent_cyan']};
            color: #ffffff;
            font-weight: 700;
            font-size: 12px;
            border-radius: 12px;
        """)
        b2_box.addWidget(b2_badge)

        b2_text = QVBoxLayout()
        b2_title = QLabel("Mở trang web trên trình duyệt và đăng nhập")
        b2_title.setStyleSheet(f"font-weight: 600; font-size: 13px; color: {c['text_primary']};")
        b2_sub = QLabel("Truy cập tiktok.com (hoặc douyin.com / facebook.com) và đăng nhập tài khoản của bạn.")
        b2_sub.setStyleSheet(f"font-size: 11px; color: {c['text_secondary']};")
        b2_text.addWidget(b2_title)
        b2_text.addWidget(b2_sub)
        b2_box.addLayout(b2_text, 1)
        steps_layout.addLayout(b2_box)

        # Bước 3
        b3_box = QHBoxLayout()
        b3_box.setSpacing(10)
        b3_badge = QLabel("3")
        b3_badge.setFixedSize(24, 24)
        b3_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        b3_badge.setStyleSheet(f"""
            background-color: {c['accent_cyan']};
            color: #ffffff;
            font-weight: 700;
            font-size: 12px;
            border-radius: 12px;
        """)
        b3_box.addWidget(b3_badge)

        b3_text = QVBoxLayout()
        b3_title = QLabel("Xuất file Cookie")
        b3_title.setStyleSheet(f"font-weight: 600; font-size: 13px; color: {c['text_primary']};")
        b3_sub = QLabel("Bấm vào biểu tượng tiện ích ở góc trên trình duyệt ➔ Chọn 'Export' (hoặc Download) để lưu file cookies.txt.")
        b3_sub.setStyleSheet(f"font-size: 11px; color: {c['text_secondary']};")
        b3_text.addWidget(b3_title)
        b3_text.addWidget(b3_sub)
        b3_box.addLayout(b3_text, 1)
        steps_layout.addLayout(b3_box)

        # Bước 4
        b4_box = QHBoxLayout()
        b4_box.setSpacing(10)
        b4_badge = QLabel("4")
        b4_badge.setFixedSize(24, 24)
        b4_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        b4_badge.setStyleSheet(f"""
            background-color: {c['accent_green']};
            color: #ffffff;
            font-weight: 700;
            font-size: 12px;
            border-radius: 12px;
        """)
        b4_box.addWidget(b4_badge)

        b4_text = QVBoxLayout()
        b4_title = QLabel("Nạp file vào OmniGrab")
        b4_title.setStyleSheet(f"font-weight: 600; font-size: 13px; color: {c['accent_green']};")
        b4_sub = QLabel("Bấm nút 'Nạp file Cookie (.txt) ngay' bên dưới hoặc vào menu Tệp ➔ Nạp file Cookie (.txt)...")
        b4_sub.setStyleSheet(f"font-size: 11px; color: {c['text_secondary']};")
        b4_text.addWidget(b4_title)
        b4_text.addWidget(b4_sub)
        b4_box.addLayout(b4_text, 1)
        steps_layout.addLayout(b4_box)

        layout.addWidget(steps_card)

        # ── Gợi ý ──
        tip_lbl = QLabel("💡 Lưu ý: File cookie chỉ cần lấy 1 lần và có thể dùng quét cho nhiều kênh/tài khoản khác nhau.")
        tip_lbl.setStyleSheet(f"font-size: 11px; color: {c['accent_orange']}; font-style: italic;")
        layout.addWidget(tip_lbl)

        # ── Nút hành động phía dưới ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_load = QPushButton("🍪 Nạp file Cookie (.txt) ngay...")
        btn_load.setFixedHeight(42)
        btn_load.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['btn_green_bg']};
                color: #ffffff;
                font-weight: 700;
                font-size: 13px;
                border: none;
                border-radius: 8px;
                padding: 6px 20px;
            }}
            QPushButton:hover {{ background-color: {c['btn_green_hover']}; }}
        """)
        btn_load.clicked.connect(self._on_choose_cookie_file)
        btn_layout.addWidget(btn_load)

        btn_layout.addStretch()

        btn_close = QPushButton("Đóng")
        btn_close.setFixedHeight(42)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['btn_secondary_bg']};
                color: {c['text_secondary']};
                font-size: 12px;
                font-weight: 600;
                border: 1px solid {c['border']};
                border-radius: 8px;
                padding: 6px 18px;
            }}
            QPushButton:hover {{
                background-color: {c['btn_secondary_hover']};
                color: {c['text_primary']};
            }}
        """)
        btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

    def _open_chrome_store(self) -> None:
        QDesktopServices.openUrl(QUrl(CHROME_EXTENSION_URL))

    def _on_choose_cookie_file(self) -> None:
        f, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file Cookie (.txt)",
            "",
            "Cookie file (*.txt);;Tất cả file (*.*)",
        )
        if f:
            self.selected_cookie_file = f
            self.accept()


class CookiePromptDialog(QDialog):
    """
    Cảnh báo trước khi quét kênh TikTok/Douyin nếu chưa có Cookie.
    Cho phép người dùng chọn nạp Cookie ngay, xem hướng dẫn, hoặc thử quét tiếp.
    """

    ACTION_CANCEL = 0
    ACTION_LOAD_COOKIE = 1
    ACTION_SHOW_GUIDE = 2
    ACTION_CONTINUE_WITHOUT = 3

    def __init__(self, parent: Optional[QWidget] = None, channel_url: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("⚠️ Lưu ý: Kênh TikTok / Douyin cần Cookie")
        self.setMinimumWidth(520)
        self.setModal(True)
        self.action_result = self.ACTION_CANCEL
        self.channel_url = channel_url
        self._build_ui()

    def _build_ui(self) -> None:
        c = COLORS
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c['bg_primary']};
                color: {c['text_primary']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(16)

        # Header
        hdr = QHBoxLayout()
        hdr.setSpacing(12)

        icon_lbl = QLabel("⚠️")
        icon_lbl.setStyleSheet("font-size: 32px;")
        hdr.addWidget(icon_lbl)

        vbox = QVBoxLayout()
        vbox.setSpacing(4)
        t_lbl = QLabel("Kênh TikTok / Douyin yêu cầu Cookie")
        t_lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {c['accent_orange']};")

        vbox.addWidget(t_lbl)
        hdr.addLayout(vbox, 1)
        layout.addLayout(hdr)

        # Content card
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {c['bg_card']};
                border: 1px solid rgba(245, 158, 11, 0.3);
                border-radius: 8px;
            }}
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(10)

        desc = QLabel(
            "TikTok và Douyin hiện đang chặn các yêu cầu quét video tự động nếu không có phiên đăng nhập (Cookie).\n\n"
            "• Nếu quét mà <b>chưa nạp Cookie</b>, có thể sẽ bị báo lỗi: <i>'Không thể truy cập kênh'</i>.\n"
            "• Bạn nên nạp file Cookie (.txt) xuất từ trình duyệt để đảm bảo quét thành công 100%!"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"font-size: 12px; color: {c['text_primary']}; line-height: 1.5;")
        cl.addWidget(desc)
        layout.addWidget(card)

        # Buttons
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)

        # Nút nạp cookie ngay (Primary)
        btn_load = QPushButton("🍪  Nạp file Cookie (.txt) ngay (Khuyên dùng)")
        btn_load.setFixedHeight(38)
        btn_load.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['accent_cyan']};
                color: #ffffff;
                font-weight: 700;
                font-size: 13px;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
            }}
            QPushButton:hover {{ background-color: #22d3ee; }}
        """)
        btn_load.clicked.connect(self._choose_load)
        btn_layout.addWidget(btn_load)

        # Nút xem hướng dẫn
        btn_guide = QPushButton("📖  Xem hướng dẫn lấy Cookie (Chỉ 1 phút)")
        btn_guide.setFixedHeight(34)
        btn_guide.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['btn_secondary_bg']};
                color: {c['text_primary']};
                font-weight: 600;
                font-size: 12px;
                border: 1px solid {c['border']};
                border-radius: 6px;
                padding: 0 16px;
            }}
            QPushButton:hover {{
                background-color: {c['btn_secondary_hover']};
            }}
        """)
        btn_guide.clicked.connect(self._choose_guide)
        btn_layout.addWidget(btn_guide)

        # Hàng nút phụ
        row_sub = QHBoxLayout()
        row_sub.setSpacing(8)

        btn_continue = QPushButton("Thử quét không Cookie")
        btn_continue.setFixedHeight(32)
        btn_continue.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {c['text_muted']};
                font-size: 11px;
                border: none;
                text-decoration: underline;
            }}
            QPushButton:hover {{ color: {c['text_secondary']}; }}
        """)
        btn_continue.clicked.connect(self._choose_continue)
        row_sub.addWidget(btn_continue)

        row_sub.addStretch()

        btn_cancel = QPushButton("Hủy bỏ")
        btn_cancel.setFixedHeight(32)
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {c['text_muted']};
                font-size: 12px;
                border: 1px solid {c['border']};
                border-radius: 5px;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                background-color: {c['btn_secondary_bg']};
                color: {c['text_primary']};
            }}
        """)
        btn_cancel.clicked.connect(self._choose_cancel)
        row_sub.addWidget(btn_cancel)

        btn_layout.addLayout(row_sub)
        layout.addLayout(btn_layout)

    def _choose_load(self) -> None:
        self.action_result = self.ACTION_LOAD_COOKIE
        self.accept()

    def _choose_guide(self) -> None:
        self.action_result = self.ACTION_SHOW_GUIDE
        self.accept()

    def _choose_continue(self) -> None:
        self.action_result = self.ACTION_CONTINUE_WITHOUT
        self.accept()

    def _choose_cancel(self) -> None:
        self.action_result = self.ACTION_CANCEL
        self.reject()


class CookieFailedDialog(QDialog):
    """
    Hộp thoại hiển thị khi quét kênh thất bại do thiếu Cookie hoặc bị chặn.
    Cung cấp giải thích nguyên nhân và nút nạp Cookie để thử lại ngay.
    """

    ACTION_CLOSE = 0
    ACTION_LOAD_COOKIE = 1
    ACTION_SHOW_GUIDE = 2

    def __init__(self, error_message: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("🛡️ Quét kênh bị chặn: Cần Cookie xác thực")
        self.setMinimumWidth(540)
        self.setModal(True)
        self.action_result = self.ACTION_CLOSE
        self.error_message = error_message
        self._build_ui()

    def _build_ui(self) -> None:
        c = COLORS
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c['bg_primary']};
                color: {c['text_primary']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(16)

        # Header
        hdr = QHBoxLayout()
        hdr.setSpacing(12)

        icon_lbl = QLabel("🛡️")
        icon_lbl.setStyleSheet("font-size: 32px;")
        hdr.addWidget(icon_lbl)

        vbox = QVBoxLayout()
        vbox.setSpacing(4)
        t_lbl = QLabel("TikTok / Douyin chặn quét danh sách video")
        t_lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {c['accent_red']};")
        s_lbl = QLabel("Nền tảng phát hiện công cụ tự động và yêu cầu phiên đăng nhập.")
        s_lbl.setStyleSheet(f"font-size: 12px; color: {c['text_secondary']};")
        vbox.addWidget(t_lbl)
        vbox.addWidget(s_lbl)
        hdr.addLayout(vbox, 1)
        layout.addLayout(hdr)

        # Card nội dung
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {c['bg_card']};
                border: 1px solid rgba(239, 68, 68, 0.3);
                border-radius: 8px;
            }}
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(10)

        txt = QLabel(
            "<b>Tại sao bị lỗi này?</b><br>"
            "TikTok và Douyin áp dụng tường lửa bảo mật (WAF/Cloudflare) để chặn bot quét toàn bộ kênh mà không có phiên đăng nhập.<br><br>"
            "<b>👉 Cách khắc phục:</b><br>"
            "Bạn chỉ cần nạp file <b>cookies.txt</b> (xuất từ trình duyệt Chrome/Edge của bạn chỉ mất 1 phút). "
            "Phần mềm sẽ dùng phiên duyệt web của bạn và quét toàn bộ video bình thường!"
        )
        txt.setWordWrap(True)
        txt.setStyleSheet(f"font-size: 12px; color: {c['text_primary']}; line-height: 1.5;")
        cl.addWidget(txt)
        layout.addWidget(card)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        btn_load = QPushButton("🍪 Nạp file Cookie (.txt) ngay...")
        btn_load.setFixedHeight(44)
        btn_load.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['btn_green_bg']};
                color: #ffffff;
                font-weight: 700;
                font-size: 13px;
                border: none;
                border-radius: 8px;
                padding: 6px 20px;
            }}
            QPushButton:hover {{ background-color: {c['btn_green_hover']}; }}
        """)
        btn_load.clicked.connect(self._choose_load)
        btn_layout.addWidget(btn_load)

        btn_guide = QPushButton("📖 Xem hướng dẫn")
        btn_guide.setFixedHeight(44)
        btn_guide.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['btn_secondary_bg']};
                color: {c['text_primary']};
                font-weight: 600;
                font-size: 12px;
                border: 1px solid {c['border']};
                border-radius: 8px;
                padding: 6px 18px;
            }}
            QPushButton:hover {{
                background-color: {c['btn_secondary_hover']};
            }}
        """)
        btn_guide.clicked.connect(self._choose_guide)
        btn_layout.addWidget(btn_guide)

        btn_close = QPushButton("Đóng")
        btn_close.setFixedHeight(44)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {c['text_muted']};
                font-size: 12px;
                font-weight: 500;
                border: 1px solid {c['border']};
                border-radius: 8px;
                padding: 6px 18px;
            }}
            QPushButton:hover {{
                background-color: {c['btn_secondary_bg']};
                color: {c['text_primary']};
            }}
        """)
        btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

    def _choose_load(self) -> None:
        self.action_result = self.ACTION_LOAD_COOKIE
        self.accept()

    def _choose_guide(self) -> None:
        self.action_result = self.ACTION_SHOW_GUIDE
        self.accept()
