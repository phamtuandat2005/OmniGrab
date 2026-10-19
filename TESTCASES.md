# OmniGrab — Bộ test case kiểm thử thủ công

**Phiên bản tham chiếu:** OmniGrab v4.0  
**Ngày lập:** 15/10/2026  
**Phạm vi:** Kiểm thử chức năng giao diện desktop, tải/quét video, Studio lồng tiếng, đăng TikTok/YouTube, bản quyền, cấu hình và đóng gói.

Tài liệu này là checklist kiểm thử thủ công dựa trên luồng hiện có trong mã nguồn. Các test tải/quét/đăng thật cần kết nối Internet, nội dung công khai hoặc tài khoản/cookie hợp lệ; không dùng nội dung bạn không có quyền truy cập. Uploader trình duyệt có thể làm thay đổi nội dung tài khoản nên chỉ thực hiện trên tài khoản thử nghiệm và video mẫu được phép đăng. Mục **Kết quả thực tế** để tester ghi sau mỗi lượt chạy.

## 1. Quy ước

- **Ưu tiên:** P0 = chặn phát hành; P1 = quan trọng; P2 = thường; P3 = phụ.
- **Loại:** UI = giao diện; F = chức năng; N = âm/biên; E = lỗi; I = tích hợp; R = hồi quy.
- **Trạng thái:** Chưa chạy / Đạt / Không đạt / Bị chặn / Không áp dụng.
- **Pass:** `PASS*` / `FAIL*` là kết quả kiểm tra thành phần offline, chưa xác nhận toàn bộ UI/tích hợp; `—` là chưa chạy. Chỉ đánh dấu `PASS` sau khi hoàn tất test end-to-end.
- Ghi lại phiên bản build, OS, Python (nếu chạy source), độ phân giải, mạng, nền tảng, cookie đã/ chưa nạp và đường dẫn log khi lập bug.
- Với test tải/quét có mạng, kết quả từ nền tảng bên ngoài có thể thay đổi. Nếu dịch vụ chặn hoặc API thay đổi, ghi rõ phản hồi thực tế và phân biệt lỗi dịch vụ với lỗi ứng dụng.

## 2. Môi trường và dữ liệu chuẩn bị

| Mã | Dữ liệu / điều kiện | Ghi chú |
|---|---|---|
| ENV-01 | Windows 10/11, ứng dụng chạy từ source hoặc bản build | Chạy cả hai nếu phát hành cả source và exe |
| ENV-02 | Thư mục output có quyền ghi và còn dung lượng | Dùng thư mục rỗng cho lượt đầu |
| ENV-03 | Video MP4 ngắn có âm thanh, H.264/AAC | Video riêng tư/nội bộ, lời thoại rõ |
| ENV-04 | Video MP4 HEVC/H.265 | Kiểm tra tương thích codec; cần bản quyền sử dụng |
| ENV-05 | Video không có audio | Kiểm tra nhánh mix audio dự phòng |
| ENV-06 | Video lỗi / file rỗng / file không phải video đổi đuôi .mp4 | Dùng cho xử lý lỗi |
| ENV-07 | Cookie Netscape hợp lệ cho nền tảng cần đăng nhập | Không đưa cookie thật vào bug report/log |
| ENV-08 | File cookie sai định dạng, rỗng hoặc không còn hiệu lực | Kiểm tra báo lỗi và phục hồi |
| ENV-09 | Một kênh/playlist công khai nhỏ có vài video | Ghi URL và số item dự kiến |
| ENV-10 | URL video hợp lệ từ TikTok, Douyin, Facebook, YouTube | Dùng video công khai/được phép tải |
| ENV-11 | Video tối thiểu, video thường và video dài hơn 60 giây | Cho bộ lọc duration |
| ENV-12 | Dữ liệu giấy phép thử: key sai định dạng, chữ ký sai, sai MID, hết hạn, hợp lệ | Không dùng/copy private key sản xuất |
| ENV-13 | Gemini API key thử nghiệm (nếu kiểm thử dịch có Gemini) | Theo hạn mức an toàn; nếu không có thì ghi Bị chặn |
| ENV-14 | Cookie TikTok/YouTube của tài khoản staging, trình duyệt Playwright khả dụng | Dùng chế độ riêng tư nếu không cần phát hành công khai |

## 3. Ma trận kiểm thử nhanh

| Nhóm | Test case | Số lượng |
|---|---|---:|
| Khởi động, giao diện, cấu hình | APP, UI, CFG | 14 |
| Parser và nhập URL | PAR | 17 |
| Tải hàng loạt | DL | 26 |
| Quét kênh và bộ lọc | SCAN | 30 |
| Studio, phiên âm, dịch, SRT, lồng tiếng | DUB | 26 |
| TikTok / YouTube upload | UP | 16 |
| License và giới hạn dùng thử | LIC | 15 |
| Đóng gói, bảo mật cơ bản, hồi quy | REL | 12 |
| Luồng kết hợp và kiểm thử biên | FLOW | 12 |
| Cookie và bí mật | SEC | 2 |
| **Tổng** |  | **170** |

### Kết quả kiểm tra offline đã thực hiện

- Môi trường: Windows, Python 3.13.6.
- `python -m compileall -q main.py core ui`: **PASS**.
- `python -m pytest -q`: không thu thập được test; hiện chưa có test pytest (`exit code 5`).
- Kiểm tra 33 assertion thành phần offline: **29 đạt, 4 không đạt**. Bốn lần thất bại gồm hai lần tái hiện cùng lỗi CSV và các lỗi xác thực hostname; có **3 lỗi riêng** được ghi ở PAR-011, PAR-013 và PAR-014.
- Đã kiểm tra parser URL/TXT và các biên bộ lọc metadata, cấu hình yt-dlp, parser cookie với dữ liệu giả, và từ chối license sai định dạng. Không thực hiện tải/quét mạng, thao tác UI đầy đủ, hoặc upload thật; các bài kiểm tra này vẫn để `—`.
- Lỗi tái hiện: PAR-011 không loại phần `,clip` trong dòng CSV chuẩn `https://youtu.be/csv,clip` (biến thể có khoảng trắng sau dấu phẩy được parse đúng); PAR-013 chấp nhận hostname giả `tiktok.com.evil.example` / `not-tiktok.com`; PAR-014 chấp nhận domain ngoài nếu query chứa `tiktok.com`. Parser cookie sai định dạng trả về rỗng nhưng đồng thời phát warning/traceback ra stderr.

---

## 4. Khởi động, giao diện và cấu hình

| ID | Ưu tiên / loại | Tiền điều kiện | Bước thực hiện | Kết quả mong đợi | Pass |
|---|---|---|---|---|---|
| APP-001 | P0 / F | Cài đủ phụ thuộc | Chạy `python main.py` | Cửa sổ chính mở, không traceback; icon, theme và chữ Việt hiển thị | — |
| APP-002 | P1 / N | Đóng ứng dụng sạch | Mở ứng dụng liên tiếp 3 lần | Mỗi lần mở được một instance bình thường; không giữ tiến trình treo | — |
| APP-003 | P1 / UI | Cửa sổ mở | Quan sát trang ban đầu, menu, status bar, log | Trang mặc định là Tải link; thành phần không chồng lấn hoặc bị cắt ở kích thước mặc định | — |
| APP-004 | P2 / UI | Cửa sổ mở | Dùng Ctrl+1, Ctrl+2 và chuyển Studio bằng menu/nút | Mở đúng trang Tải link, Quét kênh, Studio | — |
| APP-005 | P2 / UI | Cửa sổ mở | Thu nhỏ, phóng to, kéo đổi kích thước, khôi phục | Layout giữ khả năng thao tác; không crash | — |
| APP-006 | P2 / UI | Cửa sổ mở | Mở About và hướng dẫn | Nội dung hiển thị đầy đủ, đóng được | — |
| APP-007 | P1 / F | Cửa sổ mở | Đổi output directory sang thư mục ghi được; đóng/mở lại | Đường dẫn được lưu và nạp lại đúng | — |
| APP-008 | P1 / F | Có output directory hiện hữu | Đổi thành thư mục không còn tồn tại, khởi chạy lại | Ứng dụng dùng fallback an toàn hoặc yêu cầu chọn lại; không crash | — |
| APP-009 | P1 / F | Cửa sổ mở | Thay số luồng tải về giá trị biên nhỏ nhất và lớn nhất UI cho phép; lưu/mở lại | Giá trị trong giới hạn được giữ lại | — |
| APP-010 | P1 / F | Cửa sổ mở | Cấu hình ngôn ngữ, voice, model, volume, mute và auto-open; khởi chạy lại | Thiết lập được khôi phục chính xác | — |
| APP-011 | P1 / E | Có bản `~/.omnigrab_settings.json` sao lưu | Thay nội dung JSON bằng `{` rồi mở app | App bỏ qua cấu hình lỗi hoặc dùng mặc định; không crash | — |
| APP-012 | P2 / F | Cửa sổ mở | Chọn file cookie tải video; đóng/mở lại | Cookie tồn tại thì trạng thái được nạp lại; file mất thì không được sử dụng như hợp lệ | — |
| APP-013 | P2 / UI | Màn hình DPI cao hoặc scale 150% | Mở và chuyển trang | Font, nút, bảng và dialog không bị vỡ nghiêm trọng | — |
| APP-014 | P1 / E | Không có quyền ghi vào thư mục output (nếu có thể mô phỏng) | Chọn thư mục chỉ đọc rồi bắt đầu tải | Hiện lỗi rõ ràng, không khóa giao diện hoặc crash | — |

## 5. Parser và nhập URL

| ID | Ưu tiên / loại | Tiền điều kiện | Bước thực hiện | Kết quả mong đợi | Pass |
|---|---|---|---|---|---|
| PAR-001 | P0 / F | Trang Tải link | Dán một URL TikTok đầy đủ, bấm Bắt đầu tải | Nhận đúng một URL và bắt đầu tác vụ (không cần tải xong để xác nhận parser) | PASS* |
| PAR-002 | P1 / F | Trang Tải link | Dán văn bản chia sẻ Douyin bằng tiếng Hoa kèm URL ngắn | Trích đúng URL Douyin | PASS* |
| PAR-003 | P1 / F | Trang Tải link | Dán lần lượt URL `vm.tiktok.com`, `vt.tiktok.com`, `v.douyin.com`, `fb.watch`, `youtu.be` | Nhận từng URL rút gọn thuộc domain hỗ trợ | PASS* |
| PAR-004 | P1 / F | Trang Tải link | Dán nhiều URL TikTok/Douyin/Facebook/YouTube xen kẽ văn bản | Trích URL được hỗ trợ, giữ thứ tự ban đầu | PASS* |
| PAR-005 | P1 / F | Trang Tải link | Lặp cùng một URL nhiều lần với dấu câu cuối câu | Chỉ còn một URL; dấu câu không nằm trong URL | PASS* |
| PAR-006 | P1 / N | Trang Tải link | Dán rỗng, dấu cách và xuống dòng | Không có URL; báo nhắc nhập link, không tạo worker | PASS* |
| PAR-007 | P1 / N | Trang Tải link | Chỉ dán URL website không hỗ trợ (ví dụ example.com) | Báo không tìm thấy liên kết hợp lệ | PASS* |
| PAR-008 | P1 / F | Trang Tải link | Dán URL Douyin `jingxuan?modal_id=<id>` | Chuẩn hóa sang URL video dạng `/video/<id>` | PASS* |
| PAR-009 | P2 / N | Trang Tải link | Dán URL có query, dấu ngoặc, dấu phẩy/chấm kết thúc | Phần URL thật còn đủ; ký tự phân cách cuối được bỏ | — |
| PAR-010 | P1 / F | Có file UTF-8 .txt chứa nhiều URL và văn bản | Dùng chức năng nhập file | Trích URL giống dán trực tiếp, loại trùng | PASS* |
| PAR-011 | P2 / F | Có CSV chứa URL | Nhập CSV | URL trong nội dung được nhận diện; không có URL hợp lệ thì thông báo phù hợp | FAIL* |
| PAR-012 | P2 / E | Có file văn bản encoding không phải UTF-8 hoặc file không đọc được | Nhập file | Không crash; nếu đọc được fallback thì trích URL, nếu không thì báo lỗi dễ hiểu | PASS* |

## 6. Tải hàng loạt

| ID | Ưu tiên / loại | Tiền điều kiện | Bước thực hiện | Kết quả mong đợi | Pass |
|---|---|---|---|---|---|
| DL-001 | P0 / I | ENV-02, ENV-10 | Tải một video công khai hợp lệ | Tạo file trong output directory; báo thành công; tiến trình về trạng thái rảnh | — |
| DL-002 | P1 / I | Có hai URL hợp lệ | Tải theo batch | Cả hai item được xử lý, tổng thành công/thất bại khớp thực tế | — |
| DL-003 | P1 / F | Có batch gồm 2 URL hợp lệ và 1 URL lỗi | Bắt đầu tải | Các URL độc lập vẫn được xử lý; lỗi được ghi đúng URL, bộ đếm không sai | — |
| DL-004 | P1 / F | Có URL hợp lệ | Đặt max_workers = 1, tải vài URL | Tác vụ tuần tự, UI vẫn phản hồi | — |
| DL-005 | P1 / F | Có nhiều URL hợp lệ | Đặt max_workers ở mức lớn nhất UI cho phép | Worker chạy trong giới hạn; không tạo số thread vượt cấu hình | — |
| DL-006 | P1 / UI | Đang tải chậm hoặc nhiều URL | Quan sát progress, status, log và nút | Cập nhật tiến độ/item; Stop bật phù hợp; Start bị khóa hoặc báo đang chạy | — |
| DL-007 | P1 / F | Đang tải batch có nhiều URL; ít nhất một lượt tải còn đang chạy và còn URL đang chờ | Bấm Dừng; đợi worker kết thúc; chạy lại URL còn dang dở | Các tác vụ đã chạy có thể hoàn tất trước khi worker dừng; tác vụ chưa bắt đầu được hủy nếu có thể. UI phải báo số thành công/thất bại/bỏ qua đúng; lần chạy sau resume chỉ khi yt-dlp/nền tảng hỗ trợ | — |
| DL-008 | P1 / E | Mạng bị ngắt trong lúc tải | Rút mạng hoặc chặn kết nối | Item thất bại có thông báo; batch kết thúc; UI trở lại trạng thái rảnh | — |
| DL-009 | P1 / E | Có URL sai hoặc nội dung đã xóa | Tải URL | Ghi lỗi có thể hiểu; không sinh file hoàn chỉnh giả | — |
| DL-010 | P1 / F | Cookie hợp lệ và video cần login | Nạp cookie rồi tải | Cookie được dùng; file tải thành công nếu phiên có quyền truy cập | — |
| DL-011 | P1 / E | Cookie sai/hết hạn | Nạp cookie rồi tải video bị giới hạn | Lỗi xác thực được log; app vẫn hoạt động và cho phép nạp cookie khác | — |
| DL-012 | P1 / F | Có video hỗ trợ audio extraction | Bật MP3-only và tải | Xuất file âm thanh MP3; không yêu cầu file video đầu ra | PASS* |
| DL-013 | P1 / F | Có video không phải audio-only | Tải chế độ video thường | File video hoàn chỉnh có hình và tiếng | — |
| DL-014 | P1 / I | ENV-04, FFmpeg sẵn có | Tải/đưa video HEVC qua hậu xử lý | Nếu nhánh compatibility áp dụng, file cuối dùng H.264/AAC và mở/phát được | PASS* |
| DL-015 | P1 / I | Video H.264/AAC | Tải video | Không chuyển mã không cần thiết hoặc không làm hỏng video | — |
| DL-016 | P1 / E | FFmpeg tạm thời không tìm thấy / cấu hình binary sai trong môi trường thử | Thực hiện thao tác cần merge/conversion | Báo rõ thiếu/lỗi FFmpeg; không treo vô hạn | — |
| DL-017 | P1 / F | Có tên video chứa Unicode, ký tự đặc biệt, tiêu đề rất dài | Tải video | Tạo file hợp lệ trên filesystem; không ghi đè file khác không liên quan | — |
| DL-018 | P1 / F | Có file cùng tên đã tồn tại | Tải lại cùng URL | Hành vi overwrite/rename/resume nhất quán với cấu hình yt-dlp; không báo thành công giả | — |
| DL-019 | P1 / R | Bắt đầu batch rồi dừng, đợi worker hoàn tất cleanup | Bắt đầu batch mới | Batch mới chạy được; số đếm, progress, danh sách lỗi được reset | — |

## 7. Quét kênh, metadata và bộ lọc

| ID | Ưu tiên / loại | Tiền điều kiện | Bước thực hiện | Kết quả mong đợi | Pass |
|---|---|---|---|---|---|
| SCAN-001 | P0 / F | Trang Quét kênh | Bỏ trống URL, bấm Quét | Cảnh báo nhập URL; không tạo worker | — |
| SCAN-002 | P1 / I | ENV-09 là kênh YouTube/playlist công khai | Quét giới hạn vài video | Danh sách có tiêu đề, URL, duration, views/likes/date nếu nguồn cung cấp | — |
| SCAN-003 | P1 / I | ENV-09 là TikTok public | Quét profile với giới hạn nhỏ | Có kết quả hoặc lỗi nền tảng có thể đọc; UI không treo | — |
| SCAN-004 | P1 / I | ENV-09 là Douyin channel | Quét không cookie | Kết quả theo scraper hiện tại hoặc lỗi dịch vụ được hiển thị; worker thoát sạch | — |
| SCAN-005 | P1 / I | Douyin và cookie thích hợp (nếu API yêu cầu) | Nạp cookie, quét channel | Cookie được truyền vào scraper; lỗi cookie gợi ý nạp/thay cookie | — |
| SCAN-006 | P1 / I | Facebook page/reels public phù hợp scraper | Quét không cookie | Kết quả hoặc lý do chặn rõ; app tiếp tục dùng được | — |
| SCAN-007 | P1 / I | Facebook nội dung yêu cầu đăng nhập, ENV-07 | Nạp cookie và quét | Nội dung truy cập được thì có item; cookie không được lộ trong log | — |
| SCAN-008 | P1 / F | Quét thành công nhiều video | Quan sát bảng | Checkbox mặc định được chọn; số video và số chọn đúng | — |
| SCAN-009 | P1 / F | Có kết quả | Bỏ chọn một dòng, chọn lại, Chọn tất cả, Bỏ chọn tất cả | Trạng thái checkbox và bộ đếm cập nhật đúng | — |
| SCAN-010 | P1 / F | Có kết quả nhiều dòng và có video đạt/không đạt điều kiện lọc | Đặt bộ lọc để một số dòng bị ẩn; kiểm tra checkbox; bấm tải video đã chọn | Dòng bị ẩn phải bỏ chọn và không được đưa vào batch; chỉ dòng đang hiển thị, được chọn và có URL mới được tải | — |
| SCAN-011 | P1 / N | Không có hàng nào được chọn | Bấm tải video đã chọn | Cảnh báo; không tạo worker | — |
| SCAN-012 | P1 / F | Có video từ nhiều ngày | Lọc ngày = Tất cả | Không lọc theo tuổi video | — |
| SCAN-013 | P1 / F | Có ngày đăng chính xác | Chọn 3 ngày, 7 ngày, 30 ngày | Chỉ video trong ngưỡng còn lại (ngày cutoff tính theo ngày máy); không có date bị loại | PASS* |
| SCAN-014 | P1 / N | Có video duration <60s, =60s, >60s | Chọn Shorts/dưới 60 giây | Chỉ duration <60s qua lọc | PASS* |
| SCAN-015 | P1 / N | Như SCAN-014 | Chọn trên 60 giây | Video duration >=60s qua lọc theo implementation hiện tại | PASS* |
| SCAN-016 | P1 / F | Dữ liệu views/likes có nhiều mức | Đặt min views, min likes riêng và đồng thời | Chỉ item đạt tất cả ngưỡng mới xuất hiện | PASS* |
| SCAN-017 | P1 / N | Metadata views/likes thiếu hoặc không parse được | Bật ngưỡng tương ứng | Giá trị thiếu được coi là 0 và bị loại khi ngưỡng >0 | PASS* |
| SCAN-018 | P1 / E | URL hợp lệ về cú pháp nhưng không phải channel hoặc channel rỗng | Quét | Báo không có video/lỗi quét; trạng thái quét được reset | — |
| SCAN-019 | P1 / UI | Trong lúc scan | Quan sát nút scan, status và bảng cập nhật | Nút scan khóa trong khi chạy; tiến độ và kết quả không làm treo giao diện | — |
| SCAN-020 | P1 / F | Kết quả quét thành công | Xuất CSV, mở CSV bằng Excel/LibreOffice | Header/cột đúng, dữ liệu Unicode không hỏng, URL và metadata khớp bảng | — |
| SCAN-025 | P1 / F | Kênh có nhiều hơn 20 video và nguồn hỗ trợ phân trang | Mở danh sách trong ô Số lượng, chọn `All`, để mọi bộ lọc ở `Tất cả`/0 rồi quét | Ô Số lượng hiển thị All; scraper tiếp tục qua cursor/trang đến khi nguồn báo hết; log thể hiện tổng kết quả | — |
| SCAN-026 | P1 / F | Kênh có nhiều video | Nhập N nhỏ hơn số video nguồn trực tiếp vào ô Số lượng rồi quét | Chỉ tối đa N mục được đưa vào lọc/bảng; giá trị nhập được dùng làm giới hạn | — |
| SCAN-027 | P1 / N | API mock hoặc log phản hồi cursor lặp / has_more sai | Chọn `All` | Scraper dừng khi cursor không tiến triển hoặc chạm chốt an toàn; không chạy vô hạn và báo giới hạn nếu chốt an toàn đạt | — |
| SCAN-028 | P1 / F | Nguồn chỉ trả tối đa một trang hoặc yêu cầu login trang kế | Chọn `All` | Kết quả bằng dữ liệu nguồn thực trả; app ghi lỗi/dừng đúng cách và không khẳng định đã lấy hết kho video của nền tảng | — |
| SCAN-029 | P1 / I | Có kết quả TikTok dạng `https://www.tiktok.com/@user/video/<id>` | Nhấp URL/nhấp đúp để mở, sau đó thử menu chuột phải mở URL gốc và sao chép URL | Thao tác mở mặc định dùng `https://www.tiktok.com/player/v1/<id>`; URL gốc vẫn giữ để mở/copy/tải; TikTok player có thể vẫn từ chối theo phiên/vùng/chính sách | — |
| SCAN-030 | P1 / I | Kênh/playlist YouTube có video công khai với metadata hiển thị | Quét vài mục và so sánh bảng với trang video | yt-dlp phân giải chi tiết; duration/date/likes xuất hiện khi YouTube cung cấp; trường không công khai có thể vẫn là `--`; quét có thể lâu hơn flat mode | — |
| SCAN-031 | P1 / R | Cài ứng dụng bằng Setup vào thư mục mặc định `Program Files`; chạy bằng tài khoản Windows thường | Quét một kênh Douyin | Không báo `WinError 5` khi tạo log; thư mục làm việc/log nằm trong `%LOCALAPPDATA%\OmniGrab` | — |

## 8. Studio, phiên âm, dịch và lồng tiếng

| ID | Ưu tiên / loại | Tiền điều kiện | Bước thực hiện | Kết quả mong đợi | Pass |
|---|---|---|---|---|---|
| DUB-001 | P1 / UI | Mở Studio, không nạp video | Bấm phát, bóc thoại, xuất SRT, xuất dubbing | Từng thao tác bị chặn với thông báo phù hợp; không crash | — |
| DUB-002 | P0 / F | ENV-03 | Chọn video | Video hiện trong player; thời lượng/controls được cập nhật | — |
| DUB-003 | P1 / E | Chọn đường dẫn không tồn tại | Thử load video qua API/UI | Báo lỗi/không đổi sang trạng thái video hợp lệ | — |
| DUB-004 | P1 / E | ENV-06 | Chọn file hỏng hoặc không phải video | Lỗi phát/đọc được hiển thị; giao diện phục hồi | — |
| DUB-005 | P1 / F | ENV-03 | Play, pause, stop, seek bằng slider và bước tua | Hành vi player đúng, thời gian hiển thị đồng bộ | — |
| DUB-006 | P1 / F | Có video và kịch bản nhiều dòng đã nạp | Double-click một câu | Player tua đến timestamp dòng đó | — |
| DUB-007 | P1 / I | ENV-03, model Whisper có sẵn/quyền tải model | Bấm Bóc tách kịch bản | Tiến độ cập nhật; nhận được các segment với start/end/text; UI không block | — |
| DUB-008 | P1 / E | Whisper/model chưa tải được hoặc thiếu RAM | Bóc tách | Lỗi hiển thị; worker kết thúc; nút thao tác khôi phục | — |
| DUB-009 | P1 / F | Bóc tách xong | Kiểm tra danh sách segment | Thời gian tăng hợp lý; câu thoại không rỗng; bảng cập nhật từ worker | — |
| DUB-010 | P1 / I | Có segment và Gemini key thử hợp lệ | Chạy dịch ngữ cảnh | Dịch tiếng Việt theo hàng, trạng thái tiến trình cập nhật | — |
| DUB-011 | P1 / I | Có segment; lần lượt để trống Gemini key và dùng key sai/hết hạn; có mạng để thử dịch dự phòng | Chạy dịch cho từng cấu hình; theo dõi log và kiểm tra từng hàng | Không có key thì dùng Google Translate fallback; key lỗi thì thử Gemini rồi fallback khi khả dụng. Bản gốc không mất; nếu cả dịch vụ dự phòng cũng lỗi thì báo lỗi cụ thể, không đánh dấu dịch thành công giả | — |
| DUB-012 | P1 / F | Có bảng segment | Sửa text dịch tại một hàng rồi chuyển focus | Nội dung sửa giữ lại và dùng trong export/lồng tiếng | — |
| DUB-013 | P1 / F | Có segment đã dịch | Xuất SRT | File SRT hợp lệ UTF-8, timestamp chuẩn, nội dung đúng bản dịch | — |
| DUB-014 | P1 / N | Bảng kịch bản rỗng | Bấm Xuất SRT | Cảnh báo; không tạo file rỗng giả | — |
| DUB-015 | P1 / F | ENV-03 và segment đã dịch | Chạy dubbing, voice mặc định | Tạo `<tên>_dubbed.<ext>` cùng thư mục; video mở được và có tiếng thuyết minh | — |
| DUB-016 | P1 / F | Có segment | Thử volume giọng ở min/max hợp lệ, background ở min/max, bật mute gốc | Thiết lập được áp dụng; mute gốc loại âm gốc; mức âm không làm tiến trình lỗi | — |
| DUB-017 | P1 / I | ENV-05, segment đã dịch | Mix voice với mute background off/on | Nhánh fallback xử lý video không có audio; đầu ra vẫn phát được | — |
| DUB-018 | P1 / N | Segment có start/end sát nhau hoặc audio dài hơn khoảng thoại | Dubbing | Không crash do segment ngắn; output không làm lệch đồng bộ nghiêm trọng | — |
| DUB-019 | P1 / F | Bảng transcript đã tạo | Đóng/mở lại cùng video | Tự nạp JSON/SRT sidecar theo quy tắc liên quan; văn bản được khôi phục | — |
| DUB-020 | P1 / E | Trong khi dubbing dài | Bấm Stop và xác nhận Yes; thử lại và xác nhận No | Yes dừng và UI về trạng thái rảnh; No tiếp tục tiến trình | — |
| DUB-021 | P1 / R | Dubbing tạo output thành công | Mở output trong player, xuất SRT, quay lại trang tải rồi trở lại Studio | Không mất/nhân đôi transcript; chức năng trang khác vẫn hoạt động | — |

## 9. Đăng TikTok và YouTube

> Chỉ chạy upload end-to-end trên tài khoản staging. Chọn Private/Unlisted nếu nền tảng cho phép, xác minh cài đặt trước khi submit.

| ID | Ưu tiên / loại | Tiền điều kiện | Bước thực hiện | Kết quả mong đợi | Pass |
|---|---|---|---|---|---|
| UP-001 | P1 / UI | Studio chưa có video | Bấm Đăng TikTok và Đăng YouTube | Cảnh báo cần chọn video; không mở browser | — |
| UP-002 | P1 / E | Có video, không cookie TikTok | Bấm đăng TikTok, hủy hộp thoại chọn file | Báo cần cookie; không tạo worker | — |
| UP-003 | P1 / E | Có video, cookie TikTok sai/hết hạn | Bấm đăng | Browser/worker báo lỗi login; nút upload bật lại sau khi xong | — |
| UP-004 | P1 / I | ENV-14 TikTok cookie hợp lệ | Đăng video thử nghiệm với privacy Private nếu hỗ trợ | Uploader hoàn tất, hiện thành công và trạng thái/video được cập nhật | — |
| UP-005 | P1 / F | TikTok uploader, caption có Unicode/hashtags | Đăng hoặc đi tới bước preview trước submit | Caption không mất dấu, không vượt giới hạn, đúng privacy | — |
| UP-006 | P1 / E | TikTok cookie bị từ chối hoặc selector UI nền tảng đổi | Thực hiện upload staging | Lỗi có log; browser đóng/cleanup; không báo thành công giả | — |
| UP-007 | P1 / E | Có video, cookie YouTube mặc định không tồn tại; hủy chọn | Bấm đăng YouTube | Báo cần cookie; không gọi uploader | — |
| UP-008 | P1 / I | ENV-14 YouTube phiên đăng nhập/cookie hợp lệ | Upload video thử với Private/Unlisted | Video xuất hiện trên đúng tài khoản; URL hoặc trạng thái thành công đúng | — |
| UP-009 | P1 / F | Bật metadata mặc định/tag | Upload thử | Title, description, tags và child-directed setting đúng với form/uploader | — |
| UP-010 | P1 / F | Cấu hình YouTube privacy lần lượt Public, Private, Unlisted | Kiểm tra qua preview/đăng staging | Lựa chọn đúng được truyền đến Studio | — |
| UP-011 | P1 / N | Schedule bật, thời gian hợp lệ tương lai | Đăng staging có lịch | Video được lên lịch đúng ngày/giờ/timezone dự kiến | — |
| UP-012 | P1 / E | Schedule bật nhưng ngày/giờ quá khứ hoặc thiếu | Lưu cấu hình/thực hiện upload | Bị validation hoặc nền tảng từ chối rõ ràng; không đánh dấu thành công | — |
| UP-013 | P1 / F | Bật/tắt auto-upload TikTok trong cấu hình tải | Tải video test phù hợp | Auto upload chỉ chạy khi bật; dùng đúng cookie/privacy/delay | — |
| UP-014 | P1 / F | Bật/tắt auto-upload YouTube trong cấu hình tải | Tải video test phù hợp | Auto upload chỉ chạy khi bật; schedule và tags được truyền đúng | — |
| UP-015 | P1 / E | Upload đang chạy, mô phỏng đóng browser/mất mạng | Quan sát worker | Lỗi được báo; UI trở lại; không để nút disabled vĩnh viễn | — |
| UP-016 | P2 / R | Upload thành công rồi upload lỗi lần kế | Thực hiện hai lượt tách biệt | Status lượt trước không làm lượt sau báo thành công sai; bảng phản ánh đúng nền tảng | — |

## 10. License và lượt dùng thử

**Lưu ý:** license/trial ghi vào `~/.omnigrab_license.dat` và `~/.omnigrab_trial.dat`. Kiểm thử phải dùng profile/Windows user riêng hoặc sao lưu và khôi phục các file này; không sửa dữ liệu license cá nhân.

| ID | Ưu tiên / loại | Tiền điều kiện | Bước thực hiện | Kết quả mong đợi | Pass |
|---|---|---|---|---|---|
| LIC-001 | P1 / F | Profile sạch chưa có license/trial | Khởi chạy và xem status bar | Hiển thị số lượt trial ban đầu theo cấu hình hệ thống | — |
| LIC-002 | P1 / N | Dialog kích hoạt mở | Gửi chuỗi rỗng | Cảnh báo nhập mã; không lưu key | — |
| LIC-003 | P1 / E | Dialog kích hoạt mở | Nhập chuỗi không phải Base64 | Báo mã không hợp lệ; app không crash | PASS* |
| LIC-004 | P1 / E | Tạo bundle JSON thiếu payload/sig | Mã hóa Base64 và nhập | Báo cấu trúc lỗi; không lưu key | — |
| LIC-005 | P1 / E | Bundle có payload nhưng chữ ký sai | Nhập key | Từ chối chữ ký; không cấp PRO | — |
| LIC-006 | P1 / E | Key có chữ ký test hợp lệ nhưng MID khác | Nhập key | Báo key không thuộc máy; không lưu thành license hoạt động | — |
| LIC-007 | P1 / E | Key test ký hợp lệ, exp trước ngày hiện tại | Nhập key | Báo hết hạn | — |
| LIC-008 | P1 / E | Key test exp sai định dạng | Nhập key | Báo định dạng ngày không hợp lệ | — |
| LIC-009 | P1 / F | Key staging hợp lệ, MID đúng, chưa hết hạn | Kích hoạt rồi restart | Hiển thị PRO; key được xác thực offline sau restart | — |
| LIC-010 | P1 / F | Trial còn ít nhất 1 lượt | Tải một video thành công | Trial giảm đúng một lượt sau item thành công | — |
| LIC-011 | P1 / F | Trial còn lượt | Tải một URL thất bại | Lượt trial không bị trừ nếu không tải thành công | — |
| LIC-012 | P1 / N | Trial = 0, không license | Bấm tải; sau đó mở dialog activation | Tải bị chặn và activation được đề nghị; các trang khác không crash | — |

## 11. Đóng gói, vận hành và hồi quy

| ID | Ưu tiên / loại | Tiền điều kiện | Bước thực hiện | Kết quả mong đợi | Pass |
|---|---|---|---|---|---|
| REL-001 | P0 / I | Môi trường build sạch, dependencies cài đủ | Build theo `build.bat`/PyInstaller | Build hoàn tất, exe khởi chạy | — |
| REL-002 | P1 / I | Có bản PyInstaller | Chạy exe trên máy không có Python | UI mở và tài nguyên assets/public key được tìm đúng | — |
| REL-003 | P1 / I | Có bản build, ffmpeg/ffprobe được đóng gói hoặc cài cạnh app | Thực hiện tải, MP3 và một tác vụ video cần ffmpeg | Binary được resolve đúng trong môi trường frozen | — |
| REL-004 | P1 / I | Build có module faster-whisper/playwright/f2 | Mở Studio, quét Douyin, mở uploader | Import/resource không thiếu; nếu browser runtime chưa cài thì báo hướng xử lý | — |
| REL-005 | P1 / F | Bản app chạy bình thường | Đóng app khi không có tác vụ | Thoát sạch; cấu hình và cửa sổ được lưu | — |
| REL-006 | P1 / E | Đang tải/quét/dubbing/upload | Thử đóng cửa sổ | Có hành vi an toàn: xác nhận/dừng/đợi; không để process treo hoặc output hỏng ngoài dự kiến | — |
| REL-007 | P1 / F | Bật debugger/tracing trong môi trường dev | Khởi chạy (chỉ kiểm tra theo policy nội bộ) | Security check phản ứng như thiết kế; ghi rõ tác động tới debug/dev | — |
| REL-008 | P1 / E | Thiếu public key trong bản build test | Mở phần license | Lỗi được thông báo khi kiểm tra license, app không crash toàn bộ | — |
| REL-009 | P2 / F | Chạy source ở thư mục path có dấu/Unicode | Khởi động, chọn output, tải video ngắn | Đường dẫn tài nguyên và FFmpeg xử lý đúng Unicode | — |
| REL-010 | P2 / F | Mạng chập chờn | Chạy một scan và một download riêng biệt | Không chạy song song state sai; mỗi worker cleanup sau lỗi | — |
| REL-011 | P1 / R | Hoàn tất một lượt tải, scan và Studio | Chuyển qua lại các trang; kiểm tra menu/status | Không treo, log hiển thị, button state khớp trạng thái tác vụ | — |
| REL-012 | P1 / F | Có log lỗi tải | Dùng chức năng xuất danh sách lỗi | File được tạo, chứa URL và lỗi tương ứng, không chứa cookie/secret | — |

## 12. Luồng kết hợp và kiểm thử biên bổ sung

Các test trong phần này tập trung vào tương tác giữa các tính năng, đầu vào sát biên và lỗi có thể làm trạng thái UI/batch không đồng nhất. Dùng video mẫu ngắn để giảm thời gian chạy; chỉ chạy upload thật trên tài khoản staging.

### 12.1. Biên URL và dữ liệu đầu vào

| ID | Ưu tiên / loại | Tiền điều kiện | Bước thực hiện | Kết quả mong đợi | Pass |
|---|---|---|---|---|---|
| PAR-013 | P1 / N | Trang Tải link | Dán `https://tiktok.com.evil.example/video/123` và `https://not-tiktok.com/video/123` | Cả hai bị từ chối vì hostname không thuộc domain nền tảng được hỗ trợ; không bắt đầu tải | FAIL* |
| PAR-014 | P1 / N | Trang Tải link | Dán URL của domain khác có query chứa chuỗi `https://www.tiktok.com/` | Không coi domain trong query là hostname nền tảng; không tải URL ngoài danh sách hỗ trợ | FAIL* |
| PAR-015 | P2 / N | Trang Tải link | Dán URL hợp lệ theo sau bởi dấu ngoặc/dấu câu tiếng Việt, Trung Quốc và khoảng trắng zero-width | Chỉ URL hợp lệ được trích; ký tự phân cách cuối không bị đưa vào URL; không tạo URL trùng | — |
| PAR-016 | P2 / E | Có file rỗng, file chỉ có header CSV, file không tồn tại và đường dẫn trỏ tới thư mục | Thử nhập từng trường hợp | File rỗng/CSV không URL được thông báo không có liên kết; file thiếu/không đọc được báo lỗi rõ; không crash và nội dung ô nhập cũ không bị xóa | — |
| PAR-017 | P2 / F | Có file Latin-1 chứa URL ASCII và văn bản có dấu mã hóa Latin-1 | Nhập file | Fallback encoding đọc được file và trích URL đúng | PASS* |

### 12.2. Tải batch, trạng thái và tài nguyên

| ID | Ưu tiên / loại | Tiền điều kiện | Bước thực hiện | Kết quả mong đợi | Pass |
|---|---|---|---|---|---|
| DL-020 | P1 / N | Một URL hợp lệ lặp lại nhiều lần trong ô nhập | Bắt đầu batch và quan sát tổng số item | Parser loại URL trùng trước khi tạo batch; cùng một URL không bị tải nhiều lần | — |
| DL-021 | P1 / F | Có video hợp lệ và file cùng tên đã tồn tại | Tải lại cùng video ít nhất hai lần | Không xóa/ghi đè file ngoài dự kiến; tên file, resume hoặc ghi đè theo hành vi yt-dlp được ghi nhận chính xác | — |
| DL-022 | P1 / I | Có URL tạo được MP3; FFmpeg khả dụng | Bật chỉ âm thanh; tải; kiểm tra bằng media player hoặc ffprobe | File đầu ra có codec/container MP3, có âm thanh, không được báo có video thành phẩm | — |
| DL-023 | P1 / E | Có batch gồm URL thành công và URL lỗi; mạng đủ để hoàn tất ít nhất một URL | Tải batch; chờ kết thúc; xuất danh sách lỗi | Thành công/thất bại theo từng URL và tổng batch khớp; export chỉ chứa URL lỗi; có thể bắt đầu batch tiếp theo | — |
| DL-024 | P1 / N | Đang tải batch nhiều URL; có item đang chạy và item chờ | Bấm Dừng một lần; không bấm liên tiếp; chờ worker hoàn tất | Không tạo nhiều worker dừng; kết quả đã xong được giữ, hàng chờ được tính là bỏ qua; các nút/progress trở về trạng thái sẵn sàng | — |
| DL-025 | P1 / F | Thử tải một URL video trên nền tảng không thuộc cấu hình riêng TikTok/Douyin/Facebook (nếu có nguồn test được phép) | Tải video | Tùy chọn yt-dlp mặc định được dùng; file được ghép thành MP4 nếu cần FFmpeg; lỗi nguồn ngoài được báo theo item | — |
| DL-026 | P2 / N | Tiêu đề video chứa emoji, tiếng Việt/Trung, dấu nháy và ký tự cấm trong tên file Windows | Tải video | Tên file hợp lệ theo quy tắc template/yt-dlp, không làm hỏng đường dẫn hoặc dừng batch | — |

### 12.3. Quét, chọn và xuất dữ liệu

| ID | Ưu tiên / loại | Tiền điều kiện | Bước thực hiện | Kết quả mong đợi | Pass |
|---|---|---|---|---|---|
| SCAN-021 | P1 / F | Có bảng kết quả với cả dòng đạt và không đạt một bộ lọc | Bật lọc; bấm Chọn tất cả; sau đó Bỏ chọn tất cả | Chọn tất cả chỉ chọn các dòng đang hiển thị; Bỏ chọn tất cả bỏ chọn cả dòng ẩn lẫn hiện; bộ đếm chọn cập nhật ngay | — |
| SCAN-022 | P1 / N | Có video có lượt xem/lượt thích đúng bằng ngưỡng, thấp hơn 1 và cao hơn 1 | Đặt ngưỡng tương ứng | Giá trị bằng ngưỡng được giữ lại; thấp hơn bị ẩn; nhiều ngưỡng kết hợp dùng điều kiện AND | PASS* |
| SCAN-023 | P1 / N | Có video có ngày đúng cutoff, trước cutoff một ngày và metadata ngày rỗng | Thử lần lượt 3/7/30 ngày | Video đúng cutoff được giữ; cũ hơn và ngày không parse được bị ẩn; chọn “Tất cả” khôi phục mọi dòng | PASS* |
| SCAN-024 | P2 / R | Quét xong, bật bộ lọc làm ẩn vài dòng, rồi đổi URL và quét lại | So sánh bảng, số dòng, checkbox, bộ đếm và CSV | Kết quả cũ không còn lẫn vào lần quét mới; bộ lọc đang chọn chỉ áp dụng cho tập kết quả hiện tại; CSV phản ánh đúng các dòng được xuất theo quy tắc UI | — |

### 12.4. Studio và khôi phục kịch bản

| ID | Ưu tiên / loại | Tiền điều kiện | Bước thực hiện | Kết quả mong đợi | Pass |
|---|---|---|---|---|---|
| DUB-022 | P1 / F | Có video và ít nhất hai segment; sửa bản dịch một segment | Xuất SRT rồi chạy lồng tiếng từ kịch bản đã sửa | SRT dùng bản dịch đã sửa; file dubbing cũng dùng đúng nội dung đã duyệt, mốc thời gian không đổi ngoài điều chỉnh pacing | — |
| DUB-023 | P1 / F | Có video đã lưu sidecar kịch bản JSON hoặc SRT | Đóng/mở Studio, nạp lại đúng video | Sidecar liên quan được tìm và nạp; số câu, timestamp, lời gốc/bản dịch đúng; không nhân đôi hàng | — |
| DUB-024 | P1 / E | Video có tiếng nhưng không có lời nói nhận diện được | Chạy bóc tách | Báo không phát hiện giọng nói hoặc kết quả rỗng có cảnh báo; không tạo file lồng tiếng thành công giả | — |
| DUB-025 | P1 / E | Đang chạy bóc tách hoặc lồng tiếng trên video mẫu đủ dài | Bấm Dừng, xác nhận; kiểm tra lại Studio và file tạm | UI không còn báo đang chạy và có thể thao tác lại; file đầu ra dở dang không được nhận diện là thành phẩm hợp lệ; ghi nhận nếu tiến trình con/tác vụ FFmpeg còn sót | — |
| DUB-026 | P2 / F | Có transcript đã dịch; tồn tại video gốc và file `_dubbed` cùng thư mục | Nạp lần lượt video gốc rồi video `_dubbed`; quay lại video gốc | Studio nhận diện video liên quan theo tên, giữ bảng khi phù hợp; đổi sang video không liên quan thì nạp sidecar tương ứng hoặc xóa bảng cũ | — |

### 12.5. Tích hợp tải → lồng tiếng → upload và cấu hình tự động

| ID | Ưu tiên / loại | Tiền điều kiện | Bước thực hiện | Kết quả mong đợi | Pass |
|---|---|---|---|---|---|
| FLOW-001 | P1 / F | Batch một video; tắt auto-dub và auto-upload | Tải xong | Chỉ video gốc được tạo; không gọi Whisper, Gemini hay uploader; item được đánh dấu thành công | — |
| FLOW-002 | P1 / I | Batch một video MP4; bật auto-dub, tắt upload; dependencies/mạng TTS sẵn sàng | Tải video | Sau tải, tạo file `_dubbed`; log phân biệt lỗi tải và lỗi dubbing; batch hoàn tất và UI được giải phóng | — |
| FLOW-003 | P1 / E | Bật auto-dub; cố ý làm Whisper/TTS thất bại sau khi tải thành công | Tải video | Download vẫn được ghi nhận đúng; lỗi dubbing được log; không tuyên bố có file dubbed nếu file không tồn tại/hỏng | — |
| FLOW-004 | P1 / I | Tắt auto-dub; chỉ bật auto-upload TikTok; dùng video/cookie staging | Tải một video test | Upload chỉ chạy sau khi tải thành công; dùng video gốc, cookie và privacy đã cấu hình; thất bại upload không đổi kết quả tải thành lỗi | — |
| FLOW-005 | P1 / I | Bật auto-dub và auto-upload TikTok; staging đã sẵn sàng | Tải một video test | TikTok nhận file dubbed sau khi dubbing thành công; log xác định đúng đường dẫn được gửi | — |
| FLOW-006 | P1 / I | Bật auto-upload YouTube, tắt TikTok; có cookie staging | Tải một video test | YouTube upload chạy một lần sau tải/dub theo cấu hình; title/description/tags/privacy/schedule khớp cấu hình; không mở thêm upload TikTok | — |
| FLOW-007 | P1 / I | Bật cả auto-upload TikTok và YouTube; tài khoản staging và cookie cho cả hai | Tải một video test | Cả hai nền tảng được gọi theo thứ tự thực tế của pipeline; trạng thái thành công/thất bại từng nền tảng độc lập; không báo upload thành công chỉ vì tải thành công | — |
| FLOW-008 | P1 / E | Bật cả TikTok và YouTube; làm TikTok upload thất bại có kiểm soát | Chạy một video test | Lỗi TikTok được log; nếu pipeline quy định tiếp tục, YouTube vẫn được thử; kết quả tải gốc không bị đổi thành thất bại | — |
| FLOW-009 | P1 / N | Bật auto-upload TikTok cho batch hai video; cấu hình delay nhỏ nhất UI cho phép | Tải hai video test trên staging; ghi thời điểm bắt đầu upload | Mỗi upload dùng đúng caption/privacy; khoảng cách giữa các lượt tuân theo cấu hình thực tế; không gửi đồng thời ngoài ý muốn | — |
| FLOW-010 | P1 / F | Bật auto-upload YouTube và schedule; nhập ngày/giờ hợp lệ; restart ứng dụng | Mở lại cấu hình rồi tải video staging | Trạng thái bật/tắt, privacy, tags, ngày/giờ được lưu và truyền đúng; timezone hiển thị/đăng được ghi rõ | — |
| FLOW-011 | P1 / E | Bật auto-upload nhưng cookie TikTok hoặc YouTube đã bị xóa khỏi đĩa | Chạy một lượt tải test | Lượt tải vẫn được xử lý; uploader báo cookie không dùng được, không crash hoặc báo đăng thành công; UI vẫn cho nhập cookie mới | — |
| FLOW-012 | P1 / N | Chọn chế độ chỉ MP3 và bật auto-dub/upload | Bắt đầu tải MP3 test | Không khởi tạo pipeline video dubbing/upload cho đầu ra âm thanh; lỗi/không hỗ trợ được báo rõ thay vì cố upload file âm thanh như video | — |

### 12.6. Cookie, bí mật và trạng thái giấy phép

| ID | Ưu tiên / loại | Tiền điều kiện | Bước thực hiện | Kết quả mong đợi | Pass |
|---|---|---|---|---|---|
| SEC-001 | P1 / F | Dùng API key thử nghiệm và cookie staging; bật log chi tiết nếu có | Nạp cookie, chạy một thao tác lỗi xác thực/dịch, xuất log lỗi | Log không chứa giá trị cookie, Gemini API key, access token hoặc nội dung nhạy cảm; bug report chỉ đính kèm log đã rà soát | — |
| SEC-002 | P1 / N | Cookie rỗng, sai định dạng, hết hạn; có bản hợp lệ để khôi phục | Nạp từng file, chạy thử, sau đó thay bằng cookie hợp lệ | Cookie rỗng/sai/hết hạn không gây crash hoặc báo thành công; có thể thay file và chạy lại mà không restart ứng dụng | PASS* |
| LIC-013 | P1 / N | Profile test; file trial có JSON lỗi hoặc giá trị `used` ngoài khoảng hợp lệ | Mở ứng dụng, kiểm tra status và thử tải trong môi trường test | Không crash; dữ liệu hỏng phải được phát hiện/báo rõ và không âm thầm cấp lại lượt dùng thử. Code hiện tại có thể fallback về 10 lượt khi không đọc được file; nếu quan sát thấy, ghi nhận là lỗi tính toàn vẹn license | — |
| LIC-014 | P1 / R | Trial còn đúng 1 lượt trong profile test | Tải một URL lỗi, rồi tải một URL thành công | URL lỗi không trừ lượt; URL tải thành công trừ đúng 1 và status bar cập nhật còn 0 | — |
| LIC-015 | P1 / N | License hợp lệ staging có ngày hết hạn hôm nay và license đã hết hạn hôm qua | Kiểm tra license theo ngày hệ thống hiện tại | Quy tắc hết hạn theo ngày nhất quán; key hết hạn bị từ chối, key còn hạn không bị từ chối sớm | — |

## 13. Kiểm tra chấp nhận phát hành

Phát hành khi tất cả P0 và P1 áp dụng đều Đạt, hoặc có ngoại lệ được chủ sản phẩm chấp thuận và ghi lại. Không tính test cần tài khoản/cookie/API key chưa được cấp là lỗi; đánh dấu **Bị chặn** kèm lý do. Với nền tảng thay đổi giao diện/API, lưu screenshot/log đã che thông tin nhạy cảm.

### Biểu mẫu kết quả

| ID | Trạng thái | Build / môi trường | Kết quả thực tế | Bug ID / bằng chứng | Tester / ngày |
|---|---|---|---|---|---|
|  | Chưa chạy |  |  |  |  |

### Mẫu bug report

- **Tiêu đề:** `[ID] Mô tả ngắn`
- **Build / OS:**
- **Tiền điều kiện:** (che cookie, token, API key)
- **Các bước tái hiện:**
- **Kết quả mong đợi:**
- **Kết quả thực tế:**
- **Tần suất:** luôn luôn / thường xuyên / ngẫu nhiên / một lần
- **Bằng chứng:** screenshot hoặc log đã làm sạch dữ liệu nhạy cảm
- **Mức độ:** blocker / nghiêm trọng / trung bình / thấp
