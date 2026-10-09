"""
core/channel_scrapers.py - Bộ quét kênh/hồ sơ chuyên biệt cho Douyin và Facebook.

Lý do:
- yt-dlp không hỗ trợ quét hồ sơ/kênh Douyin (do chữ ký bảo mật a_bogus / x-bogus).
- yt-dlp không hỗ trợ quét Facebook Page / Watch / Reels từ hồ sơ.

Giải pháp:
1. Douyin: Sử dụng thư viện `f2` (với DouyinHandler & SecUserIdFetcher) để giải mã
   sec_user_id và trích xuất danh sách video đầy đủ kèm lượt xem/thích.
2. Facebook: Sử dụng giao diện `mbasic.facebook.com` (HTML thuần không JS) với BeautifulSoup
   và cookie xác thực để duyệt toàn bộ video/reels theo từng trang.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from datetime import date, datetime
from http.cookiejar import MozillaCookieJar
from typing import Callable, List, Optional
from urllib.parse import parse_qs, unquote, urlparse


# ═════════════════════════════════════════════════════════════════════
# TIỆN ÍCH CHUNG
# ═════════════════════════════════════════════════════════════════════

def is_douyin_channel(url: str) -> bool:
    """Kiểm tra URL có phải là kênh / trang cá nhân Douyin."""
    u = url.lower()
    return "douyin.com" in u and ("user" in u or "v.douyin.com" in u or "/@" in u)


def is_facebook_channel(url: str) -> bool:
    """Kiểm tra URL có phải là trang / profile / video Facebook."""
    u = url.lower()
    return "facebook.com" in u or "fb.com" in u or "fb.watch" in u


def parse_cookie_file(cookie_file: str) -> dict[str, str]:
    """
    Đọc cookie từ file Netscape (.txt) thành dict {name: value}.
    Hỗ trợ cả file chuẩn MozillaCookieJar và file thô.
    """
    cookies: dict[str, str] = {}
    if not cookie_file or not os.path.isfile(cookie_file):
        return cookies

    # Cách 1: MozillaCookieJar
    try:
        cj = MozillaCookieJar(cookie_file)
        cj.load(ignore_discard=True, ignore_expires=True)
        for c in cj:
            cookies[c.name] = c.value
        if cookies:
            return cookies
    except Exception:
        pass

    # Cách 2: Parse thủ công từng dòng của định dạng Netscape
    try:
        with open(cookie_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    cookies[parts[5]] = parts[6]
    except Exception:
        pass

    return cookies


def _fmt_number(n) -> str:
    """Format số thành dạng 1.5K, 1.2M."""
    if n is None:
        return "--"
    try:
        n = int(n)
    except (ValueError, TypeError):
        return "--"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _fmt_duration(secs) -> str:
    """Chuyển giây thành MM:SS hoặc HH:MM:SS."""
    if secs is None:
        return "--:--"
    try:
        secs = int(secs)
    except (ValueError, TypeError):
        return "--:--"
    mins, s = divmod(secs, 60)
    h, m = divmod(mins, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _fmt_upload_date(ts) -> tuple[str, str]:
    """Epoch hoặc timestamp sang ('DD/MM/YYYY', 'YYYYMMDD')."""
    if not ts:
        return "--/--/----", ""
    try:
        dt = datetime.fromtimestamp(int(ts))
        return dt.strftime("%d/%m/%Y"), dt.strftime("%Y%m%d")
    except Exception:
        return "--/--/----", ""


# ═════════════════════════════════════════════════════════════════════
# 1. BỘ QUÉT KÊNH DOUYIN (DÙNG f2)
# ═════════════════════════════════════════════════════════════════════

def scan_douyin_channel(
    channel_url: str,
    max_videos: int = 50,
    cookie_file: str = "",
    progress_cb: Optional[Callable[[str], None]] = None,
) -> List[dict]:
    """
    Quét danh sách video từ kênh Douyin bằng thư viện f2.

    Args:
        channel_url: URL trang cá nhân Douyin (https://www.douyin.com/user/xxx hoặc https://v.douyin.com/xxx).
        max_videos: Số lượng video tối đa cần quét.
        cookie_file: Đường dẫn file cookie Netscape (.txt).
        progress_cb: Hàm callback nhận thông báo tiến trình hiển thị lên UI.

    Returns:
        List[dict]: Danh sách video với thông tin chuẩn hóa.
    """
    def _log(msg: str) -> None:
        if progress_cb:
            progress_cb(msg)

    _log("🔍 [Douyin] Đang kiểm tra thư viện và thông tin kênh...")

    try:
        # pyrefly: ignore [missing-import]
        from f2.apps.douyin.handler import DouyinHandler
        # pyrefly: ignore [missing-import]
        from f2.apps.douyin.utils import SecUserIdFetcher
    except ImportError:
        raise RuntimeError(
            "Thư viện 'f2' chưa được cài đặt. Vui lòng chạy lệnh: pip install f2"
        )

    # 1. Trích xuất sec_user_id từ URL
    sec_user_id = ""
    # Kiểm tra xem sec_user_id đã có sẵn trong URL chưa
    m = re.search(r"user/([a-zA-Z0-9_\-]+)", channel_url)
    if m:
        sec_user_id = m.group(1)

    if not sec_user_id:
        _log("🔍 [Douyin] Đang phân giải liên kết rút gọn để lấy sec_user_id...")
        try:
            loop = asyncio.new_event_loop()
            try:
                sec_user_id = loop.run_until_complete(
                    SecUserIdFetcher.get_sec_user_id(channel_url)
                )
            finally:
                loop.close()
        except Exception as e:
            # Nếu SecUserIdFetcher lỗi, thử requests follow redirect
            import requests
            try:
                resp = requests.get(channel_url, allow_redirects=True, timeout=10)
                m2 = re.search(r"user/([a-zA-Z0-9_\-]+)", resp.url)
                if m2:
                    sec_user_id = m2.group(1)
                else:
                    m3 = re.search(r"sec_uid=([a-zA-Z0-9_\-]+)", resp.url)
                    if m3:
                        sec_user_id = m3.group(1)
            except Exception:
                pass

    if not sec_user_id:
        raise RuntimeError(
            "Không thể trích xuất ID người dùng (sec_user_id) từ liên kết Douyin này.\n"
            "Hãy đảm bảo link có dạng https://www.douyin.com/user/MS4wLjABAAAA... hoặc https://v.douyin.com/..."
        )

    _log(f"🔍 [Douyin] ID người dùng: {sec_user_id[:20]}... Đang chuẩn bị tải danh sách...")

    # 2. Chuẩn bị kwargs cho f2
    cookie_dict = parse_cookie_file(cookie_file)
    cookie_str = "; ".join(f"{k}={v}" for k, v in cookie_dict.items()) if cookie_dict else ""

    kwargs: dict = {
        "cookie": cookie_str,
        "proxies": {"http://": None, "https://": None},
        "timeout": 15,
        "max_counts": max_videos,
    }

    # 3. Thu thập danh sách video
    async def _fetch_posts() -> List[dict]:
        handler = DouyinHandler(kwargs)
        collected: List[dict] = []
        page_size = min(max_videos, 20)

        async for post_filter in handler.fetch_user_post_videos(
            sec_user_id=sec_user_id,
            max_counts=max_videos,
            page_counts=page_size,
        ):
            if post_filter is None:
                continue

            # Lấy danh sách aweme từ raw data hoặc filter
            raw_data = getattr(post_filter, "_data", {}) or {}
            aweme_list = raw_data.get("aweme_list") or []

            if not aweme_list and hasattr(post_filter, "aweme_id"):
                # Fallback qua properties của UserPostFilter
                aweme_ids = post_filter.aweme_id or []
                descs = post_filter.desc or []
                times = post_filter.create_time or []
                durs = post_filter.video_duration or []
                for idx, aid in enumerate(aweme_ids):
                    if not aid:
                        continue
                    d_desc = descs[idx] if idx < len(descs) else f"Video {aid}"
                    d_time = times[idx] if idx < len(times) else None
                    d_dur = durs[idx] if idx < len(durs) else 0
                    aweme_list.append({
                        "aweme_id": aid,
                        "desc": d_desc,
                        "create_time": d_time,
                        "duration": d_dur,
                        "statistics": {},
                    })

            for item in aweme_list:
                if not item:
                    continue
                aid = str(item.get("aweme_id", "") or "")
                if not aid:
                    continue

                desc = item.get("desc") or f"Douyin Video #{aid}"
                ctime = item.get("create_time")
                fmt_date, raw_date = _fmt_upload_date(ctime)

                # Duration: Douyin trả về milliseconds trong item['duration'] hoặc item['video']['duration']
                raw_dur = item.get("duration") or item.get("video", {}).get("duration", 0) or 0
                try:
                    dur_val = int(raw_dur)
                    duration_sec = dur_val // 1000 if dur_val > 1000 else dur_val
                except Exception:
                    duration_sec = 0

                # Statistics
                stats = item.get("statistics") or {}
                views_raw = int(stats.get("play_count") or 0)
                likes_raw = int(stats.get("digg_count") or 0)

                video_entry = {
                    "id": aid,
                    "title": str(desc).strip()[:200],
                    "url": f"https://www.douyin.com/video/{aid}",
                    "duration": _fmt_duration(duration_sec),
                    "duration_sec": duration_sec,
                    "views": _fmt_number(views_raw),
                    "views_raw": views_raw,
                    "likes": _fmt_number(likes_raw),
                    "likes_raw": likes_raw,
                    "upload_date": fmt_date,
                    "upload_date_raw": raw_date,
                    # Khả năng tương thích với _passes_filters
                    "view_count": views_raw,
                    "like_count": likes_raw,
                }
                collected.append(video_entry)
                _log(f"✔ [Douyin] Đã quét ({len(collected)}/{max_videos}): {desc[:35]}...")

                if len(collected) >= max_videos:
                    break

            if len(collected) >= max_videos:
                break

        return collected

    try:
        loop = asyncio.new_event_loop()
        try:
            videos = loop.run_until_complete(_fetch_posts())
        finally:
            loop.close()
    except Exception as e:
        err_msg = str(e)
        if "10204" in err_msg or "login" in err_msg.lower() or "private" in err_msg.lower():
            raise RuntimeError(
                "Kênh Douyin yêu cầu đăng nhập hoặc Cookie xác thực đã hết hạn.\n"
                "Vui lòng xuất lại file cookies.txt từ trình duyệt và nạp vào ứng dụng."
            )
        raise RuntimeError(f"Lỗi khi quét kênh Douyin qua f2: {err_msg}")

    if not videos:
        raise RuntimeError(
            "Không tìm thấy video nào trên kênh Douyin này.\n"
            "Kênh có thể ở chế độ riêng tư, chưa đăng video, hoặc cần nạp Cookie."
        )

    return videos


# ═════════════════════════════════════════════════════════════════════
# 2. BỘ QUÉT TRANG / VIDEO FACEBOOK
# ═════════════════════════════════════════════════════════════════════

def is_facebook_single_video(url: str) -> bool:
    """Kiểm tra xem link Facebook có phải là video / reel / watch đơn lẻ hay không."""
    u = url.lower()
    return (
        "/watch" in u
        or "/reel/" in u
        or "/reels/" in u
        or "fb.watch" in u
        or bool(re.search(r"/videos/\d+", u))
        or bool(re.search(r"[?&]v=\d+", u))
        or "/share/r/" in u
        or "/share/v/" in u
    )


def scan_facebook_channel(
    channel_url: str,
    max_videos: int = 50,
    cookie_file: str = "",
    progress_cb: Optional[Callable[[str], None]] = None,
) -> List[dict]:
    """
    Quét danh sách video từ Facebook Page / Watch / Reels.

    Hỗ trợ cả 2 trường hợp:
    1. Nếu người dùng dán link video / reel / watch đơn lẻ:
       - Tự động bóc tách thông tin video đó và đưa vào danh sách để tải ngay.
    2. Nếu người dùng dán link Page / Profile / Channel:
       - Sử dụng curl_cffi (impersonate chrome120) để vượt tường lửa TLS của Meta,
         bóc tách video IDs từ Store JSON và DOM mà không cần đăng nhập.
       - Hỗ trợ cookie Netscape (.txt) nếu trang yêu cầu bảo mật cao.

    Args:
        channel_url: URL trang hoặc video Facebook.
        max_videos: Số lượng video tối đa cần quét.
        cookie_file: Đường dẫn file cookie Netscape (.txt).
        progress_cb: Hàm callback nhận thông báo tiến trình.

    Returns:
        List[dict]: Danh sách video đã tìm thấy.
    """
    def _log(msg: str) -> None:
        if progress_cb:
            progress_cb(msg)

    today_str = date.today().strftime("%Y%m%d")
    today_fmt = date.today().strftime("%d/%m/%Y")
    cookie_dict = parse_cookie_file(cookie_file)

    # ══════════════════════════════════════════════════════════════════
    # TRƯỜNG HỢP 1: LINK VIDEO / REEL / WATCH ĐƠN LẺ
    # ══════════════════════════════════════════════════════════════════
    if is_facebook_single_video(channel_url):
        _log("🔍 [Facebook] Phát hiện link video / reel đơn lẻ, đang lấy thông tin...")
        import yt_dlp
        ydl_opts: dict = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "socket_timeout": 20,
        }
        if cookie_file and os.path.isfile(cookie_file):
            ydl_opts["cookiefile"] = cookie_file

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(channel_url, download=False)
                if info:
                    vid_id = str(info.get("id") or "1")
                    title = info.get("title") or f"Facebook Video #{vid_id}"
                    dur_sec = int(info.get("duration") or 0)
                    upload_d = str(info.get("upload_date") or today_str)
                    views_count = int(info.get("view_count") or 0)
                    likes_count = int(info.get("like_count") or 0)
                    date_display = f"{upload_d[6:8]}/{upload_d[4:6]}/{upload_d[:4]}" if len(upload_d) == 8 else today_fmt

                    video_item = {
                        "id": vid_id,
                        "title": title[:200],
                        "url": info.get("webpage_url") or channel_url,
                        "duration": _fmt_duration(dur_sec),
                        "duration_sec": dur_sec,
                        "views": _fmt_number(views_count),
                        "views_raw": views_count,
                        "likes": _fmt_number(likes_count),
                        "likes_raw": likes_count,
                        "upload_date": date_display,
                        "upload_date_raw": upload_d,
                        "view_count": views_count,
                        "like_count": likes_count,
                    }
                    _log(f"✅ [Facebook] Đã nhận diện video: {title[:40]}")
                    return [video_item]
        except Exception as e:
            _log(f"⚠ yt-dlp không trích xuất được metadata trực tiếp ({e}), sử dụng ID từ URL...")

        # Fallback tạo entry từ ID URL
        m_id = (
            re.search(r"[?&/]v[=/](\d+)", channel_url)
            or re.search(r"/reel/(\d+)", channel_url)
            or re.search(r"/videos/(\d+)", channel_url)
        )
        vid_id = m_id.group(1) if m_id else "1"
        return [{
            "id": vid_id,
            "title": f"Facebook Video #{vid_id}",
            "url": channel_url,
            "duration": "--:--",
            "duration_sec": 0,
            "views": "--",
            "views_raw": 0,
            "likes": "--",
            "likes_raw": 0,
            "upload_date": today_fmt,
            "upload_date_raw": today_str,
            "view_count": 0,
            "like_count": 0,
        }]

    # ══════════════════════════════════════════════════════════════════
    # TRƯỜNG HỢP 2: TRANG / FANPAGE / HỒ SƠ FACEBOOK
    # ══════════════════════════════════════════════════════════════════
    _log("🔍 [Facebook] Đang phân giải liên kết trang...")

    # Chuẩn hoá URL thành dạng https://www.facebook.com/.../videos
    clean_url = channel_url.strip().rstrip("/")
    for pref in ["https://mbasic.facebook.com", "https://m.facebook.com", "http://facebook.com", "https://web.facebook.com"]:
        if clean_url.startswith(pref):
            clean_url = clean_url.replace(pref, "https://www.facebook.com", 1)
            break
    if not clean_url.startswith("https://www.facebook.com"):
        clean_url = "https://www.facebook.com/" + clean_url.lstrip("/")

    if not clean_url.endswith("/videos") and "/videos" not in clean_url and "/reels" not in clean_url:
        target_url = clean_url + "/videos"
    else:
        target_url = clean_url

    _log(f"🔍 [Facebook] Đang truy xuất danh sách video từ: {target_url}")

    video_records: dict[str, dict] = {}
    collected_vids: List[str] = []
    seen_ids = set()

    def _parse_fb_json_objects(obj):
        """Đệ quy phân tích cấu trúc JSON của Facebook để bóc tách thông tin video."""
        if isinstance(obj, dict):
            vid_id = None
            if "video" in obj and isinstance(obj["video"], dict) and "id" in obj["video"]:
                vid_id = str(obj["video"]["id"])
            elif obj.get("__typename") == "Video" and "id" in obj:
                vid_id = str(obj["id"])

            if vid_id and vid_id.isdigit() and len(vid_id) >= 10:
                if vid_id not in video_records:
                    video_records[vid_id] = {
                        "id": vid_id,
                        "title": "",
                        "duration_sec": 0,
                        "views_raw": 0,
                        "likes_raw": 0,
                        "publish_time": 0,
                    }
                    if vid_id not in seen_ids:
                        seen_ids.add(vid_id)
                        collected_vids.append(vid_id)

                vmeta = video_records[vid_id]

                # Thời lượng video
                dur = obj.get("playable_duration")
                if not dur and "video" in obj and isinstance(obj["video"], dict):
                    dur = obj["video"].get("playable_duration")
                if not dur and "playable_duration_in_ms" in obj:
                    try:
                        dur = int(obj["playable_duration_in_ms"]) // 1000
                    except Exception:
                        pass
                if dur and not vmeta["duration_sec"]:
                    try:
                        vmeta["duration_sec"] = int(dur)
                    except Exception:
                        pass

                # Lượt xem (play_count)
                views = obj.get("play_count")
                if not views and "video" in obj and isinstance(obj["video"], dict):
                    views = obj["video"].get("play_count")
                if views and not vmeta["views_raw"]:
                    try:
                        vmeta["views_raw"] = int(views)
                    except Exception:
                        pass

                # Lượt thích / tương tác (reaction_count)
                fb_info = obj.get("feedback")
                if isinstance(fb_info, dict) and "reaction_count" in fb_info:
                    rc = fb_info["reaction_count"]
                    try:
                        vmeta["likes_raw"] = int(rc.get("count", 0) if isinstance(rc, dict) else rc)
                    except Exception:
                        pass
                elif "reaction_count" in obj and not vmeta["likes_raw"]:
                    rc = obj["reaction_count"]
                    try:
                        vmeta["likes_raw"] = int(rc.get("count", 0) if isinstance(rc, dict) else rc)
                    except Exception:
                        pass

                # Tiêu đề / Mô tả
                t_obj = obj.get("savable_title") or obj.get("video_title") or obj.get("message")
                if isinstance(t_obj, dict) and "text" in t_obj:
                    if t_obj["text"] and not vmeta["title"]:
                        vmeta["title"] = str(t_obj["text"]).strip().split("\n")[0][:150]
                elif isinstance(t_obj, str) and t_obj and not vmeta["title"]:
                    vmeta["title"] = t_obj.strip().split("\n")[0][:150]

                # Ngày đăng (timestamp)
                ptime = obj.get("publish_time") or obj.get("creation_time")
                if ptime and not vmeta["publish_time"]:
                    try:
                        vmeta["publish_time"] = int(ptime)
                    except Exception:
                        pass

            for k, v in obj.items():
                _parse_fb_json_objects(v)
        elif isinstance(obj, list):
            for item in obj:
                _parse_fb_json_objects(item)

    # ── Chiến lược 1: curl_cffi giả lập Chrome 120 (vượt TLS chặn của Meta) ──
    try:
        from curl_cffi import requests as cffi_requests
        import json
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.facebook.com/",
        }

        resp = cffi_requests.get(
            target_url,
            impersonate="chrome120",
            headers=headers,
            cookies=cookie_dict if cookie_dict else None,
            timeout=15,
        )

        if resp.status_code == 200:
            html_text = resp.text

            # 1. Bóc tách JSON scripts có chứa metadata video
            scripts = re.findall(r'<script type="application/json"[^>]*>(.*?)</script>', html_text)
            for s in scripts:
                if any(kw in s for kw in ["ChannelTabVideo", "all_videos", "_videos", "playable_duration", "play_count"]):
                    try:
                        d = json.loads(s)
                        _parse_fb_json_objects(d)
                    except Exception:
                        pass

            # 2. Bổ sung các video IDs qua regex nếu chưa có
            for m in re.finditer(r'\"video\":\{\"id\":\"(\d+)\"', html_text):
                vid = m.group(1)
                if vid not in seen_ids:
                    seen_ids.add(vid)
                    collected_vids.append(vid)

            for m in re.finditer(r'/(?:watch\/\?v=|reel\/)(\d+)', html_text):
                vid = m.group(1)
                if vid not in seen_ids:
                    seen_ids.add(vid)
                    collected_vids.append(vid)

            for m in re.finditer(r'\/videos\/(\d+)', html_text):
                vid = m.group(1)
                if vid not in seen_ids:
                    seen_ids.add(vid)
                    collected_vids.append(vid)

            _log(f"✔ [Facebook] Đã trích xuất {len(collected_vids)} video kèm metadata từ trang.")
    except Exception as e:
        _log(f"⚠ [Facebook] curl_cffi cảnh báo: {e}")

    # ── Chiến lược 2: Nếu có Cookie và chưa đủ số lượng, quét thêm qua mbasic ──
    if len(collected_vids) < max_videos and cookie_dict:
        try:
            import requests
            from bs4 import BeautifulSoup
            mbasic_url = target_url.replace("https://www.facebook.com", "https://mbasic.facebook.com")
            m_headers = {
                "User-Agent": (
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1"
                ),
                "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": "https://mbasic.facebook.com/",
            }
            m_resp = requests.get(
                mbasic_url,
                headers=m_headers,
                cookies=cookie_dict,
                timeout=12,
                allow_redirects=True,
            )
            if m_resp.status_code == 200 and "login" not in m_resp.url:
                soup = BeautifulSoup(m_resp.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    h = a["href"]
                    m_v = (
                        re.search(r"[?&]v=(\d+)", h)
                        or re.search(r"/videos/(\d+)", h)
                        or re.search(r"/reel/(\d+)", h)
                    )
                    if m_v:
                        vid = m_v.group(1)
                        if vid not in seen_ids:
                            seen_ids.add(vid)
                            collected_vids.append(vid)
                            if len(collected_vids) >= max_videos:
                                break
        except Exception:
            pass

    if not collected_vids:
        raise RuntimeError(
            "Không tìm thấy video nào trên trang Facebook này.\n"
            "• Hãy đảm bảo đường link Facebook công khai.\n"
            "• Nếu là trang nhóm/cá nhân cần đăng nhập, hãy nạp file cookies.txt vào OmniGrab."
        )

    # Xây dựng danh sách kết quả với thông tin chi tiết
    all_videos: List[dict] = []
    for idx, vid in enumerate(collected_vids[:max_videos]):
        vurl = f"https://www.facebook.com/watch/?v={vid}"
        meta = video_records.get(vid, {})

        title = meta.get("title") or f"Facebook Video #{idx + 1} (ID: {vid})"
        dur_sec = meta.get("duration_sec", 0)
        views_raw = meta.get("views_raw", 0)
        likes_raw = meta.get("likes_raw", 0)
        ptime = meta.get("publish_time", 0)

        if ptime:
            fmt_date, raw_date = _fmt_upload_date(ptime)
        else:
            fmt_date, raw_date = today_fmt, today_str

        entry = {
            "id": vid,
            "title": title,
            "url": vurl,
            "duration": _fmt_duration(dur_sec) if dur_sec > 0 else "--:--",
            "duration_sec": dur_sec,
            "views": _fmt_number(views_raw) if views_raw > 0 else "--",
            "views_raw": views_raw,
            "likes": _fmt_number(likes_raw) if likes_raw > 0 else "--",
            "likes_raw": likes_raw,
            "upload_date": fmt_date,
            "upload_date_raw": raw_date,
            "view_count": views_raw,
            "like_count": likes_raw,
        }
        all_videos.append(entry)
        _log(f"✔ [Facebook] Video ({len(all_videos)}/{min(len(collected_vids), max_videos)}): {title[:35]}")

    _log(f"✅ [Facebook] Quét hoàn tất! Tìm thấy {len(all_videos)} video.")
    return all_videos
