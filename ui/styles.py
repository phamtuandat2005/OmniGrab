"""
ui/styles.py - Hệ thống Theme & Design Tokens đồng nhất chuẩn Desktop UI/UX.

Nguyên tắc thiết kế:
1. Đơn nhất: Gom toàn bộ màu sắc, typography (font), khoảng cách (spacing), bo góc (radius) vào một nơi.
2. Một màu chủ đạo: Duy nhất 1 màu chính (Royal Blue #2563eb / #3b82f6) cho các tương tác CTA trọng tâm.
3. Màu ngữ nghĩa chuẩn: Xanh lá (#10b981), Vàng hổ phách (#f59e0b), Đỏ (#ef4444) CHỈ dùng cho thành công, cảnh báo, lỗi.
4. Tương phản WCAG 2.1 AA: Chữ phụ (text_secondary #cbd5e1, text_muted #94a3b8) luôn đạt độ tương phản tối thiểu >= 4.5:1 trên nền tối.
"""

from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════
# 1. BẢNG MÀU CHUẨN DESIGN TOKENS
# ══════════════════════════════════════════════════════════════════════

COLORS = {
    # ── Nền ứng dụng (Dark Theme cao cấp) ──
    "bg_primary": "#090d16",       # Nền toàn cục sâu, bảo vệ mắt
    "bg_secondary": "#0f172a",     # Nền thanh trạng thái, menu, thanh bên
    "bg_card": "#111827",          # Nền thẻ container, panel
    "bg_card_hover": "#1e293b",    # Nền hover cho thẻ, item
    "bg_input": "#0b1120",         # Nền ô nhập liệu
    "bg_input_border": "#1e293b",  # Viền ô nhập mặc định

    # ── Viền (Borders) ──
    "border": "#1e293b",           # Viền chia tách tinh tế
    "border_light": "#334155",     # Viền nổi bật
    "border_focus": "#3b82f6",     # Viền khi focus vào ô nhập

    # ── Màu chữ (Typography) — Tuân thủ WCAG 4.5:1 ──
    "text_primary": "#f8fafc",      # Trắng sáng (Slate 50), độ tương phản ~15:1
    "text_secondary": "#cbd5e1",    # Xám sáng (Slate 300), độ tương phản ~8.5:1 (vượt 4.5:1)
    "text_muted": "#94a3b8",        # Xám trung (Slate 400), độ tương phản ~5.5:1 (vượt 4.5:1)
    "text_placeholder": "#64748b",  # Dành riêng cho placeholder mờ

    # ── Màu tương tác chủ đạo (Single Primary Brand Accent) ──
    "accent_primary": "#2563eb",    # Royal Blue - Nút Primary chính
    "accent_primary_hover": "#3b82f6",
    "accent_primary_active": "#1d4ed8",
    "accent_primary_subtle": "rgba(37, 99, 235, 0.15)",

    # ── Màu trạng thái ngữ nghĩa (CHỈ dùng cho Thành công / Cảnh báo / Lỗi) ──
    "status_success": "#10b981",    # Thành công / Đã tải xong / Hoàn tất
    "status_success_bg": "rgba(16, 185, 129, 0.12)",
    "status_success_border": "rgba(16, 185, 129, 0.35)",

    "status_warning": "#f59e0b",    # Cảnh báo / Đang xử lý / Đợi
    "status_warning_bg": "rgba(245, 158, 11, 0.12)",
    "status_warning_border": "rgba(245, 158, 11, 0.35)",

    "status_error": "#ef4444",      # Lỗi / Thất bại / Hết hạn
    "status_error_bg": "rgba(239, 68, 68, 0.12)",
    "status_error_border": "rgba(239, 68, 68, 0.35)",

    # ── Nút bấm (Button States) ──
    "btn_primary_bg": "#2563eb",
    "btn_primary_hover": "#3b82f6",
    "btn_primary_active": "#1d4ed8",
    "btn_primary_text": "#ffffff",

    "btn_secondary_bg": "#1e293b",
    "btn_secondary_hover": "#334155",
    "btn_secondary_border": "#334155",

    "btn_outline_border": "#334155",
    "btn_outline_hover": "#1e293b",

    # ── Thanh tiến trình (Progress Bar) ──
    "progress_bg": "#1e293b",
    "progress_chunk_start": "#2563eb",
    "progress_chunk_end": "#3b82f6",

    # ── Badges ──
    "badge_total_bg": "#1e293b",
    "badge_success_bg": "rgba(16, 185, 129, 0.15)",
    "badge_success_border": "#10b981",
    "badge_active_bg": "rgba(37, 99, 235, 0.15)",
    "badge_active_border": "#3b82f6",
    "badge_error_bg": "rgba(239, 68, 68, 0.15)",
    "badge_error_border": "#ef4444",

    # ── Scrollbar ──
    "scrollbar_bg": "#090d16",
    "scrollbar_handle": "#1e293b",
    "scrollbar_handle_hover": "#334155",

    # ── Checkbox & Radio ──
    "checkbox_checked": "#2563eb",

    # ── Khóa tương thích & Bí danh ngữ nghĩa ──
    "brand": "#2563eb",
    "primary": "#2563eb",
    "success": "#10b981",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "error": "#ef4444",
    "accent_blue": "#3b82f6",
    "accent_green": "#10b981",
    "accent_red": "#ef4444",
    "accent_orange": "#f59e0b",
    "accent_cyan": "#3b82f6",      # Gom về tone màu chính
    "accent_purple": "#818cf8",
    "accent_pink": "#3b82f6",
    "btn_green_bg": "#2563eb",     # Chuyển nút Tải sang chuẩn màu chính
    "btn_green_hover": "#3b82f6",
    "btn_green_border": "#2563eb",
    "platform_tiktok": "#cbd5e1",
    "platform_douyin": "#cbd5e1",
    "platform_facebook": "#3b82f6",
    "platform_youtube": "#cbd5e1",
    "platform_system": "#94a3b8",
    "platform_progress": "#f59e0b",
}

# Tag màu nhật ký hệ thống (Realtime Logs)
PLATFORM_COLORS = {
    "TIKTOK": "#cbd5e1",
    "TIKTOK AUTO": "#cbd5e1",
    "DOUYIN": "#cbd5e1",
    "FACEBOOK": "#60a5fa",
    "YOUTUBE": "#f87171",
    "HỆ THỐNG": "#94a3b8",
    "TIẾN ĐỘ": "#f59e0b",
    "LỖI": "#ef4444",
    "LỒNG TIẾNG": "#818cf8",
    "STUDIO": "#60a5fa",
}


# ══════════════════════════════════════════════════════════════════════
# 2. TOKENS ĐỊNH DẠNG (FONTS, SPACING, RADIUS)
# ══════════════════════════════════════════════════════════════════════

FONTS = {
    "family": '"Segoe UI", -apple-system, "SF Pro Text", "Roboto", "Helvetica Neue", sans-serif',
    "mono": '"Cascadia Code", "Consolas", "Fira Code", monospace',
    "size_xs": "11px",
    "size_sm": "12px",
    "size_base": "13px",
    "size_md": "14px",
    "size_lg": "16px",
    "size_xl": "18px",
}

SPACING = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 20,
}

RADIUS = {
    "sm": "4px",
    "md": "6px",
    "lg": "8px",
    "full": "9999px",
}


# ══════════════════════════════════════════════════════════════════════
# 3. HELPER STYLES CHO NÚT BẤM VÀ CÁC THÀNH PHẦN GIAO DIỆN
# ══════════════════════════════════════════════════════════════════════

def btn_primary_style() -> str:
    """Style cho nút CTA Primary duy nhất trên mỗi màn hình (Bắt đầu tải / Quét / Lồng tiếng)."""
    c = COLORS
    return f"""
        QPushButton {{
            background-color: {c['accent_primary']};
            color: #ffffff;
            border: none;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 700;
            padding: 9px 24px;
            letter-spacing: 0.3px;
        }}
        QPushButton:hover {{
            background-color: {c['accent_primary_hover']};
        }}
        QPushButton:pressed {{
            background-color: {c['accent_primary_active']};
        }}
        QPushButton:disabled {{
            background-color: {c['border']};
            color: {c['text_placeholder']};
        }}
    """


def btn_secondary_style() -> str:
    """Style cho các nút chức năng phụ (Dán, Xóa, Quét, Chọn tất cả, v.v.)."""
    c = COLORS
    return f"""
        QPushButton {{
            background-color: {c['btn_secondary_bg']};
            color: {c['text_primary']};
            border: 1px solid {c['btn_secondary_border']};
            border-radius: 6px;
            font-size: 12.5px;
            font-weight: 500;
            padding: 6px 14px;
        }}
        QPushButton:hover {{
            background-color: {c['btn_secondary_hover']};
            border-color: {c['text_secondary']};
        }}
        QPushButton:pressed {{
            background-color: {c['bg_input']};
        }}
        QPushButton:disabled {{
            background-color: {c['bg_secondary']};
            color: {c['text_placeholder']};
            border-color: {c['border']};
        }}
    """


def btn_stop_style() -> str:
    """Style cho nút Dừng tải (đảm bảo không lấn át nút Primary)."""
    c = COLORS
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {c['text_secondary']};
            border: 1.5px solid {c['btn_outline_border']};
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            padding: 8px 20px;
        }}
        QPushButton:hover {{
            background-color: {c['status_error_bg']};
            border-color: {c['status_error']};
            color: {c['status_error']};
        }}
        QPushButton:disabled {{
            color: {c['text_placeholder']};
            border-color: {c['border']};
        }}
    """


def card_style() -> str:
    """Style chuẩn cho khung Card chứa nội dung."""
    c = COLORS
    return f"""
        QFrame#card {{
            background-color: {c['bg_card']};
            border: 1px solid {c['border']};
            border-radius: 8px;
        }}
    """


# ══════════════════════════════════════════════════════════════════════
# 4. STYLESHEET TOÀN CỤC (GLOBAL APP STYLESHEET)
# ══════════════════════════════════════════════════════════════════════

def get_app_stylesheet() -> str:
    """Tạo stylesheet CSS toàn cục đồng bộ hoàn toàn cho toàn bộ ứng dụng."""
    c = COLORS
    f = FONTS
    return f"""
    /* ===== TOÀN CỤC ===== */
    QWidget {{
        background-color: {c["bg_primary"]};
        color: {c["text_primary"]};
        font-family: {f["family"]};
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
        font-family: {f["mono"]};
        font-size: 12px;
        selection-background-color: {c["accent_primary"]};
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
        padding: 7px 12px;
        font-size: 13px;
        selection-background-color: {c["accent_primary"]};
        selection-color: #ffffff;
    }}

    QLineEdit:focus {{
        border-color: {c["border_focus"]};
    }}

    QLineEdit:read-only {{
        color: {c["text_secondary"]};
        background-color: {c["bg_secondary"]};
    }}

    /* ===== NÚT BẤM CHUNG ===== */
    QPushButton {{
        background-color: {c["btn_secondary_bg"]};
        color: {c["text_primary"]};
        border: 1px solid {c["btn_outline_border"]};
        border-radius: 6px;
        padding: 7px 16px;
        font-size: 12.5px;
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

    /* ===== COMBOBOX & SPINBOX ===== */
    QComboBox, QSpinBox {{
        background-color: {c["bg_input"]};
        color: {c["text_primary"]};
        border: 1px solid {c["bg_input_border"]};
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 12.5px;
        min-height: 18px;
    }}

    QComboBox:focus, QSpinBox:focus {{
        border-color: {c["border_focus"]};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {c["bg_card"]};
        color: {c["text_primary"]};
        border: 1px solid {c["border"]};
        selection-background-color: {c["accent_primary"]};
        selection-color: #ffffff;
        outline: none;
        padding: 4px;
    }}

    QSpinBox::up-button, QSpinBox::down-button {{
        background-color: {c["btn_secondary_bg"]};
        border: none;
        border-left: 1px solid {c["border"]};
        width: 20px;
    }}

    QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
        background-color: {c["btn_secondary_hover"]};
    }}

    /* ===== THANH TIẾN TRÌNH ===== */
    QProgressBar {{
        background-color: {c["progress_bg"]};
        border: none;
        border-radius: 4px;
        text-align: center;
        color: transparent;
        min-height: 8px;
        max-height: 8px;
    }}

    QProgressBar::chunk {{
        background-color: {c["accent_primary"]};
        border-radius: 4px;
    }}

    /* ===== CHECKBOX ===== */
    QCheckBox {{
        color: {c["text_secondary"]};
        spacing: 8px;
        font-size: 12.5px;
        background: transparent;
        border: none;
    }}

    QCheckBox::indicator {{
        width: 17px;
        height: 17px;
        border-radius: 4px;
        border: 1.5px solid {c["border_light"]};
        background-color: {c["bg_input"]};
    }}

    QCheckBox::indicator:hover {{
        border-color: {c["border_focus"]};
    }}

    QCheckBox::indicator:checked {{
        background-color: {c["accent_primary"]};
        border-color: {c["accent_primary"]};
        image: url(assets/checkmark.png);
    }}

    /* ===== THANH CUỘN ===== */
    QScrollBar:vertical {{
        background-color: {c["scrollbar_bg"]};
        width: 8px;
        border: none;
        border-radius: 4px;
        margin: 2px 0;
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
        margin: 0 2px;
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
        padding: 3px 10px;
    }}

    /* ===== BẢNG DỮ LIỆU ===== */
    QTableWidget {{
        background-color: {c["bg_input"]};
        color: {c["text_primary"]};
        border: 1px solid {c["bg_input_border"]};
        border-radius: 6px;
        gridline-color: {c["border"]};
        font-size: 12.5px;
        outline: none;
        selection-background-color: {c["accent_primary_subtle"]};
        selection-color: {c["text_primary"]};
    }}

    QTableWidget::item {{
        padding: 6px 10px;
        border: none;
    }}

    QTableWidget::item:selected {{
        background-color: {c["accent_primary_subtle"]};
        color: {c["text_primary"]};
    }}

    QTableWidget::item:hover {{
        background-color: {c["bg_card_hover"]};
    }}

    QHeaderView::section {{
        background-color: {c["bg_secondary"]};
        color: {c["text_secondary"]};
        border: none;
        border-right: 1px solid {c["border"]};
        border-bottom: 1px solid {c["border"]};
        padding: 8px 10px;
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 0.2px;
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

    /* ===== MENU & DIALOG ===== */
    QMenu {{
        background-color: {c["bg_card"]};
        color: {c["text_primary"]};
        border: 1px solid {c["border"]};
        border-radius: 6px;
        padding: 4px;
    }}

    QMenu::item {{
        padding: 6px 20px 6px 12px;
        border-radius: 4px;
    }}

    QMenu::item:selected {{
        background-color: {c["accent_primary"]};
        color: #ffffff;
    }}

    QMenu::separator {{
        height: 1px;
        background-color: {c["border"]};
        margin: 4px 0;
    }}

    QDialog {{
        background-color: {c["bg_secondary"]};
    }}

    QToolTip {{
        background-color: {c["bg_card"]};
        color: {c["text_primary"]};
        border: 1px solid {c["border"]};
        border-radius: 4px;
        padding: 6px 10px;
        font-size: 12px;
    }}
    """
