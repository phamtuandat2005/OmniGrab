"""
ui/widgets.py - Các thành phần giao diện nâng cao theo chuẩn UI/UX Desktop:
- TableEmptyState: Trạng thái trống (Empty State) tinh tế cho QTableWidget khi chưa có dữ liệu.
- CollapsibleSection: Khung bộ lọc có thể thu gọn / mở rộng linh hoạt, tối ưu diện tích màn hình.
"""

from __future__ import annotations

from typing import Optional
from PyQt6.QtCore import QEvent, QObject, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ui.icons import get_svg_icon, get_svg_pixmap
from ui.styles import COLORS


# ══════════════════════════════════════════════════════════════════════
# 1. EMPTY STATE CHO BẢNG DỮ LIỆU (QTableWidget)
# ══════════════════════════════════════════════════════════════════════

class TableEmptyState(QWidget):
    """
    Widget hiển thị trạng thái trống cho QTableWidget khi không có hàng nào.
    Gắn trực tiếp vào viewport của bảng, tự căn giữa và tự ẩn/hiện theo rowCount.
    """

    def __init__(
        self,
        table: QTableWidget,
        title: str = "Chưa có dữ liệu",
        description: str = "Nhập liên kết ở trên để bắt đầu tải danh sách.",
        icon_name: str = "film",
        parent: Optional[QWidget] = None,
        subtitle: Optional[str] = None,
    ) -> None:
        super().__init__(parent or table.viewport())
        self._table = table
        self._icon_name = icon_name
        self._title_text = title
        self._desc_text = subtitle if subtitle is not None else description

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 30, 20, 30)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Icon SVG
        self._lbl_icon = QLabel()
        self._lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_icon()
        layout.addWidget(self._lbl_icon)

        # Tiêu đề chính
        self._lbl_title = QLabel(self._title_text)
        self._lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_title.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['text_secondary']};
                font-size: 14px;
                font-weight: 600;
                background: transparent;
            }}
        """)
        layout.addWidget(self._lbl_title)

        # Mô tả phụ (WCAG 4.5:1 text_muted)
        self._lbl_desc = QLabel(self._desc_text)
        self._lbl_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_desc.setWordWrap(True)
        self._lbl_desc.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['text_muted']};
                font-size: 12px;
                background: transparent;
                max-width: 420px;
            }}
        """)
        layout.addWidget(self._lbl_desc)

        # Lắng nghe sự kiện của viewport bảng để căn chỉnh vị trí
        self._table.viewport().installEventFilter(self)
        self._update_visibility()

    def _update_icon(self) -> None:
        pix = get_svg_pixmap(self._icon_name, color=COLORS["text_muted"], size=40)
        self._lbl_icon.setPixmap(pix)

    def set_content(self, title: str, description: str, icon_name: Optional[str] = None) -> None:
        """Cập nhật nội dung thông điệp empty state."""
        self._lbl_title.setText(title)
        self._lbl_desc.setText(description)
        if icon_name:
            self._icon_name = icon_name
            self._update_icon()
        self._update_visibility()

    def _update_visibility(self) -> None:
        """Ẩn/hiện dựa trên số hàng thực tế của bảng."""
        is_empty = (self._table.rowCount() == 0)
        self.setVisible(is_empty)
        if is_empty:
            vp_rect = self._table.viewport().rect()
            self.setGeometry(vp_rect)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched == self._table.viewport():
            if event.type() in (QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.Paint):
                self._update_visibility()
        return super().eventFilter(watched, event)


# ══════════════════════════════════════════════════════════════════════
# 2. KHUNG BỘ LỌC THU GỌN / MỞ RỘNG (CollapsibleSection)
# ══════════════════════════════════════════════════════════════════════

class CollapsibleSection(QFrame):
    """
    Khung chứa có thể gập/mở (Accordion/Collapsible) theo chuẩn UX hiện đại.
    Giúp giao diện gọn gàng, người dùng mở ra khi cần cấu hình bộ lọc chi tiết.
    """

    toggled = pyqtSignal(bool)  # Phát tín hiệu khi mở (True) hoặc gập (False)

    def __init__(
        self,
        title: str = "Bộ lọc nâng cao",
        icon_name: str = "filter",
        initially_expanded: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._is_expanded = initially_expanded
        self._title = title
        self._icon_name = icon_name

        c = COLORS
        self.setStyleSheet(f"""
            CollapsibleSection {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border']};
                border-radius: 8px;
            }}
        """)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Header bar bấm được để toggle ──
        self._header = QFrame()
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.setStyleSheet(f"""
            QFrame {{
                background-color: {c['bg_card']};
                border: none;
                border-radius: 8px;
                padding: 4px 10px;
            }}
            QFrame:hover {{
                background-color: {c['bg_card_hover']};
            }}
        """)

        h_layout = QHBoxLayout(self._header)
        h_layout.setContentsMargins(8, 6, 8, 6)
        h_layout.setSpacing(8)

        # Icon chính của mục
        self._lbl_header_icon = QLabel()
        self._lbl_header_icon.setPixmap(get_svg_pixmap(self._icon_name, color=c["text_secondary"], size=16))
        h_layout.addWidget(self._lbl_header_icon)

        # Tiêu đề
        self._lbl_title = QLabel(self._title)
        self._lbl_title.setStyleSheet(f"""
            QLabel {{
                color: {c['text_secondary']};
                font-size: 12.5px;
                font-weight: 600;
                background: transparent;
            }}
        """)
        h_layout.addWidget(self._lbl_title)

        # Badge trạng thái bộ lọc (ví dụ: "Đang lọc" hoặc "Mặc định")
        self._lbl_badge = QLabel("")
        self._lbl_badge.setStyleSheet(f"""
            QLabel {{
                color: {c['accent_orange']};
                background-color: rgba(245, 158, 11, 0.12);
                border: 1px solid rgba(245, 158, 11, 0.3);
                border-radius: 4px;
                padding: 1px 6px;
                font-size: 11px;
                font-weight: 500;
            }}
        """)
        self._lbl_badge.setVisible(False)
        h_layout.addWidget(self._lbl_badge)

        h_layout.addStretch(1)

        # Chevron icon (mũi tên chỉ xuống khi mở, chỉ sang phải khi đóng)
        self._lbl_chevron = QLabel()
        self._update_chevron()
        h_layout.addWidget(self._lbl_chevron)

        root_layout.addWidget(self._header)

        # ── Vùng nội dung (Container) ──
        self._content_widget = QWidget()
        self._content_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {c['bg_card']};
                border-top: 1px solid {c['border']};
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
            }}
        """)
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(12, 10, 12, 12)
        self._content_layout.setSpacing(8)

        self._content_widget.setVisible(self._is_expanded)
        root_layout.addWidget(self._content_widget)

        # Xử lý click header
        self._header.mousePressEvent = self._on_header_clicked

    @property
    def content_layout(self) -> QVBoxLayout:
        """Truy cập layout nội dung để chèn các widget bộ lọc vào."""
        return self._content_layout

    def is_expanded(self) -> bool:
        return self._is_expanded

    @property
    def is_collapsed(self) -> bool:
        return not self._is_expanded

    def set_expanded(self, expanded: bool) -> None:
        if self._is_expanded != expanded:
            self._is_expanded = expanded
            self._content_widget.setVisible(expanded)
            self._update_chevron()
            self.toggled.emit(expanded)

    def toggle(self) -> None:
        self.set_expanded(not self._is_expanded)

    def set_badge(self, text: str, is_active: bool = True) -> None:
        """Hiển thị badge báo có bao nhiêu điều kiện lọc đang bật."""
        if text and is_active:
            self._lbl_badge.setText(text)
            self._lbl_badge.setVisible(True)
        else:
            self._lbl_badge.setVisible(False)

    def _on_header_clicked(self, event) -> None:
        self.toggle()

    def _update_chevron(self) -> None:
        icon_name = "chevron-down" if self._is_expanded else "chevron-right"
        pix = get_svg_pixmap(icon_name, color=COLORS["text_muted"], size=14)
        self._lbl_chevron.setPixmap(pix)
