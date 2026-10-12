"""
core/tiktok_uploader.py - Module Tự động Đăng Video lên TikTok (Auto TikTok Uploader)

Tính năng:
  1. Tự động sinh Caption giật tít + 4-5 Hashtag thịnh hành TikTok Việt Nam bằng Gemini AI.
  2. Nạp Cookie đăng nhập (.txt Netscape hoặc .json) để xác thực không cần nhập mật khẩu.
  3. Tự động hóa đăng video bằng Playwright (Chromium/Edge) mở trực quan (headless=False).
  4. Bắt thẻ tải file bị ẩn CSS (state='attached') và kiểm tra cả main frame lẫn iframe.
  5. Tự động quét và đóng toàn bộ modal popup che khuất màn hình (TUXModal-overlay).
  6. Định vị chính xác nút Đăng (Post) ở cuối trang, loại trừ hoàn toàn các nút Sidebar.
  7. Hỗ trợ tùy chọn chế độ hiển thị: Công khai (Public) hoặc Riêng tư (Private).
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests
from PyQt6.QtCore import QThread, pyqtSignal
from playwright.sync_api import sync_playwright

logger = logging.getLogger("OmniGrab.TikTokUploader")


# ══════════════════════════════════════════════════════════════════════
# 1. PARSE COOKIE TIKTOK (NETSCAPE .TXT VÀ .JSON)
# ══════════════════════════════════════════════════════════════════════

def parse_netscape_cookies(cookie_file_path: str) -> List[Dict[str, Any]]:
    """
    Tự động đọc và chuyển đổi định dạng cookie (.txt Netscape hoặc .json)
    sang danh sách cookie tương thích với Playwright (context.add_cookies).
    """
    cookies: List[Dict[str, Any]] = []
    if not cookie_file_path or not os.path.exists(cookie_file_path):
        return cookies

    with open(cookie_file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read().strip()

    if not content:
        return cookies

    # 1. Kiểm tra nếu là file định dạng JSON
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
                domain = item.get("domain", ".tiktok.com")
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

    # 2. Xử lý định dạng Netscape HTTP Cookie File (.txt)
    for line in content.splitlines():
        line = line.strip()
        if not line or (line.startswith("#") and not line.startswith("#HttpOnly_")):
            continue

        http_only = False
        if line.startswith("#HttpOnly_"):
            line = line[len("#HttpOnly_"):].strip()
            http_only = True

        parts = line.split("\t")
        if len(parts) < 7 and "   " in line:
            parts = re.split(r"\s{2,}", line)

        if len(parts) >= 7:
            domain, flag, path, secure, expiration, name, value = parts[:7]
            try:
                exp = float(expiration)
            except ValueError:
                exp = -1.0

            cookie_dict: Dict[str, Any] = {
                "name": str(name),
                "value": str(value),
                "domain": str(domain),
                "path": str(path),
                "secure": secure.upper() == "TRUE",
                "httpOnly": http_only,
            }
            if exp > 0:
                cookie_dict["expires"] = exp
            cookies.append(cookie_dict)

    return cookies


# Alias tương thích ngược
parse_cookies_file = parse_netscape_cookies


# ══════════════════════════════════════════════════════════════════════
# 2. SINH CAPTION & HASHTAG CHUẨN SEO BẰNG GEMINI AI
# ══════════════════════════════════════════════════════════════════════

def generate_tiktok_caption(
    script_content: Any,
    api_key: str = "",
    video_title: str = "",
) -> str:
    """
    Sử dụng Gemini Flash để sinh ra đúng 1 dòng Caption TikTok giật tít kèm 4-5 hashtag thịnh hành.
    Nếu không có API key hoặc lỗi mạng, sinh caption dự phòng thông minh.
    """
    summary_text = ""
    if isinstance(script_content, list):
        lines: List[str] = []
        for item in script_content:
            if hasattr(item, "text_trans") and item.text_trans:
                lines.append(item.text_trans)
            elif hasattr(item, "text_orig") and item.text_orig:
                lines.append(item.text_orig)
            elif isinstance(item, dict):
                lines.append(item.get("text_trans") or item.get("text_orig") or "")
            elif isinstance(item, str):
                lines.append(item)
        summary_text = " ".join(lines[:30])
    elif isinstance(script_content, str):
        summary_text = script_content.strip()

    clean_title = re.sub(r"[_\-.\d]+", " ", Path(video_title).stem).strip() if video_title else "Siêu phẩm kịch tính"
    if not clean_title:
        clean_title = "Phim hay đặc sắc"

    clean_key = (api_key or "").strip()
    if clean_key and (summary_text or video_title):
        headers = {"Content-Type": "application/json"}
        prompt_text = (
            "Bạn là chuyên gia sáng tạo nội dung TikTok triệu view hàng đầu Việt Nam.\n"
            f"Dựa trên kịch bản video tiếng Việt sau đây:\n\"{summary_text[:1800]}\"\n"
            f"(Tên video tham khảo: {clean_title})\n\n"
            "Hãy tạo ra ĐÚNG 1 DÒNG Caption TikTok giật tít, tò mò, cảm xúc cuốn hút, kèm 4-5 hashtag thịnh hành TikTok Việt Nam "
            "(#xuhuong #fyp #phimhay #reviewphim #omnidub #phimngan...). \n"
            "Yêu cầu:\n"
            "1. Đúng 1 dòng duy nhất dài từ 60-120 ký tự.\n"
            "2. Không để trong dấu ngoặc kép, không giải thích hay mở đầu vòng vo.\n"
            "Ví dụ mẫu: Đại náo rạp phim, khi nam thần trường học chính thức ra tay #xuhuong #fyp #phimhay #reviewphim"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 256},
        }

        candidate_models = (
            "gemini-2.5-flash",
            "gemini-1.5-flash",
            "gemini-flash-latest",
            "gemini-3.5-flash-lite",
        )

        for model_name in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={clean_key}"
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=12)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        if parts:
                            caption = parts[0].get("text", "").strip()
                            caption = caption.replace('"', "").replace("'", "").strip()
                            if caption and "#" in caption:
                                return caption
            except Exception:
                continue

    return f"{clean_title} - Cái kết bất ngờ không ai ngờ tới #xuhuong #fyp #phimhay #reviewphim #tiktokvietnam"


# ══════════════════════════════════════════════════════════════════════
# 3. TIỆN ÍCH XỬ LÝ MODAL POPUP & TÌM NÚT ĐĂNG CHÍNH XÁC
# ══════════════════════════════════════════════════════════════════════

def dismiss_tiktok_modals(page: Any, log_fn: Optional[Callable[[str], None]] = None) -> None:
    """
    Tự động quét và đóng toàn bộ modal popup, tooltip hoặc dialog che màn hình (TUXModal-overlay).
    Xử lý cả pop-up bản quyền ('Vẫn đăng' / 'Post anyway') và các nút 'Đã hiểu' / 'Got it'.
    """
    # 1. Nhấn phím Escape để đóng nhanh các dialog đơn giản
    try:
        if page.locator('.TUXModal-overlay, div[data-floating-ui-portal], div[role="dialog"]').count() > 0:
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
    except Exception:
        pass

    # 2. Danh sách các nút ưu tiên đóng/xác nhận trong modal (cả tiếng Việt và tiếng Anh)
    dismiss_selectors = [
        'div[data-floating-ui-portal] button:has-text("Post now")',
        'div[data-floating-ui-portal] button:has-text("Đăng ngay")',
        'button:has-text("Post now")',
        'button:has-text("Đăng ngay")',
        'div[data-floating-ui-portal] button:has-text("Turn on")',
        'div[data-floating-ui-portal] button:has-text("Bật")',
        'div[data-floating-ui-portal] button:has-text("Vẫn đăng")',
        'div[data-floating-ui-portal] button:has-text("Post anyway")',
        'div[data-floating-ui-portal] button:has-text("Publish anyway")',
        'div[data-floating-ui-portal] button:has-text("Đã hiểu")',
        'div[data-floating-ui-portal] button:has-text("Got it")',
        'div[data-floating-ui-portal] button:has-text("Xác nhận")',
        'div[data-floating-ui-portal] button:has-text("Confirm")',
        'div[data-floating-ui-portal] button:has-text("Tiếp tục")',
        'div[data-floating-ui-portal] button:has-text("Continue")',
        'div[data-floating-ui-portal] button:has-text("Đồng ý")',
        'div[data-floating-ui-portal] button:has-text("Agree")',
        'div[data-floating-ui-portal] button:has-text("OK")',
        'div[data-floating-ui-portal] button:has-text("Bỏ qua")',
        'div[data-floating-ui-portal] button:has-text("Skip")',
        'div[data-floating-ui-portal] button:has-text("Đóng")',
        'div[data-floating-ui-portal] button:has-text("Close")',
        'div[data-floating-ui-portal] [aria-label="Close"]',
        'div[data-floating-ui-portal] [aria-label="Đóng"]',
        '.TUXModal-close',
        'button[class*="close"]',
    ]

    for sel in dismiss_selectors:
        try:
            loc = page.locator(sel)
            cnt = loc.count()
            for i in range(cnt):
                btn = loc.nth(i)
                if btn.is_visible():
                    txt = (btn.text_content() or "Close").strip()
                    if log_fn:
                        log_fn(f"[TIKTOK AUTO] 🛡 Đã tự động đóng hộp thoại/modal: '{txt}'")
                    btn.click(timeout=1500)
                    page.wait_for_timeout(400)
        except Exception:
            pass

    # 3. Quét trong tất cả frames
    for frame in page.frames:
        try:
            for sel in dismiss_selectors[:8]:
                loc = frame.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    loc.first.click(timeout=1500)
                    page.wait_for_timeout(400)
        except Exception:
            continue


def find_tiktok_post_button(page: Any) -> Optional[Any]:
    """
    Tìm chính xác nút Đăng (Post) ở cuối trang upload TikTok Studio,
    loại bỏ hoàn toàn các nút Sidebar, menu điều hướng.
    """
    # 1. Các selector cụ thể có độ tin cậy cao nhất (tránh hoàn toàn Sidebar)
    high_priority_selectors = [
        'button[data-e2e="post_video_button"]',
        'button.btn-post',
        'div[class*="btn-post"] button',
        'div[class*="footer"] button[class*="primary"]',
        'div[class*="footer"] button[type="submit"]',
        'div[class*="footer"] button:not([data-tt*="Sidebar"])',
        'button:not([data-tt*="Sidebar"]):not([class*="Sidebar"]):text-is("Đăng")',
        'button:not([data-tt*="Sidebar"]):not([class*="Sidebar"]):text-is("Post")',
        'button:not([data-tt*="Sidebar"]):not([class*="Sidebar"]):text-is("Publish")',
    ]

    for sel in high_priority_selectors:
        try:
            loc = page.locator(sel)
            cnt = loc.count()
            for i in range(cnt):
                btn = loc.nth(i)
                if btn.is_visible() and btn.is_enabled():
                    data_tt = btn.get_attribute("data-tt") or ""
                    cls = btn.get_attribute("class") or ""
                    if "sidebar" not in data_tt.lower() and "sidebar" not in cls.lower():
                        return btn
        except Exception:
            continue

    # 2. Quét tất cả các nút chứa chữ "Đăng" hoặc "Post" nhưng KHÔNG thuộc Sidebar
    fallback_selectors = [
        'button:not([data-tt*="Sidebar"]):not([class*="Sidebar"]):has-text("Đăng")',
        'button:not([data-tt*="Sidebar"]):not([class*="Sidebar"]):has-text("Post")',
    ]
    for sel in fallback_selectors:
        try:
            loc = page.locator(sel)
            cnt = loc.count()
            # Lấy từ dưới lên (nút submit nằm ở cuối form nội dung)
            for i in reversed(range(cnt)):
                btn = loc.nth(i)
                if btn.is_visible() and btn.is_enabled():
                    txt = (btn.inner_text() or "").strip().lower()
                    data_tt = btn.get_attribute("data-tt") or ""
                    cls = btn.get_attribute("class") or ""
                    if "sidebar" in data_tt.lower() or "sidebar" in cls.lower():
                        continue
                    if txt in ("post", "đăng", "xuất bản", "publish", "post now", "đăng ngay", "vẫn đăng", "post anyway"):
                        return btn
        except Exception:
            continue

    # 3. Quét trong các frame nếu có
    for frame in page.frames:
        for sel in high_priority_selectors + fallback_selectors:
            try:
                loc = frame.locator(sel)
                if loc.count() > 0 and loc.first.is_visible() and loc.first.is_enabled():
                    return loc.first
            except Exception:
                continue

    return None


# ══════════════════════════════════════════════════════════════════════
# 4. CLASS TIKTOK UPLOADER (PLAYWRIGHT)
# ══════════════════════════════════════════════════════════════════════

class TikTokUploader:
    """Bộ xử lý tự động đăng video lên TikTok bằng Playwright."""

    def __init__(self, cookies_file_path: str, log_callback: Optional[Callable[[str], None]] = None):
        self.cookies_file_path = cookies_file_path
        self.log_callback = log_callback

    def _log(self, msg: str) -> None:
        if self.log_callback:
            self.log_callback(msg)
        logger.info(msg)

    def upload_video(
        self,
        video_path: str,
        caption: str = "",
        is_private: bool = False,
        headless: bool = False,
    ) -> bool:
        """
        Tự động tải video lên TikTok Studio sử dụng cookie phiên đã lưu.
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Không tìm thấy file video: {video_path}")

        cookies = parse_netscape_cookies(self.cookies_file_path)
        if not cookies:
            raise Exception("File cookie bị rỗng hoặc không đọc được. Vui lòng kiểm tra lại file cookies.txt.")

        self._log(f"[TIKTOK AUTO] 🍪 Đã đọc và nạp {len(cookies)} cookies phiên TikTok.")

        with sync_playwright() as p:
            # Khởi chạy trình duyệt thật (ưu tiên Edge/Chrome hoặc Chromium có sẵn)
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
                "--no-sandbox",
            ]
            browser = None
            for channel in ("msedge", "chrome", None):
                try:
                    kwargs: Dict[str, Any] = {
                        "headless": headless,
                        "args": launch_args,
                    }
                    if channel:
                        kwargs["channel"] = channel
                    browser = p.chromium.launch(**kwargs)
                    if browser:
                        break
                except Exception:
                    continue

            if not browser:
                raise RuntimeError("Không thể khởi động trình duyệt web (Edge/Chrome/Chromium). Vui lòng kiểm tra môi trường.")

            try:
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                    no_viewport=True,
                )

                # Nạp cookie vào context
                try:
                    context.add_cookies(cookies)
                except Exception as c_err:
                    self._log(f"[TIKTOK AUTO] ⚠ Lưu ý khi nạp cookie: {c_err}")

                page = context.new_page()

                # 1. Truy cập trang TikTok Studio Upload
                upload_url = "https://www.tiktok.com/tiktokstudio/upload"
                self._log(f"[TIKTOK AUTO] 🚀 Đang truy cập trang tải lên: {upload_url}...")
                page.goto(upload_url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(3000)

                # Kiểm tra trạng thái phiên
                if "login" in page.url.lower() or "passport" in page.url.lower():
                    browser.close()
                    raise Exception("Cookie đã hết hạn hoặc chưa đăng nhập. Vui lòng xuất lại file cookies.txt.")

                # Tự động đóng các popup chào mừng/tooltip cản trở
                dismiss_tiktok_modals(page, self._log)

                # 2. Tìm thẻ input file (dùng state='attached' để bắt thẻ ẩn CSS display:none)
                self._log(f"[TIKTOK AUTO] 📤 Đang tìm khung tải file và nạp video: {os.path.basename(video_path)}...")
                file_input = None
                try:
                    page.wait_for_selector('input[type="file"]', state="attached", timeout=15000)
                    file_input = page.locator('input[type="file"]').first
                except Exception:
                    # Quét trong các iframe dự phòng
                    for frame in page.frames:
                        try:
                            if frame.locator('input[type="file"]').count() > 0:
                                file_input = frame.locator('input[type="file"]').first
                                break
                        except Exception:
                            continue

                if not file_input:
                    browser.close()
                    raise Exception("Không tìm thấy khung tải file video trên trang TikTok. Có thể giao diện TikTok vừa cập nhật.")

                # 3. Nạp đường dẫn video vào input
                file_input.set_input_files(os.path.abspath(video_path))
                self._log(f"[TIKTOK AUTO] 📤 Đã nạp file video: {os.path.basename(video_path)}, đang tải lên...")

                # 4. Nhập Tiêu đề & Caption (nếu có)
                page.wait_for_timeout(5000)
                if caption:
                    self._log(f"[TIKTOK AUTO] ✍ Đang điền Caption & Hashtags: {caption[:60]}...")
                    caption_filled = False
                    caption_selectors = [
                        'div[contenteditable="true"]',
                        '.public-DraftEditor-content',
                        '[data-placeholder*="mô tả"]',
                        '[data-placeholder*="description"]',
                        '[data-placeholder*="caption"]',
                        'textarea',
                    ]
                    for sel in caption_selectors:
                        try:
                            caption_box = page.locator(sel).first
                            if caption_box.is_visible(timeout=3000):
                                caption_box.click()
                                page.keyboard.press("Control+A")
                                page.keyboard.press("Backspace")
                                page.wait_for_timeout(300)
                                page.keyboard.type(caption, delay=25)
                                caption_filled = True
                                break
                        except Exception:
                            pass

                    if not caption_filled:
                        for frame in page.frames:
                            for sel in caption_selectors:
                                try:
                                    caption_box = frame.locator(sel).first
                                    if caption_box.is_visible(timeout=2000):
                                        caption_box.click()
                                        frame.page.keyboard.press("Control+A")
                                        frame.page.keyboard.press("Backspace")
                                        page.wait_for_timeout(300)
                                        frame.page.keyboard.type(caption, delay=25)
                                        caption_filled = True
                                        break
                                except Exception:
                                    pass
                            if caption_filled:
                                break

                    if caption_filled:
                        self._log("[TIKTOK AUTO] ✅ Đã điền xong Caption và Hashtags chuẩn SEO.")

                # 5. Cài đặt chế độ Riêng tư / Công khai
                if is_private:
                    self._log("[TIKTOK AUTO] 🔒 Đang thiết lập chế độ hiển thị: Riêng tư (Private)...")
                    try:
                        for p_sel in [
                            'text="Chỉ mình tôi"',
                            'text="Private"',
                            'text="Riêng tư"',
                            '[data-e2e="privacy-private"]',
                        ]:
                            private_opt = page.locator(p_sel).first
                            if private_opt.is_visible(timeout=2000):
                                private_opt.click()
                                break
                    except Exception:
                        pass
                else:
                    self._log("[TIKTOK AUTO] 🌍 Thiết lập chế độ hiển thị: Công khai (Public)...")
                    try:
                        for p_sel in [
                            'text="Công khai"',
                            'text="Mọi người"',
                            'text="Public"',
                            '[data-e2e="privacy-public"]',
                        ]:
                            public_opt = page.locator(p_sel).first
                            if public_opt.is_visible(timeout=2000):
                                public_opt.click()
                                break
                    except Exception:
                        pass

                # 6. ĐỢI VIDEO TẢI LÊN 100% VÀ NÚT ĐĂNG KHÔNG CÒN BỊ KHÓA (DISABLED, TỐI ĐA 180s)
                self._log("[TIKTOK AUTO] ⏳ Đang đợi video tải lên hoàn tất và nút Đăng sẵn sàng (tối đa 180s)...")
                upload_ready = False
                start_upload_wait = time.time()
                last_log_time = 0

                while time.time() - start_upload_wait < 180:
                    dismiss_tiktok_modals(page)

                    try:
                        is_ready = page.evaluate("""() => {
                            const buttons = Array.from(document.querySelectorAll('button'));
                            const postBtn = buttons.find(b => {
                                const txt = (b.innerText || b.textContent || '').trim().toLowerCase();
                                const dataTt = (b.getAttribute('data-tt') || '').toLowerCase();
                                const cls = (b.className || '').toLowerCase();
                                const isSidebar = dataTt.includes('sidebar') || cls.includes('sidebar') || Boolean(b.closest('[data-tt*="Sidebar"], .sidebar, aside, nav'));
                                if (isSidebar) return false;
                                return txt === 'đăng' || txt === 'post' || txt === 'publish' || txt.includes('đăng') || txt.includes('post');
                            });
                            if (!postBtn) return false;
                            const isDisabled = postBtn.disabled || postBtn.getAttribute('aria-disabled') === 'true' || postBtn.classList.contains('disabled');
                            return !isDisabled;
                        }""")
                        if is_ready:
                            upload_ready = True
                            break
                    except Exception:
                        pass

                    elapsed = int(time.time() - start_upload_wait)
                    if elapsed - last_log_time >= 15:
                        last_log_time = elapsed
                        self._log(f"[TIKTOK AUTO] ⏳ Đang đợi video xử lý & tải lên... ({elapsed}s/180s)")

                    page.wait_for_timeout(1500)

                if not upload_ready:
                    # Kiểm tra lại một lần cuối bằng wait_for_function
                    try:
                        page.wait_for_function("""() => {
                            const buttons = Array.from(document.querySelectorAll('button'));
                            const postBtn = buttons.find(b => {
                                const txt = (b.innerText || b.textContent || '').trim().toLowerCase();
                                const isSidebar = (b.getAttribute('data-tt') || '').toLowerCase().includes('sidebar') || b.className.toLowerCase().includes('sidebar');
                                return !isSidebar && (txt.includes('đăng') || txt.includes('post'));
                            });
                            if (!postBtn) return false;
                            return !postBtn.disabled && postBtn.getAttribute('aria-disabled') !== 'true' && !postBtn.classList.contains('disabled');
                        }""", timeout=3000)
                        upload_ready = True
                    except Exception:
                        pass

                if not upload_ready:
                    try:
                        page.screenshot(path="tiktok_upload_timeout.png")
                    except Exception:
                        pass
                    browser.close()
                    raise Exception(
                        "Quá thời gian tải video lên TikTok (Mạng chậm hoặc file video quá nặng > 180s). "
                        "Đã lưu ảnh lỗi tại tiktok_upload_timeout.png."
                    )

                self._log("[TIKTOK AUTO] 🚀 Video đã tải lên xong 100%, nút Đăng đã sẵn sàng! Đang bấm nút Đăng...")

                # Đảm bảo caption đã được điền đầy đủ
                if caption:
                    try:
                        cap_box = page.locator('div[contenteditable="true"]').first
                        if cap_box.is_visible() and not (cap_box.inner_text() or "").strip():
                            cap_box.click()
                            page.keyboard.type(caption, delay=25)
                    except Exception:
                        pass

                # 7. BẤM NÚT ĐĂNG (POST)
                post_btn = find_tiktok_post_button(page)
                if not post_btn:
                    post_btn = page.locator('button:has-text("Đăng"), button:has-text("Post")').first

                try:
                    post_btn.scroll_into_view_if_needed()
                    page.wait_for_timeout(400)
                except Exception:
                    pass

                dismiss_tiktok_modals(page, self._log)

                try:
                    post_btn.click(timeout=5000)
                except Exception:
                    try:
                        post_btn.click(force=True, timeout=3000)
                    except Exception:
                        post_btn.evaluate("el => el.click()")

                page.wait_for_timeout(1500)

                # 8. VÒNG LẶP XỬ LÝ TẤT CẢ CÁC MODAL XÁC NHẬN CỦA TIKTOK SAU KHI BẤM ĐĂNG (TRONG ~10 GIÂY)
                self._log("[TIKTOK AUTO] 🛡 Đang kiểm tra và tự động xử lý các popup xác nhận của TikTok sau khi bấm Đăng...")
                for _ in range(8):
                    # 1. Xử lý popup: "Continue to post?" -> Bấm "Post now" / "Đăng ngay"
                    try:
                        post_now_btn = page.locator('button:has-text("Post now"), button:has-text("Đăng ngay")')
                        if post_now_btn.count() > 0 and post_now_btn.first.is_visible():
                            self._log("[TIKTOK AUTO] ⚠️ Phát hiện bảng 'Continue to post?', đang tự động click 'Post now'...")
                            post_now_btn.first.click()
                            page.wait_for_timeout(1500)
                    except Exception:
                        pass

                    # 2. Xử lý popup: "Turn on automatic content checks?" -> Bấm "Turn on" / "Bật"
                    try:
                        turn_on_btn = page.locator('button:has-text("Turn on"), button:has-text("Bật")')
                        if turn_on_btn.count() > 0 and turn_on_btn.first.is_visible():
                            self._log("[TIKTOK AUTO] 🛡 Phát hiện bảng 'Turn on automatic content checks?', đang click 'Turn on'...")
                            turn_on_btn.first.click()
                            page.wait_for_timeout(1500)
                    except Exception:
                        pass

                    # 3. Xử lý tooltip: "Got it" / "Đã hiểu"
                    try:
                        got_it_btn = page.locator('button:has-text("Got it"), button:has-text("Đã hiểu")')
                        if got_it_btn.count() > 0 and got_it_btn.first.is_visible():
                            self._log("[TIKTOK AUTO] ⚡ Đã tự động đóng tooltip Got it / Đã hiểu.")
                            got_it_btn.first.click()
                            page.wait_for_timeout(500)
                    except Exception:
                        pass

                    # 4. Xử lý các nút xác nhận phụ khác (Vẫn đăng / Post anyway / Publish anyway / Confirm / Xác nhận)
                    try:
                        for confirm_sel in [
                            'button:has-text("Vẫn đăng")',
                            'button:has-text("Post anyway")',
                            'button:has-text("Publish anyway")',
                            'button:has-text("Confirm")',
                            'button:has-text("Xác nhận")',
                        ]:
                            c_btn = page.locator(confirm_sel).first
                            if c_btn.count() > 0 and c_btn.is_visible():
                                self._log(f"[TIKTOK AUTO] ⚡ Xác nhận hộp thoại: '{c_btn.text_content().strip()}'")
                                c_btn.click(timeout=1500)
                                page.wait_for_timeout(1000)
                                break
                    except Exception:
                        pass

                    # Nếu URL đã chuyển sang trang content hoặc có thông báo thành công thì thoát sớm
                    if "content" in page.url.lower():
                        break
                    page.wait_for_timeout(1000)

                # 9. CHỜ THÔNG BÁO XÁC NHẬN ĐĂNG THÀNH CÔNG TỪ TIKTOK (TỐI ĐA 35s)
                self._log("[TIKTOK AUTO] ⏳ Đang chờ xác nhận đăng thành công từ TikTok (tối đa 35s)...")
                success_confirmed = False
                start_confirm_wait = time.time()

                while time.time() - start_confirm_wait < 35:
                    # 1. Kiểm tra URL chuyển hướng sang trang quản lý nội dung
                    cur_url = page.url.lower()
                    if "content" in cur_url or "manage" in cur_url:
                        success_confirmed = True
                        self._log(f"[TIKTOK AUTO] 🎯 URL đã chuyển sang trang quản lý nội dung: {page.url}")
                        break

                    # 2. Kiểm tra thông báo hoặc modal xác nhận thành công
                    for pattern in [
                        'text="Video của bạn đã được tải lên"',
                        'text="Your video has been uploaded"',
                        'text="Quản lý bài đăng"',
                        'text="Manage your posts"',
                        'text="Uploaded"',
                        'text="Đã tải lên"',
                        'text="Xem bài đăng"',
                        'text="View post"',
                        'text="Tải lên video khác"',
                        'text="Upload another video"',
                        'text="Bài đăng của bạn đã được chia sẻ"',
                        'text="Your post has been shared"',
                    ]:
                        try:
                            loc = page.locator(pattern).first
                            if loc.is_visible(timeout=300):
                                success_confirmed = True
                                self._log(f"[TIKTOK AUTO] 🎯 Nhận được xác nhận thành công: {pattern}")
                                break
                        except Exception:
                            pass

                    if success_confirmed:
                        break

                    # Xử lý modal phát sinh sau khi bấm đăng (Post now, Turn on, Got it, Vẫn đăng)
                    try:
                        for c_sel in [
                            'button:has-text("Post now")',
                            'button:has-text("Đăng ngay")',
                            'button:has-text("Turn on")',
                            'button:has-text("Bật")',
                            'button:has-text("Got it")',
                            'button:has-text("Đã hiểu")',
                            'button:has-text("Vẫn đăng")',
                            'button:has-text("Post anyway")',
                        ]:
                            cb = page.locator(c_sel).first
                            if cb.count() > 0 and cb.is_visible(timeout=200):
                                self._log(f"[TIKTOK AUTO] 🛡 Đã tự động click xác nhận: '{cb.text_content().strip()}'")
                                cb.click(timeout=1000)
                                page.wait_for_timeout(500)
                                break
                    except Exception:
                        pass

                    page.wait_for_timeout(1000)

                if not success_confirmed:
                    try:
                        page.screenshot(path="tiktok_post_failed.png")
                        page.screenshot(path="tiktok_post_unconfirmed.png")
                    except Exception:
                        pass
                    browser.close()
                    raise Exception(
                        "Đã bấm Đăng nhưng không nhận được phản hồi xác nhận từ TikTok trong vòng 35s. "
                        "Đã lưu ảnh màn hình tại 'tiktok_post_failed.png'. Vui lòng kiểm tra lại trạng thái bài đăng."
                    )

                self._log(f"[TIKTOK AUTO] 🎉 XÁC NHẬN ĐĂNG THÀNH CÔNG 100% LÊN TIKTOK: {os.path.basename(video_path)}!")
                page.wait_for_timeout(3000)
                browser.close()
                return True

            except Exception:
                try:
                    browser.close()
                except Exception:
                    pass
                raise


# ══════════════════════════════════════════════════════════════════════
# 5. HÀM GỌI ĐỒNG BỘ UPLOAD_TO_TIKTOK
# ══════════════════════════════════════════════════════════════════════

def upload_to_tiktok(
    video_path: str,
    caption: str,
    cookies_path: str,
    privacy: str = "public",
    headless: bool = False,
    log_callback: Optional[Callable[[str], None]] = None,
) -> bool:
    """
    Quy trình tự động đăng video MP4 lên TikTok Studio thông qua Playwright và Cookie đăng nhập.
    """
    is_private = privacy.lower() in ("private", "riêng tư", "bản nháp", "chỉ mình tôi")
    uploader = TikTokUploader(cookies_file_path=cookies_path, log_callback=log_callback)
    return uploader.upload_video(
        video_path=video_path,
        caption=caption,
        is_private=is_private,
        headless=headless,
    )


# Alias tương thích
def upload_video(
    video_path: str,
    caption: str = "",
    cookies_path: str = "",
    is_private: bool = False,
    headless: bool = False,
    log_callback: Optional[Callable[[str], None]] = None,
) -> bool:
    """Hàm tiện ích gọi trực tiếp upload_video với TikTokUploader."""
    uploader = TikTokUploader(cookies_file_path=cookies_path, log_callback=log_callback)
    return uploader.upload_video(
        video_path=video_path,
        caption=caption,
        is_private=is_private,
        headless=headless,
    )


# ══════════════════════════════════════════════════════════════════════
# 6. LUỒNG NỀN XỬ LÝ ĐĂNG TIKTOK (QTHREAD KHÔNG ĐƠ UI)
# ══════════════════════════════════════════════════════════════════════

class TikTokUploadWorker(QThread):
    """Luồng nền đăng video lên TikTok mà không gây giật lag giao diện."""

    log_message = pyqtSignal(str)
    upload_started = pyqtSignal(str)
    upload_finished = pyqtSignal(str, bool, str)  # (video_path, success, message)

    def __init__(
        self,
        video_path: str,
        caption: str,
        cookies_path: str,
        privacy: str = "public",
        headless: bool = False,
        parent: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        self.video_path = video_path
        self.caption = caption
        self.cookies_path = cookies_path
        self.privacy = privacy
        self.headless = headless

    def run(self) -> None:
        try:
            self.upload_started.emit(self.video_path)
            ok = upload_to_tiktok(
                video_path=self.video_path,
                caption=self.caption,
                cookies_path=self.cookies_path,
                privacy=self.privacy,
                headless=self.headless,
                log_callback=self.log_message.emit,
            )
            if ok:
                self.upload_finished.emit(self.video_path, True, "Đã đăng thành công lên kênh TikTok!")
            else:
                self.upload_finished.emit(self.video_path, False, "Quá trình đăng video không hoàn tất.")
        except Exception as e:
            err_msg = str(e)
            self.log_message.emit(f"❌ [TIKTOK AUTO] Lỗi: {err_msg}")
            self.upload_finished.emit(self.video_path, False, err_msg)
