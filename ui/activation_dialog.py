"""
ui/activation_dialog.py — OmniGrab License Activation Dialog

Hộp thoại kích hoạt bản quyền với giao diện Dark Theme hiện đại:
  - Hiển thị Mã máy tính (Machine ID) + nút sao chép nhanh.
  - Bảng giá gói cước & Thông tin tài khoản ngân hàng chuyển khoản.
  - Ô dán License Key (Base64 RSA 2048-bit) + nút kích hoạt tức thì.
  - Bố cục 2 cột tối ưu (chiều rộng thoáng, chiều cao vừa vặn không bị tràn màn hình).
"""

from __future__ import annotations

from typing import Callable, Optional

# pyrefly: ignore [missing-import]
from PyQt6.QtCore import Qt, QTimer
# pyrefly: ignore [missing-import]
from PyQt6.QtGui import QClipboard, QFont
# pyrefly: ignore [missing-import]
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.license_manager import LicenseManager
from ui.styles import COLORS


# ==========================================================================
# ACTIVATION DIALOG
# ==========================================================================

class ActivationDialog(QDialog):
    """
    Cửa sổ kích hoạt bản quyền OmniGrab PRO.

    Khi kích hoạt thành công, gọi on_activated_callback để MainWindow
    cập nhật giao diện sang trạng thái PRO.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        on_activated_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent)
        self._lm = LicenseManager()
        self._on_activated = on_activated_callback
        self._machine_id = self._lm.get_machine_id()

        self.setWindowTitle("Kích hoạt Bản quyền OmniGrab PRO")
        self.resize(790, 520)
        self.setMinimumWidth(750)
        self.setMinimumHeight(480)
        self.setModal(True)
        self.setWindowFlags(
            self.windowFlags()
            & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        self._build_ui()

    # -----------------------------------------------------------------------
    # BUILD UI
    # -----------------------------------------------------------------------

    def _build_ui(self) -> None:
        c = COLORS
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c['bg_primary']};
            }}
            QLabel {{
                color: {c['text_primary']};
                background: transparent;
            }}
            QLineEdit, QTextEdit {{
                background-color: {c['bg_input']};
                color: {c['text_primary']};
                border: 1px solid {c['bg_input_border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                selection-background-color: {c['accent_blue']};
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border-color: {c['border_focus']};
            }}
            QPushButton {{
                background-color: {c['btn_secondary_bg']};
                color: {c['text_primary']};
                border: 1px solid {c['btn_outline_border']};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {c['btn_secondary_hover']};
                border-color: {c['text_secondary']};
            }}
            QPushButton:pressed {{
                background-color: {c['bg_input']};
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 16, 22, 16)
        root.setSpacing(12)

        # ── Header ──
        root.addWidget(self._build_header())
        root.addWidget(self._make_sep())

        # ── Thân chính: Bố cục 2 Cột ──
        body = QHBoxLayout()
        body.setSpacing(18)

        # Cột Trái: Mã máy + Bảng giá + Thông tin chuyển khoản
        col_left = self._build_left_column()
        body.addWidget(col_left, 55)

        # Cột Phải: Ô dán Key + Kích hoạt + Nút Đóng
        col_right = self._build_right_column()
        body.addWidget(col_right, 45)

        root.addLayout(body, 1)

    # -----------------------------------------------------------------------
    # SECTION: Header
    # -----------------------------------------------------------------------

    def _build_header(self) -> QWidget:
        c = COLORS
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)

        top_row = QHBoxLayout()
        lbl_title = QLabel("👑  Kích hoạt Bản quyền OmniGrab PRO")
        lbl_title.setStyleSheet(
            f"font-size: 17px; font-weight: 700; color: {c['accent_blue']};"
        )
        top_row.addWidget(lbl_title)
        top_row.addStretch()

        badge_offline = QLabel("🛡️ Xác thực RSA 2048-bit (Offline 100%)")
        badge_offline.setStyleSheet(f"""
            background-color: rgba(6, 182, 212, 0.15);
            color: {c['accent_cyan']};
            border: 1px solid rgba(6, 182, 212, 0.4);
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            padding: 2px 8px;
        """)
        top_row.addWidget(badge_offline)
        lay.addLayout(top_row)

        lbl_sub = QLabel(
            "Phần mềm tải video đa kênh & lồng tiếng AI cao cấp — Khóa theo mã phần cứng thiết bị."
        )
        lbl_sub.setStyleSheet(f"font-size: 12px; color: {c['text_muted']};")
        lay.addWidget(lbl_sub)
        return w

    # -----------------------------------------------------------------------
    # CỘT TRÁI: Mã máy + Bảng giá + Ngân hàng
    # -----------------------------------------------------------------------

    def _build_left_column(self) -> QWidget:
        c = COLORS
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        # 1. Mã thiết bị (Machine ID)
        lbl_mid = QLabel("💻  Mã thiết bị của bạn (Machine ID):")
        lbl_mid.setStyleSheet(
            f"font-size: 12px; font-weight: 700; color: {c['text_primary']};"
        )
        lay.addWidget(lbl_mid)

        mid_row = QHBoxLayout()
        mid_row.setSpacing(8)

        self._mid_edit = QLineEdit(self._machine_id)
        self._mid_edit.setReadOnly(True)
        self._mid_edit.setFixedHeight(34)
        self._mid_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {c['bg_secondary']};
                color: {c['accent_cyan']};
                border: 1px solid {c['accent_blue']};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 13px;
                font-weight: 700;
                letter-spacing: 1.5px;
            }}
        """)
        mid_row.addWidget(self._mid_edit, 1)

        self._btn_copy_mid = QPushButton("📋 Sao chép")
        self._btn_copy_mid.setFixedHeight(34)
        self._btn_copy_mid.setFixedWidth(100)
        self._btn_copy_mid.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['bg_secondary']};
                color: {c['accent_cyan']};
                border: 1px solid {c['accent_blue']};
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
                padding: 0 8px;
            }}
            QPushButton:hover {{
                background-color: {c['accent_blue']};
                color: #ffffff;
            }}
        """)
        self._btn_copy_mid.clicked.connect(self._on_copy_mid)
        mid_row.addWidget(self._btn_copy_mid)
        lay.addLayout(mid_row)

        hint = QLabel("ℹ️ Gửi mã này cho Admin kèm nội dung CK để nhận Key.")
        hint.setStyleSheet(f"font-size: 11px; color: {c['text_muted']};")
        lay.addWidget(hint)

        # 2. Bảng giá
        lbl_price = QLabel("💰  Bảng giá đăng ký bản quyền PRO:")
        lbl_price.setStyleSheet(
            f"font-size: 12px; font-weight: 700; color: {c['text_primary']}; margin-top: 2px;"
        )
        lay.addWidget(lbl_price)

        price_row = QHBoxLayout()
        price_row.setSpacing(8)

        packages = [
            ("1 Tháng",  "99.000đ",  c['accent_blue'],  False),
            ("3 Tháng", "249.000đ", c['accent_green'], True),
            ("1 Năm",   "699.000đ", c['accent_purple'], False),
        ]
        for name, price, color, recommended in packages:
            price_row.addWidget(self._make_price_card(name, price, color, recommended))
        lay.addLayout(price_row)

        # 3. Thông tin chuyển khoản
        bank_box = self._build_bank_box()
        lay.addWidget(bank_box)

        lay.addStretch()
        return w

    def _make_price_card(
        self, name: str, price: str, accent: str, recommended: bool
    ) -> QWidget:
        c = COLORS
        card = QFrame()
        card.setObjectName("price_card")
        border_color = accent if recommended else c['border']
        card.setStyleSheet(f"""
            QFrame#price_card {{
                background-color: {c['bg_card']};
                border: {'2' if recommended else '1'}px solid {border_color};
                border-radius: 8px;
            }}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(3)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if recommended:
            badge = QLabel("⭐ Phổ biến")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(f"""
                background-color: {accent};
                color: #ffffff;
                border-radius: 3px;
                font-size: 9px;
                font-weight: 700;
                padding: 1px 5px;
            """)
            lay.addWidget(badge)

        lbl_name = QLabel(name)
        lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_name.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {c['text_secondary']};"
        )
        lay.addWidget(lbl_name)

        lbl_price = QLabel(price)
        lbl_price.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_price.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {accent};"
        )
        lay.addWidget(lbl_price)
        return card

    def _build_bank_box(self) -> QWidget:
        c = COLORS
        bank_card = QFrame()
        bank_card.setObjectName("bank_card")
        bank_card.setStyleSheet(f"""
            QFrame#bank_card {{
                background-color: {c['bg_secondary']};
                border: 1px solid {c['border']};
                border-radius: 8px;
            }}
        """)
        bl = QVBoxLayout(bank_card)
        bl.setContentsMargins(12, 10, 12, 10)
        bl.setSpacing(5)

        lbl_bank_head = QLabel("🏦  Thông tin chuyển khoản:")
        lbl_bank_head.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {c['accent_orange']};"
        )
        bl.addWidget(lbl_bank_head)

        bank_info = [
            ("Ngân hàng",     "Vietcombank (VCB)"),
            ("Số tài khoản",  "1234 5678 90"),
            ("Chủ tài khoản", "NGUYEN VAN A"),
        ]
        for label, value in bank_info:
            row = QHBoxLayout()
            row.setSpacing(4)
            lbl_k = QLabel(f"{label}:")
            lbl_k.setFixedWidth(100)
            lbl_k.setStyleSheet(f"color: {c['text_muted']}; font-size: 11px;")
            lbl_v = QLabel(value)
            lbl_v.setStyleSheet(
                f"color: {c['text_primary']}; font-size: 12px; font-weight: 600;"
            )
            row.addWidget(lbl_k)
            row.addWidget(lbl_v)
            row.addStretch()
            bl.addLayout(row)

        # Cú pháp CK
        cu_phap_row = QHBoxLayout()
        cu_phap_row.setSpacing(6)
        lbl_cu = QLabel("Cú pháp CK:")
        lbl_cu.setFixedWidth(100)
        lbl_cu.setStyleSheet(f"color: {c['text_muted']}; font-size: 11px;")

        self._cu_phap_edit = QLineEdit(
            f"OMNIGRAB {self._machine_id} [SĐT]"
        )
        self._cu_phap_edit.setReadOnly(True)
        self._cu_phap_edit.setFixedHeight(26)
        self._cu_phap_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {c['bg_input']};
                color: {c['accent_orange']};
                border: 1px dashed {c['accent_orange']};
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
                font-weight: 600;
            }}
        """)
        btn_copy_ck = QPushButton("📋")
        btn_copy_ck.setFixedSize(28, 26)
        btn_copy_ck.setToolTip("Sao chép cú pháp chuyển khoản")
        btn_copy_ck.clicked.connect(
            lambda: self._copy_text(self._cu_phap_edit.text(), "cú pháp chuyển khoản")
        )

        cu_phap_row.addWidget(lbl_cu)
        cu_phap_row.addWidget(self._cu_phap_edit, 1)
        cu_phap_row.addWidget(btn_copy_ck)
        bl.addLayout(cu_phap_row)

        return bank_card

    # -----------------------------------------------------------------------
    # CỘT PHẢI: Nhập Key + Kích hoạt + Nút Đóng
    # -----------------------------------------------------------------------

    def _build_right_column(self) -> QWidget:
        c = COLORS
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        lbl_key = QLabel("🔑  Nhập mã kích hoạt (License Key):")
        lbl_key.setStyleSheet(
            f"font-size: 12px; font-weight: 700; color: {c['text_primary']};"
        )
        lay.addWidget(lbl_key)

        self._key_input = QTextEdit()
        self._key_input.setObjectName("key_input")
        self._key_input.setPlaceholderText(
            "Dán mã kích hoạt (License Key) do Admin cấp vào đây...\n\n"
            "Mã là chuỗi Base64 dài, ví dụ:\n"
            "eyJwYXlsb2FkIjogey...},ICJzaWciOiAi...\"}"
        )
        self._key_input.setStyleSheet(f"""
            QTextEdit {{
                background-color: {c['bg_input']};
                color: {c['accent_green']};
                border: 1px solid {c['bg_input_border']};
                border-radius: 8px;
                padding: 8px 10px;
                font-size: 12px;
                font-family: "Cascadia Code", "Consolas", monospace;
                line-height: 1.5;
            }}
            QTextEdit:focus {{
                border-color: {c['accent_green']};
            }}
        """)
        lay.addWidget(self._key_input, 1)

        # Thông báo trạng thái/lỗi
        self._lbl_result = QLabel("")
        self._lbl_result.setWordWrap(True)
        self._lbl_result.setStyleSheet("font-size: 11px;")
        self._lbl_result.setVisible(False)
        lay.addWidget(self._lbl_result)

        # Nút Kích hoạt lớn
        self._btn_activate = QPushButton("🔑  KÍCH HOẠT BẢN QUYỀN")
        self._btn_activate.setFixedHeight(42)
        self._btn_activate.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #16a34a, stop:1 #22c55e
                );
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #22c55e, stop:1 #4ade80
                );
            }}
            QPushButton:pressed {{
                background-color: #15803d;
            }}
            QPushButton:disabled {{
                background: {c['border']};
                color: {c['text_placeholder']};
            }}
        """)
        self._btn_activate.clicked.connect(self._on_activate)
        lay.addWidget(self._btn_activate)

        # Hàng nút phụ: Hỗ trợ Admin + Đóng
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_contact = QPushButton("💬 Hỗ trợ Admin")
        btn_contact.setFixedHeight(34)
        btn_contact.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(59, 130, 246, 0.12);
                color: {c['accent_blue']};
                border: 1px solid rgba(59, 130, 246, 0.4);
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background-color: rgba(59, 130, 246, 0.25);
            }}
        """)
        btn_contact.clicked.connect(self._on_contact_admin)
        btn_row.addWidget(btn_contact, 1)

        btn_close = QPushButton("Đóng")
        btn_close.setFixedHeight(34)
        btn_close.clicked.connect(self.reject)
        btn_row.addWidget(btn_close)

        lay.addLayout(btn_row)
        return w

    # -----------------------------------------------------------------------
    # XỬ LÝ SỰ KIỆN
    # -----------------------------------------------------------------------

    def _on_copy_mid(self) -> None:
        """Sao chép Machine ID vào clipboard."""
        self._copy_text(self._machine_id, "mã máy tính")
        self._btn_copy_mid.setText("✅ Đã chép!")
        QTimer.singleShot(2000, lambda: self._btn_copy_mid.setText("📋 Sao chép"))

    def _copy_text(self, text: str, label: str = "") -> None:
        cb = QApplication.clipboard()
        if cb:
            cb.setText(text, QClipboard.Mode.Clipboard)

    def _on_contact_admin(self) -> None:
        QMessageBox.information(
            self,
            "Liên hệ Admin",
            "💬 Liên hệ Admin để nhận License Key kích hoạt:\n\n"
            "  • Zalo / Hotline : 09xx.xxx.xxx\n"
            "  • Telegram       : @omnigrab_support\n"
            "  • Email          : support@omnigrab.vn\n\n"
            "Vui lòng gửi kèm:\n"
            f"  1. Mã thiết bị: {self._machine_id}\n"
            "  2. Ảnh chụp màn hình giao dịch chuyển khoản\n\n"
            "Admin sẽ cấp License Key trong vòng 5–15 phút.",
        )

    def _on_activate(self) -> None:
        """Kích hoạt bản quyền: xác thực RSA và cập nhật giao diện chính."""
        key_text = self._key_input.toPlainText().strip()
        if not key_text:
            self._show_result(False, "⚠️ Vui lòng dán mã kích hoạt vào ô bên trên.")
            return

        self._btn_activate.setEnabled(False)
        self._btn_activate.setText("⏳  Đang xác thực...")

        success, message = self._lm.verify_and_save_key(key_text)

        self._btn_activate.setEnabled(True)
        self._btn_activate.setText("🔑  KÍCH HOẠT BẢN QUYỀN")

        if success:
            self._show_result(True, message)
            QMessageBox.information(self, "Kích hoạt thành công!", message)
            if self._on_activated:
                self._on_activated()
            QTimer.singleShot(300, self.accept)
        else:
            self._show_result(False, f"❌ {message}")

    def _show_result(self, success: bool, message: str) -> None:
        c = COLORS
        color = c["accent_green"] if success else c["accent_red"]
        self._lbl_result.setStyleSheet(
            f"font-size: 11px; color: {color}; font-weight: 600;"
        )
        self._lbl_result.setText(message)
        self._lbl_result.setVisible(True)

    # -----------------------------------------------------------------------
    # TIỆN ÍCH
    # -----------------------------------------------------------------------

    def _make_sep(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: {COLORS['border']}; max-height: 1px;")
        return sep
