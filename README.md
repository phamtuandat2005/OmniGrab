# 🎬 OmniGrab — Công Cụ Tải Video Hàng Loạt

> Tải video hàng loạt từ **TikTok**, **Douyin**, **Facebook** với giao diện đồ họa hiện đại, hỗ trợ Tiếng Việt toàn diện.

---

## ✨ Tính năng chính

- 🎯 **Tải hàng loạt** — Dán nhiều liên kết cùng lúc, tải song song đa luồng
- 🌐 **Đa nền tảng** — Hỗ trợ TikTok, Douyin (抖音), Facebook
- 🧹 **Trích xuất thông minh** — Tự động nhận diện URL từ chuỗi chia sẻ (kể cả văn bản Trung Quốc kèm link Douyin)
- 🍪 **Xác thực Cookie** — Tải video từ nhóm riêng tư Facebook hoặc tài khoản giới hạn
- 🎨 **Giao diện tối hiện đại** — Dark Theme đẹp mắt, dễ sử dụng
- 📋 **Nhật ký chi tiết** — Theo dõi tiến trình thời gian thực
- 📤 **Xuất liên kết lỗi** — Dễ dàng thử lại các video tải thất bại
- 🛡 **An toàn** — Không đơ giao diện, dừng tải an toàn bất cứ lúc nào

---

## 📦 Cài đặt

### Yêu cầu hệ thống
- **Python**: 3.10 trở lên
- **FFmpeg**: Cần thiết để ghép video/audio (đặc biệt cho Facebook)

### Bước 1: Cài đặt thư viện

```bash
pip install -r requirements.txt
```

### Bước 2: Cài đặt FFmpeg

#### Windows
1. Tải FFmpeg từ [ffmpeg.org](https://ffmpeg.org/download.html) hoặc [gyan.dev](https://www.gyan.dev/ffmpeg/builds/)
2. Giải nén và đặt `ffmpeg.exe` vào:
   - Thư mục chứa `main.py`, **HOẶC**
   - Thêm vào biến môi trường `PATH`

#### Linux (Ubuntu/Debian)
```bash
sudo apt update && sudo apt install ffmpeg
```

#### macOS
```bash
brew install ffmpeg
```

---

## 🚀 Sử dụng

### Chạy ứng dụng
```bash
python main.py
```

### Hướng dẫn nhanh
1. **Dán liên kết** — Dán danh sách URL vào ô nhập liệu (mỗi dòng một link, hoặc chuỗi chia sẻ có chứa link)
2. **Chọn thư mục lưu** — Nhấn "Chọn thư mục lưu..." để chọn nơi lưu video
3. **Tùy chọn Cookie** — Nếu cần tải video riêng tư, chọn file `cookies.txt`
4. **Chỉnh số luồng** — Chọn từ 1 đến 5 luồng tải đồng thời
5. **Bắt đầu tải** — Nhấn nút "Bắt đầu tải" và theo dõi tiến trình

### Nhập từ file
- Nhấn "Nhập từ file (.txt)" để đọc danh sách liên kết từ file văn bản
- Hỗ trợ file `.txt` và `.csv`

### Xuất liên kết lỗi
- Sau khi tải xong, nhấn "Xuất liên kết lỗi" để lưu các link thất bại
- File xuất ra có thể dùng lại để thử tải lần sau

---

## 🍪 Hướng dẫn lấy Cookie

Để tải video từ nhóm riêng tư Facebook hoặc tài khoản giới hạn:

1. Cài tiện ích mở rộng **"Get cookies.txt LOCALLY"** trên Chrome/Edge
2. Đăng nhập vào Facebook/TikTok trên trình duyệt
3. Nhấn vào tiện ích → "Export" để lưu file `cookies.txt`
4. Chọn file cookie trong ứng dụng OmniGrab

---

## 📁 Cấu trúc dự án

```
OmniGrab/
├── main.py                  # Điểm khởi chạy ứng dụng
├── ui/
│   ├── __init__.py
│   ├── main_window.py       # Giao diện chính PyQt6
│   └── styles.py            # Dark Theme & CSS tùy biến
├── core/
│   ├── __init__.py
│   ├── parser.py            # Trích xuất & làm sạch URL
│   ├── worker.py            # QThread đa luồng nền
│   └── downloader.py        # Cấu hình yt-dlp tối ưu
├── requirements.txt         # Thư viện phụ thuộc
├── build.bat                # Đóng gói Windows (PyInstaller)
├── build.sh                 # Đóng gói Linux/macOS
└── README.md                # Hướng dẫn này
```

---

## 🏗 Đóng gói thành ứng dụng (.exe)

### Windows
```batch
build.bat
```

### Linux/macOS
```bash
chmod +x build.sh
./build.sh
```

Sau khi đóng gói, ứng dụng nằm trong thư mục `dist/OmniGrab/`.

> **Lưu ý**: Đặt `ffmpeg.exe` (Windows) vào thư mục `dist/OmniGrab/` để ứng dụng nhận diện tự động.

---

## 🔧 Khắc phục sự cố

| Vấn đề | Giải pháp |
|--------|-----------|
| Không tải được video Facebook | Cung cấp file `cookies.txt` với tài khoản đã đăng nhập |
| Video Douyin lỗi | Kiểm tra liên kết còn hoạt động, thử lại với cookie |
| Ứng dụng báo thiếu ffmpeg | Cài đặt ffmpeg hoặc đặt `ffmpeg.exe` cùng thư mục ứng dụng |
| Tốc độ tải chậm | Giảm số luồng đồng thời xuống 1-2, kiểm tra kết nối mạng |

---

## 📄 Giấy phép

Dự án này được phát hành theo giấy phép MIT.

---

*Được xây dựng bằng ❤️ với Python, PyQt6 và yt-dlp.*
