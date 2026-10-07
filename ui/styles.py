"""
ui/styles.py - Theme & CSS tùy biến cho giao diện Dark Mode hiện đại.

Bảng màu chính:
- Nền: Gradient tối #0b0e14 → #141921
- Accent: Xanh dương #3b82f6, Xanh lá #22c55e, Đỏ #ef4444
- Viền: #1e293b
- Chữ: #e2e8f0 (chính), #94a3b8 (phụ)
"""

from __future__ import annotations

# === Bảng màu ===
COLORS = {
    # Nền
    "bg_primary": "#0b0e14",
    "bg_secondary": "#111827",
    "bg_card": "#0f1724",
    "bg_input": "#0c1220",
    "bg_input_border": "#1e293b",
    # Viền
    "border": "#1e293b",
    "border_focus": "#3b82f6",
    # Chữ
    "text_primary": "#e2e8f0",
    "text_secondary": "#94a3b8",
    "text_placeholder": "#475569",
    "text_muted": "#64748b",
    # Accent
    "accent_blue": "#3b82f6",
    "accent_green": "#22c55e",
    "accent_red": "#ef4444",
    "accent_orange": "#f59e0b",
    "accent_cyan": "#06b6d4",
    "accent_purple": "#a855f7",
    "accent_pink": "#ec4899",
    # Nút bấm
    "btn_green_bg": "#16a34a",
    "btn_green_hover": "#22c55e",
    "btn_green_border": "#16a34a",
    "btn_outline_border": "#334155",
    "btn_outline_hover": "#1e293b",
    "btn_secondary_bg": "#1e293b",
    "btn_secondary_hover": "#334155",
    # Progress
    "progress_bg": "#1e293b",
    "progress_chunk_start": "#2563eb",
    "progress_chunk_end": "#3b82f6",
    # Badge
    "badge_total_bg": "#1e293b",
    "badge_success_bg": "#052e16",
    "badge_success_border": "#16a34a",
    "badge_active_bg": "#0c1a3d",
    "badge_active_border": "#2563eb",
    "badge_error_bg": "#2a0a0a",
    "badge_error_border": "#dc2626",
    # Platform
    "platform_tiktok": "#ec4899",
    "platform_douyin": "#22c55e",
    "platform_facebook": "#3b82f6",
    "platform_youtube": "#ef4444",
    "platform_system": "#06b6d4",
    "platform_progress": "#f59e0b",
    # Scrollbar
    "scrollbar_bg": "#0b0e14",
    "scrollbar_handle": "#1e293b",
    "scrollbar_handle_hover": "#334155",
    # Checkbox
    "checkbox_checked": "#22c55e",
}

# === Platform tag colors ===
PLATFORM_COLORS = {
    "TIKTOK": COLORS["platform_tiktok"],
    "DOUYIN": COLORS["platform_douyin"],
    "FACEBOOK": COLORS["platform_facebook"],
    "YOUTUBE": COLORS["platform_youtube"],
    "HỆ THỐNG": COLORS["platform_system"],
    "TIẾN ĐỘ": COLORS["platform_progress"],
    "LỖI": COLORS["accent_red"],
    "LỒNG TIẾNG": "#a78bfa",
}


def get_app_stylesheet() -> str:
    """Tạo stylesheet CSS toàn cục cho ứng dụng."""
    c = COLORS
    return f"""
    /* ===== TOÀN CỤC ===== */
    QWidget {{
        background-color: {c["bg_primary"]};
        color: {c["text_primary"]};
        font-family: "Segoe UI", "Noto Sans", "Arial", sans-serif;
        font-size: 13px;
    }}

    QMainWindow {{
        background-color: {c["bg_primary"]};
    }}

    /* ===== NHÃN ===== */
    QLabel {{
        color: {c["text_primary"]};
        background: transparent;
        padding: 0;
    }}

    /* ===== TRƯỜNG NHẬP LIỆU ===== */
    QTextEdit, QPlainTextEdit {{
        background-color: {c["bg_input"]};
        color: {c["text_primary"]};
        border: 1px solid {c["bg_input_border"]};
        border-radius: 6px;
        padding: 8px;
        font-family: "Cascadia Code", "Consolas", "Fira Code", monospace;
        font-size: 12px;
        selection-background-color: {c["accent_blue"]};
        selection-color: #ffffff;
    }}

    QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {c["border_focus"]};
    }}

    QLineEdit {{
        background-color: {c["bg_input"]};
        color: {c["text_primary"]};
        border: 1px solid {c["bg_input_border"]};
        border-radius: 6px;
        padding: 8px 12px;
        font-size: 13px;
        selection-background-color: {c["accent_blue"]};
    }}

    QLineEdit:focus {{
        border-color: {c["border_focus"]};
    }}

    QLineEdit:read-only {{
        color: {c["text_secondary"]};
    }}

    /* ===== NÚT BẤM ===== */
    QPushButton {{
        background-color: {c["btn_secondary_bg"]};
        color: {c["text_primary"]};
        border: 1px solid {c["btn_outline_border"]};
        border-radius: 6px;
        padding: 7px 16px;
        font-size: 13px;
        font-weight: 500;
        min-height: 16px;
    }}

    QPushButton:hover {{
        background-color: {c["btn_secondary_hover"]};
        border-color: {c["text_secondary"]};
    }}

    QPushButton:pressed {{
        background-color: {c["bg_input"]};
    }}

    QPushButton:disabled {{
        background-color: {c["bg_secondary"]};
        color: {c["text_placeholder"]};
        border-color: {c["border"]};
    }}

    /* ===== SPINBOX ===== */
    QSpinBox {{
        background-color: {c["bg_input"]};
        color: {c["text_primary"]};
        border: 1px solid {c["bg_input_border"]};
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 14px;
        font-weight: 600;
        min-width: 60px;
    }}

    QSpinBox:focus {{
        border-color: {c["border_focus"]};
    }}

    QSpinBox::up-button, QSpinBox::down-button {{
        background-color: {c["btn_secondary_bg"]};
        border: none;
        border-left: 1px solid {c["border"]};
        width: 22px;
    }}

    QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
        background-color: {c["btn_secondary_hover"]};
    }}

    QSpinBox::up-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-bottom: 5px solid {c["text_secondary"]};
        width: 0; height: 0;
    }}

    QSpinBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {c["text_secondary"]};
        width: 0; height: 0;
    }}

    /* ===== THANH TIẾN TRÌNH ===== */
    QProgressBar {{
        background-color: {c["progress_bg"]};
        border: none;
        border-radius: 5px;
        text-align: center;
        color: transparent;
        min-height: 10px;
        max-height: 10px;
    }}

    QProgressBar::chunk {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 {c["progress_chunk_start"]}, stop:1 {c["progress_chunk_end"]}
        );
        border-radius: 5px;
    }}

    /* ===== CHECKBOX ===== */
    QCheckBox {{
        color: {c["text_secondary"]};
        spacing: 8px;
        font-size: 12px;
        background: transparent;
        border: none;
    }}

    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border-radius: 3px;
        border: 1px solid {c["border"]};
        background-color: {c["bg_input"]};
    }}

    QCheckBox::indicator:checked {{
        background-color: {c["checkbox_checked"]};
        border-color: {c["checkbox_checked"]};
        image: url(assets/checkmark.png);
    }}

    QCheckBox::indicator:hover {{
        border-color: {c["accent_blue"]};
    }}

    /* ===== THANH CUỘN ===== */
    QScrollBar:vertical {{
        background-color: {c["scrollbar_bg"]};
        width: 8px;
        border: none;
        border-radius: 4px;
    }}

    QScrollBar::handle:vertical {{
        background-color: {c["scrollbar_handle"]};
        border-radius: 4px;
        min-height: 30px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: {c["scrollbar_handle_hover"]};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
        background: none;
    }}

    QScrollBar:horizontal {{
        background-color: {c["scrollbar_bg"]};
        height: 8px;
        border: none;
        border-radius: 4px;
    }}

    QScrollBar::handle:horizontal {{
        background-color: {c["scrollbar_handle"]};
        border-radius: 4px;
        min-width: 30px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background-color: {c["scrollbar_handle_hover"]};
    }}

    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
        background: none;
    }}

    /* ===== THANH TRẠNG THÁI ===== */
    QStatusBar {{
        background-color: {c["bg_secondary"]};
        color: {c["text_secondary"]};
        border-top: 1px solid {c["border"]};
        font-size: 12px;
        padding: 4px 12px;
    }}

    /* ===== TOOLTIP ===== */
    QToolTip {{
        background-color: {c["bg_card"]};
        color: {c["text_primary"]};
        border: 1px solid {c["border"]};
        border-radius: 4px;
        padding: 6px 10px;
        font-size: 12px;
    }}

    /* ===== MESSAGEBOX ===== */
    QMessageBox {{
        background-color: {c["bg_secondary"]};
    }}

    QMessageBox QLabel {{
        color: {c["text_primary"]};
        font-size: 13px;
    }}

    QMessageBox QPushButton {{
        min-width: 80px;
        padding: 6px 20px;
    }}

    /* ===== SPLITTER ===== */
    QSplitter::handle {{
        background-color: {c["border"]};
    }}

    QSplitter::handle:horizontal {{
        width: 1px;
    }}

    /* ===== TAB WIDGET ===== */
    QTabWidget::pane {{
        border: 1px solid {c["border"]};
        border-radius: 8px;
        background-color: {c["bg_primary"]};
        top: -1px;
    }}

    QTabBar::tab {{
        background-color: {c["bg_secondary"]};
        color: {c["text_muted"]};
        border: 1px solid {c["border"]};
        border-bottom: none;
        border-radius: 0;
        border-top-left-radius: 7px;
        border-top-right-radius: 7px;
        padding: 9px 22px;
        font-size: 13px;
        font-weight: 600;
        margin-right: 3px;
        min-width: 200px;
    }}

    QTabBar::tab:selected {{
        background-color: {c["bg_card"]};
        color: {c["text_primary"]};
        border-color: {c["border"]};
        border-bottom: 2px solid {c["accent_blue"]};
    }}

    QTabBar::tab:hover:!selected {{
        background-color: {c["btn_secondary_hover"]};
        color: {c["text_secondary"]};
    }}

    /* ===== TABLE WIDGET ===== */
    QTableWidget {{
        background-color: {c["bg_input"]};
        color: {c["text_primary"]};
        border: 1px solid {c["bg_input_border"]};
        border-radius: 6px;
        gridline-color: {c["border"]};
        font-size: 12px;
        outline: none;
        selection-background-color: {c["badge_active_bg"]};
        selection-color: {c["text_primary"]};
    }}

    QTableWidget::item {{
        padding: 6px 10px;
        border: none;
    }}

    QTableWidget::item:selected {{
        background-color: {c["badge_active_bg"]};
        color: {c["text_primary"]};
    }}

    QTableWidget::item:hover {{
        background-color: {c["btn_secondary_hover"]};
    }}

    QHeaderView::section {{
        background-color: {c["bg_secondary"]};
        color: {c["text_secondary"]};
        border: none;
        border-right: 1px solid {c["border"]};
        border-bottom: 1px solid {c["border"]};
        padding: 7px 10px;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.3px;
    }}

    QHeaderView::section:first {{
        border-top-left-radius: 6px;
    }}

    QHeaderView::section:last {{
        border-right: none;
    }}

    QTableCornerButton::section {{
        background-color: {c["bg_secondary"]};
        border: none;
        border-bottom: 1px solid {c["border"]};
    }}
    """
