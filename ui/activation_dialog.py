"""
ui/activation_dialog.py — OmniGrab License Activation Dialog

Hộp thoại kích hoạt bản quyền với giao diện Dark Theme hiện đại:
  - Hiển thị Mã máy tính (Machine ID) + nút sao chép nhanh.
  - Bảng giá gói cước & Thông tin tài khoản ngân hàng chuyển khoản.
  - Ô dán License Key (Base64 RSA 2048-bit) + nút kích hoạt tức thì.
  - Bố cục 2 cột tối ưu (chiều rộng thoáng, chiều cao vừa vặn không bị tràn màn hình).
"""

from __future__ import annotations

import os
from typing import Callable, Optional

# pyrefly: ignore [missing-import]
from PyQt6.QtCore import Qt, QTimer
# pyrefly: ignore [missing-import]
from PyQt6.QtGui import QClipboard, QCursor, QFont, QPixmap
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
from core.security import get_resource_path
from ui.styles import COLORS


# ==========================================================================
# QR ZOOM DIALOG & CLICKABLE LABEL
# ==========================================================================

class QRZoomDialog(QDialog):
    """Cửa sổ phóng to mã QR thanh toán để quét dễ dàng từ điện thoại."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        qr_path: str = "",
        machine_id: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Mã QR Thanh Toán — OmniGrab PRO")
        self.setFixedSize(330, 470)
        self.setModal(True)
        self.setWindowFlags(
            self.windowFlags()
            & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        c = COLORS
        self.setStyleSheet(f"""
            QDialog {{ background-color: {c['bg_primary']}; }}
            QLabel {{ color: {c['text_primary']}; }}
            QPushButton {{
                background-color: {c['btn_secondary_bg']};
                color: {c['text_primary']};
                border: 1px solid {c['btn_outline_border']};
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {c['btn_secondary_hover']};
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        title = QLabel("📱 Quét mã chuyển khoản VietQR")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {c['accent_blue']};")
        lay.addWidget(title)

        sub = QLabel("Mở app Ngân hàng để quét mã & tự động điền thông tin")
        sub.setWordWrap(True)
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"font-size: 11px; color: {c['text_muted']};")
        lay.addWidget(sub)

        # Khung viền trắng cho mã QR
        frame = QFrame()
        frame.setStyleSheet("""
            background-color: #ffffff;
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.2);
        """)
        flay = QVBoxLayout(frame)
        flay.setContentsMargins(6, 6, 6, 6)
        lbl_img = QLabel()
        lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if qr_path and os.path.isfile(qr_path):
            pix = QPixmap(qr_path)
            lbl_img.setPixmap(
                pix.scaled(
                    200, 268,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        flay.addWidget(lbl_img)
        lay.addWidget(frame, alignment=Qt.AlignmentFlag.AlignCenter)

        # Cú pháp chuyển khoản gợi ý
        info_lbl = QLabel(
            f"Cú pháp: <b style='color:{c['accent_orange']}'>OMNIGRAB {machine_id} [SĐT]</b>"
        )
        info_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_lbl.setStyleSheet("font-size: 11px;")
        lay.addWidget(info_lbl)

        btn_close = QPushButton("Đóng")
        btn_close.setFixedHeight(32)
        btn_close.clicked.connect(self.accept)
        lay.addWidget(btn_close)


class ClickableQRLabel(QLabel):
    """Label hiển thị QR có hiệu ứng hover pointer và click để phóng to."""

    def __init__(
        self,
        qr_path: str = "",
        machine_id: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._qr_path = qr_path
        self._machine_id = machine_id
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setToolTip("🔍 Bấm vào ảnh để phóng to mã QR")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            dlg = QRZoomDialog(self.window(), self._qr_path, self._machine_id)
            dlg.exec()
        super().mousePressEvent(event)


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
        self.resize(830, 560)
        self.setMinimumWidth(780)
        self.setMinimumHeight(520)
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
        bl.setSpacing(8)

        lbl_bank_head = QLabel("🏦  Thông tin chuyển khoản & Quét mã QR:")
        lbl_bank_head.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {c['accent_orange']};"
        )
        bl.addWidget(lbl_bank_head)

        # Hàng trên: Thông tin ngân hàng (Trái) + Mã QR (Phải)
        top_bank_layout = QHBoxLayout()
        top_bank_layout.setSpacing(12)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(5)

        # Ngân hàng
        r_bank = QHBoxLayout()
        r_bank.setSpacing(4)
        lbl_bk = QLabel("Ngân hàng:")
        lbl_bk.setFixedWidth(80)
        lbl_bk.setStyleSheet(f"color: {c['text_muted']}; font-size: 11px;")
        lbl_bv = QLabel("MB Bank")
        lbl_bv.setStyleSheet(f"color: {c['text_primary']}; font-size: 12px; font-weight: 600;")
        r_bank.addWidget(lbl_bk)
        r_bank.addWidget(lbl_bv)
        r_bank.addStretch()
        info_layout.addLayout(r_bank)

        # Số tài khoản + Nút sao chép STK
        r_stk = QHBoxLayout()
        r_stk.setSpacing(6)
        lbl_sk = QLabel("Số tài khoản:")
        lbl_sk.setFixedWidth(80)
        lbl_sk.setStyleSheet(f"color: {c['text_muted']}; font-size: 11px;")
        lbl_sv = QLabel("9704 2220 7284 8450")
        lbl_sv.setStyleSheet(f"color: {c['accent_green']}; font-size: 12px; font-weight: 700;")
        btn_copy_stk = QPushButton("Sao chép")
        btn_copy_stk.setFixedHeight(20)
        btn_copy_stk.setToolTip("Sao chép số tài khoản MB Bank")
        btn_copy_stk.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['bg_input']};
                color: {c['text_secondary']};
                border: 1px solid {c['bg_input_border']};
                border-radius: 4px;
                padding: 0 6px;
                font-size: 10px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                color: {c['accent_green']};
                border-color: {c['accent_green']};
            }}
        """)
        btn_copy_stk.clicked.connect(
            lambda: self._on_copy_stk("9704222072848450", btn_copy_stk)
        )
        r_stk.addWidget(lbl_sk)
        r_stk.addWidget(lbl_sv)
        r_stk.addWidget(btn_copy_stk)
        r_stk.addStretch()
        info_layout.addLayout(r_stk)

        # Chủ tài khoản
        r_ctk = QHBoxLayout()
        r_ctk.setSpacing(4)
        lbl_ck = QLabel("Chủ tài khoản:")
        lbl_ck.setFixedWidth(80)
        lbl_ck.setStyleSheet(f"color: {c['text_muted']}; font-size: 11px;")
        lbl_cv = QLabel("PHẠM TUẤN ĐẠT")
        lbl_cv.setStyleSheet(f"color: {c['text_primary']}; font-size: 12px; font-weight: 600;")
        r_ctk.addWidget(lbl_ck)
        r_ctk.addWidget(lbl_cv)
        r_ctk.addStretch()
        info_layout.addLayout(r_ctk)

        # Gợi ý
        tip_lbl = QLabel("💡 Quét mã QR để tự động nhận STK & Chủ TK.")
        tip_lbl.setWordWrap(True)
        tip_lbl.setStyleSheet(f"color: {c['accent_cyan']}; font-size: 10px; font-style: italic;")
        info_layout.addWidget(tip_lbl)
        info_layout.addStretch()

        top_bank_layout.addLayout(info_layout, 1)

        # Mã QR bên phải
        qr_path = get_resource_path("assets/qr/ma-thanh-toan.png")
        if os.path.isfile(qr_path):
            qr_frame = QFrame()
            qr_frame.setObjectName("qr_box")
            qr_frame.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            qr_frame.setStyleSheet(f"""
                QFrame#qr_box {{
                    background-color: #ffffff;
                    border: 1px solid rgba(255, 255, 255, 0.3);
                    border-radius: 8px;
                }}
                QFrame#qr_box:hover {{
                    border: 1px solid {c['accent_blue']};
                }}
            """)
            qr_vbox = QVBoxLayout(qr_frame)
            qr_vbox.setContentsMargins(4, 4, 4, 4)
            qr_vbox.setSpacing(2)

            qr_label = ClickableQRLabel(qr_path, self._machine_id)
            pix = QPixmap(qr_path)
            scaled_pix = pix.scaled(
                100, 134,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            qr_label.setPixmap(scaled_pix)
            qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            qr_vbox.addWidget(qr_label)

            lbl_zoom_hint = QLabel("🔍 Bấm để phóng to")
            lbl_zoom_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_zoom_hint.setStyleSheet("font-size: 9px; color: #475569; font-weight: 600;")
            qr_vbox.addWidget(lbl_zoom_hint)

            top_bank_layout.addWidget(qr_frame)

        bl.addLayout(top_bank_layout)

        # Cú pháp CK ở hàng dưới full width
        cu_phap_row = QHBoxLayout()
        cu_phap_row.setSpacing(6)
        lbl_cu = QLabel("Cú pháp CK:")
        lbl_cu.setFixedWidth(80)
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
        btn_copy_ck = QPushButton("📋 Sao chép")
        btn_copy_ck.setFixedHeight(26)
        btn_copy_ck.setToolTip("Sao chép cú pháp chuyển khoản")
        btn_copy_ck.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['bg_input']};
                color: {c['accent_orange']};
                border: 1px solid {c['accent_orange']};
                border-radius: 4px;
                padding: 0 8px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {c['accent_orange']};
                color: #ffffff;
            }}
        """)
        btn_copy_ck.clicked.connect(
            lambda: self._on_copy_ck(self._cu_phap_edit.text(), btn_copy_ck)
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

    def _on_copy_stk(self, stk: str, btn: QPushButton) -> None:
        """Sao chép số tài khoản MB Bank vào clipboard."""
        self._copy_text(stk, "số tài khoản")
        btn.setText("✅ Đã chép!")
        QTimer.singleShot(2000, lambda: btn.setText("Sao chép"))

    def _on_copy_ck(self, text: str, btn: QPushButton) -> None:
        """Sao chép cú pháp chuyển khoản vào clipboard."""
        self._copy_text(text, "cú pháp chuyển khoản")
        btn.setText("✅ Đã chép!")
        QTimer.singleShot(2000, lambda: btn.setText("📋 Sao chép"))

    def _copy_text(self, text: str, label: str = "") -> None:
        cb = QApplication.clipboard()
        if cb:
            cb.setText(text, QClipboard.Mode.Clipboard)

    def _on_contact_admin(self) -> None:
        QMessageBox.information(
            self,
            "Liên hệ Admin",
            "💬 Liên hệ Admin để nhận License Key kích hoạt:\n\n"
            "  • Zalo / Hotline : 0342374729\n"
            "  • Telegram       : @pamtuandat\n"
            "  • Email          : phamtuandat.me@gmail.com\n\n"
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
