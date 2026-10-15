"""
ui/youtube_upload_dialog.py — Hộp thoại Cài đặt Tự động Đăng & Hẹn giờ YouTube Shorts.
Sử dụng Playwright & Cookie (không cần Google Cloud / API Key).
Đồng bộ thiết kế Dark Theme với hệ thống OmniGrab.
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path
from typing import Optional

# pyrefly: ignore [missing-import]
from PyQt6.QtCore import QDate, QTime, Qt
from PyQt6.QtGui import QIcon, QPixmap
# pyrefly: ignore [missing-import]
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from core.youtube_uploader import parse_netscape_cookies
from ui.styles import COLORS


def _resolve_icon_path(rel_path: str) -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target = os.path.join(base, rel_path)
    return target if os.path.exists(target) else rel_path


class YouTubeUploadDialog(QDialog):
    """
    Popup cài đặt Tự động Đăng & Hẹn giờ YouTube Shorts (Playwright + Cookie).
    Mở qua Menu Công cụ ➔ Cài đặt Tự động Đăng & Hẹn giờ YouTube...
    """

    def __init__(
        self,
        auto_upload: bool = False,
        privacy: str = "public",
        cookies_path: str = "youtube_cookies.txt",
        schedule_enabled: bool = False,
        schedule_date: str = "",
        schedule_time: str = "",
        scheduled_datetime: Optional[datetime.datetime] = None,
        default_tags: str = "Shorts, AI, PhimHay, ReviewPhim",
        client_secrets_path: str = "",  # Tương thích ngược
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cài đặt Tự động Đăng & Hẹn giờ YouTube Shorts")
        yt_icon_p = _resolve_icon_path("assets/icon/youtube.png")
        if os.path.exists(yt_icon_p):
            self.setWindowIcon(QIcon(yt_icon_p))
        self.setMinimumWidth(620)
        self.setModal(True)

        self.result_auto_upload = auto_upload
        self.result_privacy = privacy
        self.result_cookies_path = cookies_path or "youtube_cookies.txt"
        self.result_schedule_enabled = schedule_enabled
        self.result_schedule_date = schedule_date
        self.result_schedule_time = schedule_time
        self.result_scheduled_datetime = scheduled_datetime
        self.result_default_tags = default_tags
        self.result_client_secrets_path = client_secrets_path

        # Nếu có scheduled_datetime cũ mà chưa có date/time chuỗi
        if scheduled_datetime and not self.result_schedule_date:
            self.result_schedule_date = scheduled_datetime.strftime("%d/%m/%Y")
            self.result_schedule_time = scheduled_datetime.strftime("%H:%M")

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
            QCheckBox, QRadioButton {{
                color: {c['text_primary']};
                font-size: 13px;
                spacing: 10px;
                background: transparent;
            }}
            QCheckBox:checked, QRadioButton:checked {{
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
            QRadioButton::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 9px;
                border: 2px solid #64748b;
                background-color: {c['bg_input']};
            }}
            QRadioButton::indicator:hover {{
                border-color: #ff4b4b;
            }}
            QRadioButton::indicator:checked {{
                border: 2px solid #ff4b4b;
                background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 #ff4b4b, stop:0.55 #ff4b4b, stop:0.56 {c['bg_input']}, stop:1 {c['bg_input']});
            }}
            QComboBox, QLineEdit, QDateEdit, QTimeEdit {{
                background-color: {c['bg_input']};
                color: {c['text_primary']};
                border: 1px solid {c['bg_input_border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QComboBox:focus, QLineEdit:focus, QDateEdit:focus, QTimeEdit:focus {{
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
        root.setSpacing(14)

        # ── 1. Tiêu đề ──
        h_box = QHBoxLayout()
        lbl_icon = QLabel()
        yt_icon_p = _resolve_icon_path("assets/icon/youtube.png")
        if os.path.exists(yt_icon_p):
            pix = QPixmap(yt_icon_p).scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl_icon.setPixmap(pix)
        else:
            lbl_icon.setText("▶")
            lbl_icon.setStyleSheet("color: #ff0000; font-size: 22px; font-weight: bold;")
        lbl_header = QLabel("Tự động Đăng & Hẹn giờ YouTube Shorts (Playwright / Cookie)")
        lbl_header.setStyleSheet("font-size: 16px; font-weight: 700; color: #ff4b4b;")
        h_box.addWidget(lbl_icon)
        h_box.addWidget(lbl_header)
        h_box.addStretch(1)
        root.addLayout(h_box)

        lbl_desc = QLabel(
            "Tự động đăng video lên YouTube Studio mà KHÔNG cần tạo Google Cloud hay API Key. "
            "Sử dụng file Cookie tài khoản YouTube để tự động hóa đăng và lên lịch hẹn giờ phát hành."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(f"font-size: 12px; color: {c['text_secondary']};")
        root.addWidget(lbl_desc)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {c['border']}; max-height: 1px;")
        root.addWidget(sep)

        # ── 2. Checkbox kích hoạt chính ──
        self._chk_enable = QCheckBox("Tự động đăng YouTube Shorts sau khi hoàn tất video")
        self._chk_enable.setChecked(self.result_auto_upload)
        self._chk_enable.setStyleSheet("font-size: 14px; font-weight: 600; color: #ffffff;")
        root.addWidget(self._chk_enable)

        # ── 3. Khung cài đặt chi tiết ──
        self._config_frame = QFrame()
        self._config_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border']};
                border-radius: 8px;
            }}
        """)
        f_layout = QVBoxLayout(self._config_frame)
        f_layout.setContentsMargins(16, 14, 16, 14)
        f_layout.setSpacing(12)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        # File Cookie youtube_cookies.txt
        grid.addWidget(QLabel("File Cookie YouTube (.txt):"), 0, 0)
        ck_box = QHBoxLayout()
        self._txt_cookie_path = QLineEdit()
        self._txt_cookie_path.setPlaceholderText("youtube_cookies.txt (Netscape format)")
        self._txt_cookie_path.setText(self.result_cookies_path or "youtube_cookies.txt")
        self._txt_cookie_path.textChanged.connect(lambda _: self._check_cookie_status())

        btn_browse_ck = QPushButton("📂 Chọn file...")
        btn_browse_ck.setStyleSheet(f"background-color: {c['btn_secondary_bg']}; color: {c['text_primary']};")
        btn_browse_ck.clicked.connect(self._on_browse_cookies)
        ck_box.addWidget(self._txt_cookie_path, 1)
        ck_box.addWidget(btn_browse_ck)
        ck_widget = QWidget()
        ck_widget.setLayout(ck_box)
        grid.addWidget(ck_widget, 0, 1)

        # Trạng thái Cookie & Nút kiểm tra
        grid.addWidget(QLabel("Trạng thái Cookie:"), 1, 0)
        auth_row = QHBoxLayout()
        self._lbl_auth_status = QLabel("Chưa kiểm tra")
        self._lbl_auth_status.setStyleSheet("font-weight: 600;")
        btn_test_auth = QPushButton("🔍 Kiểm tra Cookie")
        btn_test_auth.setStyleSheet(f"background-color: {c['btn_secondary_bg']}; color: {c['text_primary']};")
        btn_test_auth.clicked.connect(self._on_test_cookies)
        auth_row.addWidget(self._lbl_auth_status, 1)
        auth_row.addWidget(btn_test_auth)
        auth_widget = QWidget()
        auth_widget.setLayout(auth_row)
        grid.addWidget(auth_widget, 1, 1)

        # Thẻ Tags mặc định
        grid.addWidget(QLabel("Thẻ Tags mặc định:"), 2, 0)
        self._txt_tags = QLineEdit()
        self._txt_tags.setPlaceholderText("Cách nhau bởi dấu phẩy, ví dụ: Shorts, AI, Review")
        self._txt_tags.setText(self.result_default_tags)
        grid.addWidget(self._txt_tags, 2, 1)

        f_layout.addLayout(grid)

        # Phân cách hẹn giờ
        sched_sep = QFrame()
        sched_sep.setFrameShape(QFrame.Shape.HLine)
        sched_sep.setStyleSheet(f"background-color: {c['border']}; max-height: 1px;")
        f_layout.addWidget(sched_sep)

        # ── 4. Chế độ xuất bản: Đăng ngay vs Lên lịch hẹn giờ ──
        sched_box = QVBoxLayout()
        sched_box.setSpacing(10)

        lbl_sched_title = QLabel("🕒 Chế độ phát hành video:")
        lbl_sched_title.setStyleSheet("font-weight: 600; font-size: 13px; color: #ffffff;")
        sched_box.addWidget(lbl_sched_title)

        # Radio 1: Đăng ngay
        row_now = QHBoxLayout()
        self._radio_now = QRadioButton("Đăng ngay (Public)")
        self._cbo_privacy = QComboBox()
        self._cbo_privacy.addItem("Công khai (Public)", "public")
        self._cbo_privacy.addItem("Riêng tư (Private)", "private")
        self._cbo_privacy.addItem("Không công khai (Unlisted)", "unlisted")
        idx_p = self._cbo_privacy.findData(self.result_privacy)
        if idx_p >= 0:
            self._cbo_privacy.setCurrentIndex(idx_p)
        row_now.addWidget(self._radio_now)
        row_now.addWidget(self._cbo_privacy)
        row_now.addStretch(1)
        sched_box.addLayout(row_now)

        # Radio 2: Lên lịch hẹn giờ
        self._radio_schedule = QRadioButton("Lên lịch hẹn giờ (Schedule trên YouTube Studio)")
        self._btn_group_sched = QButtonGroup(self)
        self._btn_group_sched.addButton(self._radio_now)
        self._btn_group_sched.addButton(self._radio_schedule)

        if self.result_schedule_enabled:
            self._radio_schedule.setChecked(True)
        else:
            self._radio_now.setChecked(True)

        sched_box.addWidget(self._radio_schedule)

        # Khung chọn Ngày và Giờ riêng biệt
        dt_frame = QWidget()
        dt_row = QHBoxLayout(dt_frame)
        dt_row.setContentsMargins(28, 0, 0, 0)
        dt_row.setSpacing(12)

        lbl_date = QLabel("Ngày hẹn:")
        lbl_date.setStyleSheet(f"color: {c['text_secondary']};")
        self._date_edit = QDateEdit()
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("dd/MM/yyyy")
        self._date_edit.setMinimumDate(QDate.currentDate())

        lbl_time = QLabel("Giờ hẹn:")
        lbl_time.setStyleSheet(f"color: {c['text_secondary']};")
        self._time_edit = QTimeEdit()
        self._time_edit.setDisplayFormat("HH:mm")

        # Cài đặt giá trị ngày giờ ban đầu
        now_date = QDate.currentDate()
        now_time = QTime.currentTime()

        if self.result_schedule_date:
            try:
                # Thử parse dd/MM/yyyy hoặc yyyy-MM-dd
                parts = self.result_schedule_date.replace("-", "/").split("/")
                if len(parts) == 3:
                    if len(parts[0]) == 4:  # yyyy/MM/dd
                        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                    else:  # dd/MM/yyyy
                        d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                    self._date_edit.setDate(QDate(y, m, d))
            except Exception:
                self._date_edit.setDate(now_date)
        else:
            self._date_edit.setDate(now_date)

        if self.result_schedule_time:
            try:
                tp = self.result_schedule_time.split(":")
                self._time_edit.setTime(QTime(int(tp[0]), int(tp[1])))
            except Exception:
                self._time_edit.setTime(QTime(19, 0))
        else:
            # Mặc định hẹn lúc 19:00 hoặc 2 tiếng sau
            self._time_edit.setTime(QTime(19, 0))

        dt_row.addWidget(lbl_date)
        dt_row.addWidget(self._date_edit, 1)
        dt_row.addWidget(lbl_time)
        dt_row.addWidget(self._time_edit, 1)

        sched_box.addWidget(dt_frame)
        f_layout.addLayout(sched_box)
        root.addWidget(self._config_frame)

        # ── 5. Hướng dẫn lấy cookie ──
        lbl_guide = QLabel(
            "💡 Hướng dẫn lấy cookie: Đăng nhập YouTube trên Chrome/Edge ➔ Cài tiện ích 'Get cookies.txt LOCALLY' "
            "➔ Bấm Export để lưu file 'youtube_cookies.txt' vào thư mục OmniGrab."
        )
        lbl_guide.setStyleSheet(f"font-size: 11px; color: {c['text_muted']}; line-height: 1.4;")
        lbl_guide.setWordWrap(True)
        root.addWidget(lbl_guide)

        # Toggles
        self._chk_enable.toggled.connect(self._on_enable_toggled)
        self._radio_schedule.toggled.connect(self._on_schedule_toggled)
        self._on_enable_toggled(self._chk_enable.isChecked())
        self._on_schedule_toggled(self._radio_schedule.isChecked())
        self._check_cookie_status()

        # ── 6. Buttons Footer ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        btn_cancel = QPushButton("Hủy bỏ")
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['bg_card']};
                color: {c['text_secondary']};
                border: 1px solid {c['border']};
            }}
            QPushButton:hover {{
                background-color: {c['bg_secondary']};
                color: {c['text_primary']};
            }}
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("💾  Lưu cài đặt YouTube")
        btn_save.setStyleSheet("""
            QPushButton {{
                background-color: #ff0000;
                color: #ffffff;
                font-weight: 700;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #cc0000;
            }}
        """)
        btn_save.clicked.connect(self._on_save)

        btn_layout.addStretch(1)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        root.addLayout(btn_layout)

    def _on_enable_toggled(self, checked: bool) -> None:
        self._config_frame.setEnabled(checked)

    def _on_schedule_toggled(self, checked: bool) -> None:
        self._date_edit.setEnabled(checked)
        self._time_edit.setEnabled(checked)
        self._cbo_privacy.setEnabled(not checked)

    def _resolve_cookie_file(self) -> str:
        ck = self._txt_cookie_path.text().strip() or "youtube_cookies.txt"
        if not os.path.isabs(ck):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            ck = os.path.join(base_dir, ck)
        return ck

    def _check_cookie_status(self) -> None:
        c = COLORS
        ck_path = self._resolve_cookie_file()
        if os.path.exists(ck_path) and os.path.getsize(ck_path) > 20:
            cookies = parse_netscape_cookies(ck_path)
            if cookies:
                self._lbl_auth_status.setText(f"✅ Sẵn sàng ({len(cookies)} cookies)")
                self._lbl_auth_status.setStyleSheet(f"color: {c['accent_green']}; font-weight: 600;")
                return
        self._lbl_auth_status.setText("Chưa có cookie")
        self._lbl_auth_status.setStyleSheet(f"color: {c['accent_orange']}; font-weight: 600;")

    def _on_browse_cookies(self) -> None:
        f, _ = QFileDialog.getOpenFileName(
            self, "Chọn file Cookie YouTube (youtube_cookies.txt)", "",
            "Cookie files (*.txt *.json);;Tất cả file (*.*)"
        )
        if f:
            self._txt_cookie_path.setText(f)
            self._check_cookie_status()

    def _on_test_cookies(self) -> None:
        ck_path = self._resolve_cookie_file()
        if not os.path.exists(ck_path):
            QMessageBox.warning(
                self, "Chưa tìm thấy file Cookie",
                f"Không tìm thấy file: {ck_path}\n"
                "Vui lòng chọn file youtube_cookies.txt hợp lệ."
            )
            return

        cookies = parse_netscape_cookies(ck_path)
        if not cookies:
            QMessageBox.critical(
                self, "Cookie không hợp lệ",
                "File cookie trống hoặc không đúng định dạng Netscape / JSON.\n"
                "Vui lòng xuất lại cookie từ tiện ích 'Get cookies.txt LOCALLY'."
            )
            return

        # Kiểm tra xem có cookie xác thực của Google / YouTube không
        auth_cookie_names = {"LOGIN_INFO", "SID", "HSID", "SSID", "APISID", "SAPISID"}
        found_auth = [c["name"] for c in cookies if c.get("name") in auth_cookie_names]

        self._check_cookie_status()
        if found_auth:
            QMessageBox.information(
                self, "Cookie hợp lệ",
                f"🎉 File cookie YouTube hợp lệ!\n"
                f"- Tổng số cookie: {len(cookies)}\n"
                f"- Tìm thấy session login: {', '.join(found_auth)}\n\n"
                "Sẵn sàng đăng video tự động lên YouTube Studio!"
            )
        else:
            QMessageBox.information(
                self, "Đã đọc Cookie",
                f"Đã đọc được {len(cookies)} cookies từ file.\n"
                "Lưu ý: Hãy chắc chắn bạn đã đăng nhập YouTube trước khi xuất file cookie."
            )

    def _on_save(self) -> None:
        self.result_auto_upload = self._chk_enable.isChecked()
        self.result_cookies_path = self._txt_cookie_path.text().strip() or "youtube_cookies.txt"
        self.result_default_tags = self._txt_tags.text().strip()
        self.result_schedule_enabled = self._radio_schedule.isChecked()
        self.result_privacy = self._cbo_privacy.currentData() or "public"

        # Lấy ngày & giờ hẹn
        q_d = self._date_edit.date()
        q_t = self._time_edit.time()
        self.result_schedule_date = f"{q_d.day():02d}/{q_d.month():02d}/{q_d.year()}"
        self.result_schedule_time = f"{q_t.hour():02d}:{q_t.minute():02d}"

        # Tạo đối tượng datetime tương thích ngược
        try:
            self.result_scheduled_datetime = datetime.datetime(
                q_d.year(), q_d.month(), q_d.day(), q_t.hour(), q_t.minute()
            )
        except Exception:
            self.result_scheduled_datetime = None

        if self.result_auto_upload:
            ck = self._resolve_cookie_file()
            if not os.path.exists(ck):
                ret = QMessageBox.warning(
                    self, "Chưa có file Cookie",
                    f"Không tìm thấy file cookie '{ck}'.\n\n"
                    "Bạn có muốn tiếp tục lưu không? (Hệ thống cần file này để đăng video lên YouTube Studio).",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                if ret != QMessageBox.StandardButton.Yes:
                    return

        self.accept()
