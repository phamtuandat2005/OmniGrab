"""
core/youtube_uploader.py — Module Tự động Đăng & Hẹn giờ YouTube Shorts bằng Playwright Persistent Profile.

Đặc tả:
- Sử dụng launch_persistent_context lưu vĩnh viễn phiên đăng nhập Google vào profiles/youtube_profile.
- Nếu phiên chưa đăng nhập: Mở cửa sổ cho người dùng đăng nhập 1 lần duy nhất (hoặc nạp cookie nếu có),
  tự động lưu lại phiên cho mọi lần sau không bị văng đăng nhập.
- Không cần Google Cloud hay YouTube Data API Key / client_secret.json.
- Tự động điền Tiêu đề (gắn #Shorts), Mô tả chuẩn SEO, chọn "Không dành cho trẻ em".
- Hỗ trợ Chế độ hiển thị: Công khai (Public), Riêng tư (Private), Không công khai (Unlisted).
- Hỗ trợ Lên lịch hẹn giờ (Schedule) xuất bản video trên YouTube Studio.
- Tích hợp QThread worker để xử lý trong nền không làm đơ giao diện người dùng.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger("OmniGrab.YouTubeUploader")


def _resolve_config_path(file_path: Optional[str], default_name: str) -> str:
    """Xác định đường dẫn file cấu hình tuyệt đối cạnh thư mục gốc app."""
    if file_path and os.path.isabs(file_path):
        return file_path

    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target = os.path.join(base_dir, file_path or default_name)
    return target


def parse_netscape_cookies(cookie_file_path: str) -> List[Dict[str, Any]]:
    """
    Đọc và chuyển đổi file cookies.txt (.txt Netscape hoặc .json) sang chuẩn Playwright.
    Hỗ trợ định dạng xuất ra từ tiện ích 'Get cookies.txt LOCALLY' trên Chrome/Edge.
    """
    cookies: List[Dict[str, Any]] = []
    if not cookie_file_path or not os.path.exists(cookie_file_path):
        return cookies

    try:
        with open(cookie_file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read().strip()
    except Exception as e:
        logger.warning(f"Không thể đọc file cookie: {e}")
        return cookies

    if not content:
        return cookies

    # 1. Định dạng JSON
    if content.startswith("[") or content.startswith("{"):
        try:
            data = json.loads(content)
            raw_list = data if isinstance(data, list) else [data]
            clean_cookies = []
            for item in raw_list:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                value = item.get("value")
                if not name or value is None:
                    continue
                domain = item.get("domain", ".youtube.com")
                c_dict: Dict[str, Any] = {
                    "name": str(name),
                    "value": str(value),
                    "domain": str(domain),
                    "path": str(item.get("path", "/")),
                    "secure": bool(item.get("secure", False)),
                    "httpOnly": bool(item.get("httpOnly", False)),
                }
                if "sameSite" in item and item["sameSite"] in ("Strict", "Lax", "None"):
                    c_dict["sameSite"] = item["sameSite"]
                exp = item.get("expirationDate") or item.get("expires")
                if exp:
                    try:
                        c_dict["expires"] = float(exp)
                    except Exception:
                        pass
                clean_cookies.append(c_dict)
            if clean_cookies:
                return clean_cookies
        except Exception:
            pass

    # 2. Định dạng Netscape (.txt)
    for line in content.splitlines():
        line = line.strip()
        if not line or (line.startswith("#") and not line.startswith("#HttpOnly_")):
            continue

        http_only = False
        if line.startswith("#HttpOnly_"):
            line = line[len("#HttpOnly_"):]
            http_only = True

        parts = line.split("\t")
        if len(parts) >= 7:
            domain, flag, path, secure, expiration, name, value = parts[:7]
            try:
                exp = float(expiration)
            except ValueError:
                exp = -1

            cookie_dict: Dict[str, Any] = {
                "name": name,
                "value": value,
                "domain": domain,
                "path": path,
                "secure": secure.upper() == "TRUE",
                "httpOnly": http_only,
            }
            if exp > 0:
                cookie_dict["expires"] = exp
            cookies.append(cookie_dict)

    return cookies


def generate_youtube_metadata(
    script_content: str,
    api_key: str = "",
    video_title: str = "",
) -> Tuple[str, str, List[str]]:
    """
    Dùng Gemini AI để tạo Tiêu đề (<90 ký tự gắn #Shorts), Mô tả và Thẻ Tags chuẩn SEO YouTube.
    """
    clean_title = (video_title or "Video Lồng tiếng AI").strip()
    if clean_title.lower().endswith((".mp4", ".mkv", ".mov")):
        clean_title = os.path.splitext(clean_title)[0]

    # Đảm bảo có gắn #Shorts
    shorts_tag = "#Shorts"
    if shorts_tag.lower() not in clean_title.lower():
        clean_title = f"{clean_title} {shorts_tag}"

    clean_key = (api_key or "").strip()
    if not clean_key:
        default_tags = ["Shorts", "AI", "ReviewPhim", "PhimHay", "OmniGrab"]
        default_desc = f"{clean_title}\n\nVideo được xử lý và lồng tiếng tự động bởi OmniGrab AI.\n#Shorts #AI #PhimHay"
        return clean_title[:100], default_desc, default_tags

    headers = {"Content-Type": "application/json"}
    prompt_text = (
        f"Bạn là chuyên gia SEO YouTube số 1. Dựa trên nội dung sau:\n"
        f"Tên video: '{clean_title}'\n"
        f"Kịch bản/nội dung: '{script_content[:400] if script_content else clean_title}'\n\n"
        f"Hãy tạo siêu dữ liệu YouTube Shorts định dạng JSON chuẩn với 3 trường:\n"
        f"1. 'title': Tiêu đề giật tít, tò mò, bắt mắt KHÔNG quá 90 ký tự và BẮT BUỘC có chứa hashtag #Shorts.\n"
        f"2. 'description': Đoạn mô tả ngắn 2-3 câu tóm tắt nội dung kèm lời kêu gọi Like/Sub và 3-5 hashtag.\n"
        f"3. 'tags': Mảng từ 5-8 từ khóa/thẻ tag liên quan nhất.\n"
        f"Chỉ trả về JSON thuần túy, không có giải thích."
    )

    candidate_models = (
        "gemini-2.5-flash",
        "gemini-1.5-flash",
        "gemini-flash-latest",
        "gemini-3.5-flash-lite",
    )

    for model_name in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={clean_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 512},
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates and "content" in candidates[0]:
                    parts = candidates[0]["content"].get("parts", [])
                    if parts:
                        raw_text = parts[0].get("text", "").strip()
                        if raw_text.startswith("```"):
                            raw_text = raw_text.strip("`")
                            if raw_text.lower().startswith("json"):
                                raw_text = raw_text[4:].strip()
                        meta = json.loads(raw_text)
                        t = str(meta.get("title", clean_title)).strip()
                        if "#shorts" not in t.lower():
                            t = f"{t} #Shorts"
                        d = str(meta.get("description", f"{clean_title}\n\n#Shorts #Review")).strip()
                        tags_list = meta.get("tags", [])
                        if not isinstance(tags_list, list):
                            tags_list = ["Shorts", "AI", "Review"]
                        return t[:100], d, [str(x) for x in tags_list[:15]]
        except Exception:
            continue

    default_tags = ["Shorts", "AI", "ReviewPhim", "PhimHay"]
    default_desc = f"{clean_title}\n\nVideo được xử lý và lồng tiếng tự động bởi OmniGrab AI.\n#Shorts #PhimHay"
    return clean_title[:100], default_desc, default_tags


def split_title_and_description(raw_text: str) -> Tuple[str, str]:
    """
    Tách thông minh Tiêu đề (Title) và Mô tả (Description) từ văn bản thô:
    - Tiêu đề (Title): Chỉ lấy câu đầu tiên (loại bỏ các hashtag), cắt ngắn tối đa 70 ký tự + thêm đuôi ' #Shorts'.
      Đảm bảo tổng chiều dài tiêu đề luôn dưới 85 ký tự (an toàn tuyệt đối dưới ngưỡng 100 của YouTube).
    - Mô tả (Description): Lấy toàn bộ nội dung gốc (gồm đầy đủ câu từ, lời kêu gọi Like/Đăng ký và các hashtag).
    """
    raw_content = (raw_text or "").strip()
    if not raw_content:
        return ("#Shorts", "")

    # Lọc bỏ hashtag để lấy câu tiêu đề thuần túy
    clean_text = re.sub(r'#\S+', '', raw_content).strip()
    # Lấy câu đầu tiên (ngăn cách bởi dấu chấm, xuống dòng hoặc dấu chấm than)
    first_sentence = re.split(r'[.\n!]', clean_text)[0].strip()
    if not first_sentence:
        first_sentence = clean_text[:65]
    if len(first_sentence) > 65:
        first_sentence = first_sentence[:65].rsplit(' ', 1)[0]
    if not first_sentence:
        first_sentence = "Video"

    # Gắn đuôi #Shorts vào tiêu đề
    final_title = f"{first_sentence} #Shorts"[:85]

    # Toàn bộ nội dung dài đưa vào Mô tả
    final_desc = raw_content.strip()

    return final_title, final_desc


def extract_thumbnail_from_video(video_path: str, output_thumb_path: Optional[str] = None, at_second: int = 4) -> Optional[str]:
    """
    Trích xuất 1 khung hình sắc nét từ video tại thời điểm at_second để làm thumbnail.
    """
    if not output_thumb_path:
        base_name = os.path.splitext(video_path)[0]
        output_thumb_path = f"{base_name}_thumb.jpg"
    
    # Định dạng timestamp hh:mm:ss
    time_str = f"00:00:{at_second:02d}"

    ff_bin = "ffmpeg"
    if not shutil.which("ffmpeg"):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidate = os.path.join(base_dir, "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
        if os.path.isfile(candidate):
            ff_bin = candidate
        elif os.path.isfile("ffmpeg.exe"):
            ff_bin = os.path.abspath("ffmpeg.exe")

    cmd = [
        ff_bin, "-y",
        "-ss", time_str,
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        output_thumb_path
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        if os.path.exists(output_thumb_path) and os.path.getsize(output_thumb_path) > 0:
            return output_thumb_path
    except Exception as e:
        # Fallback thử lại tại giây 01 nếu video ngắn hơn 4s
        try:
            cmd_fallback = [
                ff_bin, "-y",
                "-ss", "00:00:01",
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",
                output_thumb_path
            ]
            subprocess.run(cmd_fallback, capture_output=True, check=True)
            if os.path.exists(output_thumb_path) and os.path.getsize(output_thumb_path) > 0:
                return output_thumb_path
        except Exception:
            pass
        print(f"[YouTube] Không thể trích xuất thumbnail bằng FFmpeg: {e}")
    return None




class YouTubeUploader:
    """
    Tự động hóa đăng video lên YouTube Studio bằng Playwright với Persistent Browser Profile (không bị văng đăng nhập).
    """

    def __init__(
        self,
        cookies_file_path: Optional[str] = "youtube_cookies.txt",
        profile_dir: str = "profiles/youtube_profile",
        log_callback: Optional[Callable[[str], None]] = None,
        headless: bool = False,
    ) -> None:
        self.cookies_file_path = _resolve_config_path(cookies_file_path, "youtube_cookies.txt") if cookies_file_path else None
        self.profile_dir = _resolve_config_path(profile_dir, "profiles/youtube_profile")
        os.makedirs(self.profile_dir, exist_ok=True)
        self.log_callback = log_callback
        self.headless = headless

    def _log(self, msg: str) -> None:
        logger.info(msg)
        print(msg)
        if self.log_callback:
            try:
                self.log_callback(msg)
            except Exception:
                pass

    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str = "",
        privacy_status: str = "public",
        schedule_date: Optional[str] = None,   # Định dạng: "DD/MM/YYYY" hoặc "YYYY-MM-DD"
        schedule_time: Optional[str] = None,   # Định dạng: "HH:MM" (Ví dụ: "19:00")
        scheduled_time: Optional[Any] = None,  # Hỗ trợ truyền datetime.datetime cũ
        tags: Optional[List[str]] = None,
        custom_thumbnail: Optional[str] = None,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> Dict[str, Any]:
        """
        Tự động tải video lên YouTube Studio với Persistent Browser Profile.
        - privacy_status: 'public', 'private', hoặc 'unlisted'
        - schedule_date: Ngày hẹn giờ (nếu có)
        - schedule_time: Giờ hẹn giờ (nếu có)
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Không tìm thấy file video: {video_path}")

        # Hỗ trợ tham số datetime cũ nếu có truyền
        if scheduled_time is not None:
            if isinstance(scheduled_time, (datetime.datetime, datetime.date)):
                schedule_date = scheduled_time.strftime("%d/%m/%Y")
                if isinstance(scheduled_time, datetime.datetime):
                    schedule_time = scheduled_time.strftime("%H:%M")

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise ImportError(
                "Chưa cài đặt thư viện Playwright. Vui lòng chạy lệnh:\n"
                "pip install playwright && playwright install chromium"
            ) from e

        if progress_callback:
            try:
                progress_callback(10)
            except Exception:
                pass

        self._log(f"[YouTube] 🚀 Khởi chạy trình duyệt Playwright với Persistent Profile ({os.path.basename(self.profile_dir)})...")

        with sync_playwright() as p:
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ]

            # Sử dụng persistent context để lưu vĩnh viễn phiên đăng nhập Google
            context = None
            try:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=self.profile_dir,
                    channel="chrome",
                    headless=self.headless,
                    no_viewport=True,
                    args=launch_args,
                )
            except Exception:
                try:
                    context = p.chromium.launch_persistent_context(
                        user_data_dir=self.profile_dir,
                        channel="msedge",
                        headless=self.headless,
                        no_viewport=True,
                        args=launch_args,
                    )
                except Exception:
                    try:
                        context = p.chromium.launch_persistent_context(
                            user_data_dir=self.profile_dir,
                            headless=self.headless,
                            no_viewport=True,
                            args=launch_args,
                        )
                    except Exception as e:
                        raise Exception(f"Không thể khởi chạy Chrome/Edge với Persistent Context: {e}")

            # Nếu có file cookie, nạp bổ sung cookie vào context
            if self.cookies_file_path and os.path.exists(self.cookies_file_path):
                try:
                    cookies = parse_netscape_cookies(self.cookies_file_path)
                    if cookies:
                        context.add_cookies(cookies)
                except Exception:
                    pass

            page = context.pages[0] if context.pages else context.new_page()

            # 1. Mở YouTube Studio
            self._log("[YouTube] 🌐 Đang mở YouTube Studio (https://studio.youtube.com)...")
            page.goto("https://studio.youtube.com", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)

            # Nếu bị yêu cầu đăng nhập, cho người dùng 90 giây để đăng nhập thủ công trên cửa sổ trình duyệt
            if "accounts.google.com" in page.url or "signin" in page.url:
                self._log("[YouTube] ⚠ Phát hiện yêu cầu đăng nhập. Vui lòng đăng nhập tài khoản Google trên cửa sổ trình duyệt...")
                start_login_wait = time.time()
                logged_in = False
                while time.time() - start_login_wait < 90:
                    if "studio.youtube.com" in page.url and "signin" not in page.url and "accounts.google.com" not in page.url:
                        logged_in = True
                        break
                    page.wait_for_timeout(2000)

                if not logged_in:
                    context.close()
                    raise Exception("Chưa hoàn tất đăng nhập Google trên trình duyệt. Vui lòng thử lại sau khi đăng nhập.")
                self._log("[YouTube] ✅ Đăng nhập thành công! Phiên duyệt đã được tự động lưu vĩnh viễn vào máy.")

            if progress_callback:
                try:
                    progress_callback(30)
                except Exception:
                    pass

            # 1. Tự động đóng các popup chào mừng/tiếp tục của YouTube Studio nếu có
            try:
                for btn_text in ["Tiếp tục", "Continue", "Đóng", "Close", "Bỏ qua", "Dismiss"]:
                    btn = page.locator(f'ytcp-button:has-text("{btn_text}"), button:has-text("{btn_text}")')
                    if btn.count() > 0 and btn.first.is_visible():
                        btn.first.click()
                        page.wait_for_timeout(1000)
            except Exception:
                pass

            # 2. KÍCH HOẠT HỘP THOẠI TẢI VIDEO LÊN
            self._log("[YouTube] Đang kích hoạt hộp thoại tải video lên...")
            page.wait_for_timeout(2000)

            # Ưu tiên 1: Nếu có nút to "Tải video lên" ở giữa trang (kênh chưa có video)
            center_btn = page.locator('#upload-button, ytcp-button#upload-button')
            if center_btn.count() > 0 and center_btn.first.is_visible():
                self._log("[YouTube] Bấm nút Tải video lên ở giữa Dashboard...")
                center_btn.first.click(force=True)
                page.wait_for_timeout(2000)
            else:
                # Ưu tiên 2: Mở qua nút Tạo ở góc trên bên phải
                create_btn = page.locator('#create-icon, ytcp-button#create-icon').first
                if create_btn.is_visible():
                    self._log("[YouTube] Bấm nút Tạo...")
                    create_btn.click(force=True)
                    page.wait_for_timeout(1500)

                # Click chính xác vào mục đầu tiên trong menu xổ xuống (#text-item-0)
                upload_menu_item = page.locator('#text-item-0, tp-yt-paper-item#text-item-0').first
                if upload_menu_item.is_visible():
                    self._log("[YouTube] Bấm chọn dòng Tải video lên trong menu (#text-item-0)...")
                    upload_menu_item.click(force=True)
                    page.wait_for_timeout(2000)

            # 3. Chờ hộp thoại tải video xuất hiện và nạp file
            self._log("[YouTube] Đang nạp file video vào khung upload...")
            try:
                # Thẻ input file luôn có sẵn khi dialog mở
                file_input = page.locator('ytcp-uploads-dialog input[type="file"], input[type="file"]').first
                file_input.wait_for(state="attached", timeout=25000)
                file_input.set_input_files(os.path.abspath(video_path))
                self._log("[YouTube] Đã chọn file video thành công!")
                page.wait_for_timeout(5000)
            except Exception:
                page.screenshot(path="youtube_upload_dialog_error.png")
                context.close()
                raise Exception("Không thể mở khung tải video của YouTube Studio. Đã lưu ảnh màn hình tại 'youtube_upload_dialog_error.png'.")

            if progress_callback:
                try:
                    progress_callback(50)
                except Exception:
                    pass

            # 4. TÁCH THÔNG MINH: TIÊU ĐỀ NGẮN GỌN (<85 KÝ TỰ) VÀ ĐƯA ĐOẠN VĂN DÀI VÀO MÔ TẢ
            print("[YouTube] Đang chuẩn hóa Tiêu đề (<85 ký tự) và nạp Mô tả đầy đủ...")
            if self.log_callback:
                self.log_callback("[YouTube] Đang chuẩn hóa Tiêu đề (<85 ký tự) và nạp Mô tả đầy đủ...")
            page.wait_for_timeout(2000)

            raw_content = title if title else description
            
            # Tách tiêu đề ngắn gọn
            import re
            # Lọc bỏ hashtag để lấy câu tiêu đề thuần túy
            clean_text = re.sub(r'#\S+', '', raw_content).strip()
            # Lấy câu đầu tiên (ngăn cách bởi dấu chấm, xuống dòng hoặc dấu phẩy)
            first_sentence = re.split(r'[.\n!]', clean_text)[0].strip()
            if not first_sentence:
                first_sentence = clean_text[:65]
            if len(first_sentence) > 65:
                first_sentence = first_sentence[:65].rsplit(' ', 1)[0]
            
            # Gắn đuôi #Shorts vào tiêu đề
            final_title = f"{first_sentence} #Shorts"[:85]

            # Toàn bộ nội dung dài đưa vào Mô tả
            final_desc = raw_content.strip()
            if description and description.strip() and description.strip() != title.strip():
                final_desc = description.strip()

            # 4.1. Điền vào ô Tiêu đề (#title-textarea #textbox)
            try:
                title_box = page.locator('#title-textarea #textbox').first
                title_box.click()
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.wait_for_timeout(300)
                title_box.type(final_title, delay=20)
                page.keyboard.press("Escape")
                print(f"[YouTube] Đã nhập Tiêu đề chuẩn ({len(final_title)}/100): {final_title}")
                if self.log_callback:
                    self.log_callback(f"[YouTube] Đã nhập Tiêu đề chuẩn ({len(final_title)}/100): {final_title}")
            except Exception as e:
                print(f"[YouTube] Lỗi nhập tiêu đề: {e}")
                if self.log_callback:
                    self.log_callback(f"[YouTube] Lỗi nhập tiêu đề: {e}")

            # 4.2. Điền vào ô Mô tả (#description-textarea #textbox)
            try:
                desc_box = page.locator('#description-textarea #textbox').first
                desc_box.scroll_into_view_if_needed()
                desc_box.click()
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.wait_for_timeout(300)
                desc_box.type(final_desc[:4500], delay=10)
                page.keyboard.press("Escape")
                print(f"[YouTube] Đã nhập Mô tả đầy đủ ({len(final_desc)} ký tự)!")
                if self.log_callback:
                    self.log_callback(f"[YouTube] Đã nhập Mô tả đầy đủ ({len(final_desc)} ký tự)!")
            except Exception as e:
                print(f"[YouTube] Lỗi nhập mô tả: {e}")
                if self.log_callback:
                    self.log_callback(f"[YouTube] Lỗi nhập mô tả: {e}")

            page.wait_for_timeout(1000)

            # 4.3. TỰ ĐỘNG TẠO VÀ NẠP ẢNH BÌA (THUMBNAIL)
            print("[YouTube] Đang xử lý ảnh bìa (Thumbnail)...")
            if self.log_callback:
                self.log_callback("[YouTube] Đang xử lý ảnh bìa (Thumbnail)...")
            thumb_file = custom_thumbnail
            
            # Nếu người dùng không chỉ định ảnh bìa riêng, tự động trích xuất 1 frame từ video
            if not thumb_file or not os.path.exists(thumb_file):
                thumb_file = extract_thumbnail_from_video(video_path, at_second=4)

            if thumb_file and os.path.exists(thumb_file):
                try:
                    # Ô nạp file ảnh thu nhỏ của YouTube Studio có id là #file-loader
                    thumb_input = page.locator('ytcp-thumbnails-compact-editor input[type="file"], #file-loader').first
                    if thumb_input.count() > 0:
                        thumb_input.set_input_files(os.path.abspath(thumb_file))
                        print(f"[YouTube] Đã tải ảnh bìa thành công từ: {os.path.basename(thumb_file)}!")
                        if self.log_callback:
                            self.log_callback(f"[YouTube] Đã tải ảnh bìa thành công từ: {os.path.basename(thumb_file)}!")
                        page.wait_for_timeout(2000)
                except Exception as e:
                    print(f"[YouTube] Lưu ý khi nạp ảnh bìa tùy chỉnh: {e}")

            # Dự phòng: Tự động click chọn 1 trong 3 khung hình gợi ý có sẵn của YouTube
            try:
                auto_thumbs = page.locator('ytcp-thumbnails-compact-editor-uploader-old .thumbnail, ytcp-thumbnails-compact-editor tp-yt-paper-radio-button')
                if auto_thumbs.count() > 1:
                    # Chọn khung hình thứ 2 (ở giữa)
                    auto_thumbs.nth(1).click(force=True)
                    print("[YouTube] Đã chọn khung hình gợi ý có sẵn từ video!")
                    if self.log_callback:
                        self.log_callback("[YouTube] Đã chọn khung hình gợi ý có sẵn từ video!")
            except Exception:
                pass

            page.wait_for_timeout(1000)

            # 5. BẮT BUỘC: CUỘN XUỐNG VÀ TICK "KHÔNG DÀNH CHO TRẺ EM"
            self._log("[YouTube] Đang cuộn xuống để chọn 'Không dành cho trẻ em'...")
            page.wait_for_timeout(1000)
            
            # Cuộn container xuống dưới để hiện mục Đối tượng người xem
            page.evaluate("""() => {
                const scrollContainer = document.querySelector('#scrollable-content') || document.querySelector('#dialog');
                if (scrollContainer) scrollContainer.scrollTop = scrollContainer.scrollHeight / 2;
            }""")
            page.wait_for_timeout(1000)

            # Click trực tiếp vào ô Không dành cho trẻ em
            try:
                not_kids_elem = page.locator(
                    'tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"], '
                    '#radioLabel:has-text("không phải nội dung dành cho trẻ em"), '
                    '#radioLabel:has-text("not made for kids")'
                ).first
                not_kids_elem.scroll_into_view_if_needed()
                not_kids_elem.click(force=True)
                self._log("[YouTube] Đã tick chọn: Không dành cho trẻ em!")
                page.wait_for_timeout(1000)
            except Exception as e:
                self._log(f"[YouTube] Lỗi khi tick chọn trẻ em: {e}")
                try:
                    page.evaluate("""() => {
                        const radio = document.querySelector('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]');
                        if (radio) {
                            radio.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            radio.click();
                        }
                    }""")
                except Exception:
                    pass

            if progress_callback:
                try:
                    progress_callback(70)
                except Exception:
                    pass

            # 6. BẤM "TIẾP" (NEXT) QUA TỪNG BƯỚC ĐẾN CHẾ ĐỘ HIỂN THỊ (BƯỚC 4)
            self._log("[YouTube] Đang chuyển tiếp qua các bước đến Chế độ hiển thị...")
            for step in range(1, 5):
                page.wait_for_timeout(1000)

                # Kiểm tra nếu đã đến bước cuối (Chế độ hiển thị có #done-button)
                is_at_final = page.evaluate("""() => {
                    const done = document.querySelector('#done-button');
                    return done && !done.hasAttribute('hidden') && done.offsetParent !== null;
                }""")
                if is_at_final:
                    self._log("[YouTube] Đã đến bước Chế độ hiển thị!")
                    break

                # Chờ nút Tiếp (Next) sáng lên và có thể click
                try:
                    page.wait_for_function("""() => {
                        const btn = document.querySelector('#next-button');
                        return btn && !btn.hasAttribute('disabled') && btn.getAttribute('aria-disabled') !== 'true';
                    }""", timeout=15000)
                    
                    page.evaluate("""() => {
                        const btn = document.querySelector('#next-button');
                        if (btn) btn.click();
                    }""")
                    self._log(f"[YouTube] Đã bấm Tiếp theo (bước {step})...")
                    page.wait_for_timeout(2000)
                except Exception as e:
                    self._log(f"[YouTube] Đang thử bấm Tiếp lại ở bước {step}: {e}")
                    try:
                        page.locator('#next-button').click(force=True)
                    except Exception:
                        pass
                    page.wait_for_timeout(2000)

            page.wait_for_timeout(2000)

            # 7. Ở Bước 4: Cài đặt Chế độ hiển thị hoặc Lên lịch
            if schedule_date and schedule_time:
                self._log(f"[YouTube] Đang thiết lập lịch hẹn giờ: {schedule_date} lúc {schedule_time}...")
                try:
                    page.evaluate("""() => {
                        const sched = document.querySelector('#schedule-radio-button') || 
                                      document.querySelector('tp-yt-paper-radio-button[name="SCHEDULE"]');
                        if (sched) sched.click();
                    }""")
                    page.wait_for_timeout(1000)
                    time_input = page.locator('input[aria-label*="thời gian"], input[aria-label*="Time"]').first
                    if time_input.is_visible():
                        time_input.fill(schedule_time)
                        page.keyboard.press("Enter")
                except Exception as e:
                    self._log(f"[YouTube] Lỗi cài đặt hẹn giờ: {e}")
            else:
                # Đăng trực tiếp: Chọn Công khai (PUBLIC), Không công khai (UNLISTED) hoặc Riêng tư (PRIVATE)
                if privacy_status.lower() == "private":
                    target_privacy = "PRIVATE"
                elif privacy_status.lower() == "unlisted":
                    target_privacy = "UNLISTED"
                else:
                    target_privacy = "PUBLIC"
                self._log(f"[YouTube] Đang chọn chế độ hiển thị: {target_privacy}...")
                page.evaluate(f"""() => {{
                    const radio = document.querySelector('tp-yt-paper-radio-button[name="{target_privacy}"]');
                    if (radio) radio.click();
                }}""")

            page.wait_for_timeout(2000)

            if progress_callback:
                try:
                    progress_callback(90)
                except Exception:
                    pass

            # 8. Bấm nút Hoàn tất / Lên lịch / Xuất bản (#done-button)
            self._log("[YouTube] Đang bấm nút Hoàn tất/Lưu bài...")
            try:
                # Đợi nút done-button có thể click được
                page.wait_for_function("""() => {
                    const done = document.querySelector('#done-button');
                    return done && !done.hasAttribute('hidden') && done.offsetParent !== null && !done.hasAttribute('disabled');
                }""", timeout=20000)

                page.evaluate("""() => {
                    const done = document.querySelector('#done-button');
                    if (done) done.click();
                }""")
                self._log("[YouTube] Đã bấm nút đăng/lên lịch thành công!")
            except Exception:
                page.screenshot(path="youtube_done_btn_error.png")
                context.close()
                raise Exception("Không thể bấm nút Hoàn tất của YouTube. Đã lưu ảnh màn hình tại 'youtube_done_btn_error.png'.")

            # 9. Chờ popup xác nhận và lấy Link video
            video_url = ""
            start_wait = time.time()
            while time.time() - start_wait < 35:
                try:
                    link_elem = page.locator('a.ytcp-video-info, a[href*="youtu.be"]')
                    if link_elem.count() > 0:
                        href = link_elem.first.get_attribute("href")
                        if href:
                            video_url = href.strip()
                            break
                except Exception:
                    pass

                try:
                    close_dialog_btn = page.locator('#close-button, button:has-text("Đóng"), button:has-text("Close")')
                    if close_dialog_btn.count() > 0 and close_dialog_btn.first.is_visible():
                        break
                except Exception:
                    pass

                page.wait_for_timeout(1000)

            page.wait_for_timeout(2000)
            context.close()

            if progress_callback:
                try:
                    progress_callback(100)
                except Exception:
                    pass

            self._log(f"[YouTube] 🎉 Hoàn tất đăng video! Link: {video_url or 'Đã lưu trên kênh'}")
            return {
                "success": True,
                "url": video_url,
                "video_url": video_url,
                "video_id": video_url.split("/")[-1] if "/" in video_url else "",
            }


def upload_to_youtube(
    video_path: str,
    title: str,
    description: str = "",
    tags: Optional[List[str]] = None,
    privacy_status: str = "public",
    schedule_date: Optional[str] = None,
    schedule_time: Optional[str] = None,
    scheduled_time: Optional[Any] = None,
    custom_thumbnail: Optional[str] = None,
    cookies_file_path: Optional[str] = "youtube_cookies.txt",
    profile_dir: str = "profiles/youtube_profile",
    client_secrets_file: str = "",  # Tham số giữ tương thích ngược
    token_file: str = "",           # Tham số giữ tương thích ngược
    log_callback: Optional[Callable[[str], None]] = None,
    progress_callback: Optional[Callable[[int], None]] = None,
    headless: bool = False,
) -> Dict[str, Any]:
    """Hàm tiện ích gọi trực tiếp upload_video với YouTubeUploader."""
    uploader = YouTubeUploader(
        cookies_file_path=cookies_file_path,
        profile_dir=profile_dir,
        log_callback=log_callback,
        headless=headless,
    )
    return uploader.upload_video(
        video_path=video_path,
        title=title,
        description=description,
        privacy_status=privacy_status,
        schedule_date=schedule_date,
        schedule_time=schedule_time,
        scheduled_time=scheduled_time,
        tags=tags,
        custom_thumbnail=custom_thumbnail,
        progress_callback=progress_callback,
    )


# ══════════════════════════════════════════════════════════════════════
# LUỒNG NỀN XỬ LÝ ĐĂNG YOUTUBE (QTHREAD)
# ══════════════════════════════════════════════════════════════════════

class YouTubeUploadWorker(QThread):
    """
    Luồng nền đăng video lên YouTube không gây giật lag giao diện người dùng.
    """

    log_message = pyqtSignal(str)
    upload_started = pyqtSignal(str)
    progress_updated = pyqtSignal(int)
    upload_finished = pyqtSignal(str, bool, str, str)  # (video_path, success, message, video_url)

    def __init__(
        self,
        video_path: str,
        title: str,
        description: str = "",
        tags: Optional[List[str]] = None,
        privacy_status: str = "public",
        schedule_date: Optional[str] = None,
        schedule_time: Optional[str] = None,
        scheduled_time: Optional[Any] = None,
        custom_thumbnail: Optional[str] = None,
        cookies_file_path: Optional[str] = "youtube_cookies.txt",
        profile_dir: str = "profiles/youtube_profile",
        client_secrets_file: str = "",
        token_file: str = "",
        headless: bool = False,
        parent: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        self.video_path = video_path
        self.title = title
        self.description = description
        self.tags = tags
        self.privacy_status = privacy_status
        self.schedule_date = schedule_date
        self.schedule_time = schedule_time
        self.scheduled_time = scheduled_time
        self.custom_thumbnail = custom_thumbnail
        self.cookies_file_path = cookies_file_path
        self.profile_dir = profile_dir or "profiles/youtube_profile"
        self.headless = headless

    def run(self) -> None:
        self.upload_started.emit(self.video_path)
        try:
            resp = upload_to_youtube(
                video_path=self.video_path,
                title=self.title,
                description=self.description,
                tags=self.tags,
                privacy_status=self.privacy_status,
                schedule_date=self.schedule_date,
                schedule_time=self.schedule_time,
                scheduled_time=self.scheduled_time,
                custom_thumbnail=self.custom_thumbnail,
                cookies_file_path=self.cookies_file_path,
                profile_dir=self.profile_dir,
                log_callback=self.log_message.emit,
                progress_callback=self.progress_updated.emit,
                headless=self.headless,
            )
            v_url = resp.get("video_url", resp.get("url", ""))
            msg = f"Đăng thành công! Link: {v_url or 'Đã lưu trên kênh'}"
            if self.schedule_date and self.schedule_time:
                msg += f" (Hẹn giờ: {self.schedule_date} lúc {self.schedule_time})"
            self.upload_finished.emit(self.video_path, True, msg, v_url)
        except Exception as e:
            err_msg = str(e)
            self.log_message.emit(f"[YouTube] ❌ Lỗi đăng video: {err_msg}")
            self.upload_finished.emit(self.video_path, False, err_msg, "")
