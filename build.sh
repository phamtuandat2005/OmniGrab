#!/bin/bash
# OmniGrab - Kịch bản đóng gói ứng dụng (Linux/macOS)

set -e

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║       OmniGrab - Kịch bản đóng gói ứng dụng     ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# Kiểm tra Python
if ! command -v python3 &> /dev/null; then
    echo "[LỖI] Không tìm thấy Python 3. Hãy cài đặt Python 3.10+ trước."
    exit 1
fi

# Cài đặt thư viện
echo "[1/3] Đang cài đặt thư viện phụ thuộc..."
pip3 install -r requirements.txt --quiet

echo "[2/3] Đang kiểm tra PyInstaller..."
pip3 install pyinstaller --quiet --upgrade

echo "[3/3] Đang đóng gói ứng dụng..."
echo ""

# Đóng gói
pyinstaller \
    --noconfirm \
    --clean \
    --noconsole \
    --onedir \
    --name "OmniGrab" \
    --add-data "ui:ui" \
    --add-data "core:core" \
    --hidden-import "PyQt6" \
    --hidden-import "PyQt6.QtCore" \
    --hidden-import "PyQt6.QtGui" \
    --hidden-import "PyQt6.QtWidgets" \
    --hidden-import "yt_dlp" \
    main.py

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║            ĐÓNG GÓI THÀNH CÔNG!                 ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  Thư mục đầu ra: dist/OmniGrab/                 ║"
echo "║                                                  ║"
echo "║  Đảm bảo ffmpeg đã cài trên hệ thống:           ║"
echo "║  sudo apt install ffmpeg  (Ubuntu/Debian)        ║"
echo "║  brew install ffmpeg      (macOS)                ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
