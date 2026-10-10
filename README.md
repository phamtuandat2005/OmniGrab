<div align="center">
  <img src="assets/icon.png" alt="OmniGrab Logo" width="120" />
  <h1>OmniGrab v4.0</h1>
  <p><b>Công Cụ Tải Video Hàng Loạt & Lồng Tiếng AI Đa Nền Tảng</b></p>
  <p>
    <b>TikTok</b> &bull; 
    <b>Douyin (抖音)</b> &bull; 
    <b>Facebook</b> &bull; 
    <b>YouTube</b>
  </p>
  <p><i>Giao diện Cyber Dark hiện đại &bull; Tối ưu 100% Tiếng Việt &bull; Đa luồng tốc độ cao</i></p>
</div>

---

## 📸 Giao Diện Ứng Dụng

<div align="center">
  <h3>Chế độ 1: Tải hàng loạt theo danh sách link (Ctrl + 1)</h3>
  <img src="assets/gui/tai-link.png" alt="Giao diện tải link" width="850" />
  <br/><br/>
  <h3>Chế độ 2: Quét & Tải toàn bộ Kênh / Hồ sơ (Ctrl + 2)</h3>
  <img src="assets/gui/tai-kenh.png" alt="Giao diện quét kênh" width="850" />
</div>

---

## ✨ Điểm Nổi Bật & Tính Năng Chính

### 1. 📥 Tải Video Hàng Loạt (Chế độ 1)
- **Nhận diện link thông minh:** Tự động phát hiện và lọc URL từ văn bản chia sẻ bất kỳ (kể cả đoạn chat tiếng Trung kèm link Douyin).
- **Tải đa luồng song song:** Tùy biến từ 1 đến 5 luồng tải cùng lúc, tận dụng tối đa băng thông mạng.
- **Tách âm thanh MP3:** Tự động trích xuất file nhạc MP3 chuẩn 192kbps chỉ với một cú click chuột.
- **Tương thích tuyệt đối (H.264/AAC):** Tự động chuyển đổi các video dùng codec HEVC (H.265) sang H.264, xem được ngay trên Windows Media Player mà không lo lỗi màn hình đen.

### 2. 🔍 Quét & Tải Toàn Bộ Kênh / Hồ Sơ (Chế độ 2)
- **Douyin (抖音):** Tích hợp thư viện chuyên dụng `f2`, vượt qua hệ thống chữ ký chống cào (`a_bogus`, `X-Bogus`) để lấy toàn bộ video của kênh/user profile.
- **Facebook:** Quét toàn bộ video từ Fanpage, Trang cá nhân, danh sách Reels bằng cơ chế bóc tách JSON và giả lập TLS (`curl_cffi`).
- **TikTok & YouTube:** Duyệt danh sách kênh và playlist cực nhanh.
- **Hiển thị đầy đủ siêu dữ liệu (Metadata):** Bảng quản lý trực quan hiển thị Lượt xem (Views), Lượt thích (Likes), Thời lượng (Duration), Ngày đăng tải.

### 3. 🎯 Bộ Lọc Video Viral
- **Lọc theo Lượt xem & Lượt thích:** Nhanh chóng lọc ra các video triệu view, video xu hướng để phục vụ nghiên cứu nội dung hoặc re-up.
- **Lọc theo Thời lượng:** Phân loại nhanh video ngắn (Shorts/Reels dưới 60s) hoặc video dài (trên 60s).
- **Lọc theo Ngày đăng:** Lọc các video mới đăng trong 3 ngày, 7 ngày hoặc 30 ngày gần nhất.

### 4. 🎙 Lồng Tiếng AI Tiếng Việt (AI Dubbing)
- **Nhận diện giọng nói:** Mô hình `faster-whisper` bóc tách chính xác từng câu thoại gốc.
- **Dịch thuật thông minh:** Dịch ngữ nghĩa tự nhiên sang Tiếng Việt bằng `deep-translator`.
- **Thuyết minh cảm xúc:** Tích hợp `edge-tts` với các giọng đọc Tiếng Việt chuẩn (HoaiMy, NamMinh) tự nhiên, đồng bộ chuẩn thời lượng video.

### 5. 🍪 Quản Lý Cookie & Vượt Tường Lửa
- Hỗ trợ nạp file cookie định dạng chuẩn Netscape (`cookies.txt`).
- Tự động nhận diện khi nền tảng yêu cầu xác thực phiên và mở bảng hướng dẫn chi tiết.

---

## 📦 Yêu Cầu Hệ Thống & Cài Đặt

### Yêu cầu tiên quyết
- **Hệ điều hành:** Windows 10 / 11, macOS, hoặc Linux.
- **Python:** Phiên bản 3.10 trở lên (khuyên dùng Python 3.11 - 3.13).
- **FFmpeg & FFprobe:** Cần thiết để xử lý ghép nối âm thanh/video và đổi mã codec.
  > *Trên Windows: Đặt trực tiếp 2 file `ffmpeg.exe` và `ffprobe.exe` vào cùng thư mục với `main.py` (dự án đã tích hợp sẵn).*

---

### Các bước cài đặt mã nguồn

1. **Clone repository hoặc tải mã nguồn:**
   ```bash
   git clone https://github.com/phamtuandat2005/OmniGrab.git
   cd OmniGrab
   ```

2. **Khởi tạo môi trường ảo (khuyên dùng):**
   ```bash
   python -m venv venv
   # Kích hoạt trên Windows:
   .\venv\Scripts\activate
   # Kích hoạt trên Linux/macOS:
   source venv/bin/activate
   ```

3. **Cài đặt các thư viện phụ thuộc:**
   ```bash
   pip install -r requirements.txt
   ```

---

## 🚀 Hướng Dẫn Sử Dụng

### Khởi chạy ứng dụng
```bash
python main.py
```

### 1. Tải theo danh sách link (Phím tắt: `Ctrl + 1`)
![Chế độ tải link](assets/gui/tai-link.png)
1. Dán danh sách link video vào ô nhập liệu (mỗi link một dòng, hoặc dán cả đoạn tin nhắn chia sẻ).
2. Chọn thư mục lưu video.
3. Tích chọn **"Chỉ trích xuất âm thanh (MP3)"** nếu chỉ cần lấy file nhạc.
4. Bấm **"Bắt đầu tải"** và theo dõi tiến trình trực quan.

### 2. Quét & Tải theo Kênh (Phím tắt: `Ctrl + 2`)
![Chế độ quét kênh](assets/gui/tai-kenh.png)
1. Dán link kênh/hồ sơ:
   - **Douyin:** `https://www.douyin.com/user/MS4wLjABAAAA...`
   - **Facebook:** `https://www.facebook.com/ten_page/videos` hoặc link Fanpage/Reels.
   - **TikTok:** `https://www.tiktok.com/@username`
2. Thiết lập số lượng video tối đa cần quét và các điều kiện lọc (Lượt xem, Lượt thích, Thời lượng).
3. Bấm **"Quét kênh"**.
4. Chọn các video ưng ý trong bảng danh sách và bấm **"Tải các video đã chọn"**.

---

## 🍪 Hướng Dẫn Nạp Cookie (`cookies.txt`)

Một số nền tảng (như Douyin khi quét toàn bộ kênh hoặc video Facebook nhóm kín) yêu cầu cookie phiên đăng nhập:

1. Cài đặt tiện ích mở rộng trình duyệt **Get cookies.txt LOCALLY** trên Chrome / Edge / Cốc Cốc.
2. Truy cập vào website mục tiêu (ví dụ `douyin.com` hoặc `facebook.com`) và đăng nhập tài khoản.
3. Bấm vào biểu tượng tiện ích trên thanh công cụ → Chọn **Export** để tải file `cookies.txt`.
4. Trong ứng dụng OmniGrab, bấm nút **"Nạp Cookie (.txt)"** và chọn file vừa tải.

---

## 📁 Cấu Trúc Dự Án

```
OmniGrab/
├── assets/                  # Tài nguyên hình ảnh, logo, icon, giao diện
│   ├── gui/                 # Ảnh chụp màn hình ứng dụng (tai-link.png, tai-kenh.png)
│   ├── icon.ico             # Biểu tượng phần mềm Windows
│   └── icon.png             # Logo chính độ phân giải cao
├── core/                    # Lõi xử lý nền tảng
│   ├── channel_scrapers.py  # Bộ quét kênh Douyin (f2) & Facebook (curl_cffi)
│   ├── downloader.py        # Tích hợp yt-dlp & chuẩn hóa H.264
│   ├── dubber.py            # Whisper + Dịch tự động + Lồng tiếng TTS
│   ├── dub_worker.py        # Luồng nền lồng tiếng AI
│   ├── parser.py            # Trích xuất & làm sạch URL thông minh
│   ├── security.py          # Quản lý đường dẫn môi trường thực thi
│   └── worker.py            # Luồng tải đa luồng & quản lý tiến trình
├── ui/                      # Giao diện đồ họa (PyQt6)
│   ├── cookie_dialog.py     # Hộp thoại cảnh báo & hỗ trợ Cookie
│   ├── main_window.py       # Cửa sổ chính & điều phối giao diện
│   └── styles.py            # Bảng màu Cyber Dark Theme & CSS
├── main.py                  # Điểm khởi chạy ứng dụng
├── requirements.txt         # Danh sách thư viện Python
├── build.bat                # Kịch bản đóng gói .exe cho Windows
└── README.md                # Tài liệu hướng dẫn sử dụng dự án
```

---

## 🔨 Đóng Gói Thành Ứng Dụng (.exe)

Để đóng gói thành một file thực thi độc lập cho máy tính Windows không cần cài Python:

```cmd
build.bat
```

Sau khi hoàn tất, file chạy sẽ nằm trong thư mục `dist/OmniGrab/OmniGrab.exe`.

---

## ❓ Câu Hỏi Thường Gặp (FAQ)

<details>
<summary><b>1. Quét kênh Douyin báo lỗi 403 Forbidden?</b></summary>
Douyin thắt chặt bảo mật API đối với danh sách kênh. Bạn chỉ cần nạp file <code>cookies.txt</code> của một tài khoản Douyin (dù là tài khoản clone) vào ứng dụng là có thể quét bình thường.
</details>

<details>
<summary><b>2. Video tải về có tiếng nhưng màn hình đen trên Windows Media Player?</b></summary>
OmniGrab đã tích hợp tính năng tự động phát hiện codec HEVC (H.265) và chuyển đổi sang H.264 chuẩn. Hãy đảm bảo bạn có file <code>ffmpeg.exe</code> nằm cùng thư mục phần mềm.
</details>

<details>
<summary><b>3. Tải video từ nhóm Facebook kín hoặc video giới hạn độ tuổi?</b></summary>
Nạp file <code>cookies.txt</code> được xuất từ trình duyệt đã đăng nhập tài khoản Facebook có quyền xem video đó.
</details>

---

## ⚖️ Tuyên Bố Từ Chối Trách Nhiệm (Disclaimer)

* Công cụ này được phát triển phục vụ mục đích **học tập, nghiên cứu kỹ thuật và sao lưu dữ liệu cá nhân**.
* Tác giả không chịu trách nhiệm cho bất kỳ hành vi sử dụng công cụ này vào mục đích thương mại trái phép, vi phạm bản quyền nội dung hoặc vi phạm Điều khoản dịch vụ (ToS) của các nền tảng mạng xã hội liên quan.

---

## 📄 Giấy Phép

Phát hành theo giấy phép **MIT License**. Tự do sử dụng và tùy biến cho mục đích cá nhân.
