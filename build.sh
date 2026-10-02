#!/bin/bash
# OmniGrab - Trinh quan ly dong goi (Build Manager - Linux/macOS)

echo "========================================================"
echo "       OmniGrab - Trình quản lý đóng gói ứng dụng"
echo "========================================================"
echo ""

# 1. Kiem tra Python
if ! command -v python3 &> /dev/null; then
    echo "[LỖI] Không tìm thấy python3. Hãy cài đặt Python 3.10+ trước."
    exit 1
fi

# 2. Kiem tra/Thiet lap moi truong ao (venv)
if [ -f "venv/bin/activate" ]; then
    echo "[1/2] Phát hiện môi trường ảo. Đang kích hoạt..."
    source venv/bin/activate
else
    echo "[1/2] Chưa có môi trường ảo. Đang tạo mới..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "[LỖI] Không thể tạo môi trường ảo."
        exit 1
    fi
    source venv/bin/activate
    echo "      Đã tạo và kích hoạt môi trường ảo tại: venv"
fi

# 3. Cai dat thu vien vao venv
echo "[2/2] Đang cài đặt thư viện phụ thuộc..."
pip install -r requirements.txt --quiet
if [ $? -ne 0 ]; then
    echo "[LỖI] Không thể cài đặt thư viện."
    exit 1
fi
echo ""

while true; do
    echo "========================================================"
    echo "CHỌN PHƯƠNG THỨC ĐÓNG GÓI:"
    echo "========================================================"
    echo "1. Build tiêu chuẩn (PyInstaller) - Nhanh nhất, không bảo mật"
    echo "2. Build bảo mật Nuitka (C++) - Bảo mật cao, cần gcc/clang"
    echo "0. Thoát"
    echo "========================================================"
    read -p "Nhập lựa chọn của bạn (0-2): " choice

    case $choice in
        1)
            echo ""
            echo "Đang đóng gói tiêu chuẩn với PyInstaller..."
            pip install pyinstaller --quiet --upgrade
            pyinstaller --noconfirm --clean --noconsole --onedir --name "OmniGrab" \
                --icon "assets/icon.png" --add-data "ui:ui" --add-data "core:core" \
                --add-data "assets:assets" --hidden-import "PyQt6" --hidden-import "yt_dlp" main.py
            if [ $? -ne 0 ]; then
                echo "[LỖI] Đóng gói thất bại!"
                exit 1
            fi
            echo ""
            echo "ĐÓNG GÓI THÀNH CÔNG! Thư mục đầu ra: dist/OmniGrab"
            exit 0
            ;;
        2)
            echo "[1/3] Kiểm tra Nuitka..."
            pip install nuitka --quiet
            if [ $? -ne 0 ]; then
                echo "[LỖI] Không thể cài đặt Nuitka."
                exit 1
            fi
            echo "[2/3] Bắt đầu biên dịch mã nguồn Python sang C++ (Có thể mất nhiều phút)..."
            echo ""
            nuitka --standalone --onefile --enable-plugin=pyqt6 --include-package=yt_dlp --include-data-dir=assets=assets --include-data-dir=ui=ui --remove-output --lto=yes main.py
            if [ $? -ne 0 ]; then
                echo ""
                echo "[LỖI] Biên dịch thất bại! Vui lòng kiểm tra log C++ compiler."
                echo "Gợi ý: Bạn có thể cần cài đặt gcc hoặc clang."
                exit 1
            fi
            echo ""
            echo "[3/3] Biên dịch thành công!"
            echo "File thực thi: main.bin (đã được bảo mật chống dịch ngược)"
            exit 0
            ;;
        0)
            exit 0
            ;;
        *)
            echo "Lựa chọn không hợp lệ!"
            echo ""
            ;;
    esac
done
