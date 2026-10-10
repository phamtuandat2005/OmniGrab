"""
core/downloader.py - Cấu hình wrapper yt-dlp tối ưu cho từng nền tảng.

Hỗ trợ:
- TikTok / Douyin: Tải MP4 độ phân giải cao nhất, không watermark.
- Facebook: Tải chất lượng cao nhất, tự động ghép bằng ffmpeg.
- Tùy chọn cookie, thư mục lưu, resume khi gián đoạn.
- Hỗ trợ xuất chỉ âm thanh (.mp3) và mẫu đặt tên file linh hoạt.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


@dataclass
class DownloadConfig:
    """Cấu hình cho phiên tải video."""

    output_dir: str = ""
    cookie_file: str = ""
    ffmpeg_path: str = ""
    file_template: str = "%(extractor)s_%(title).40s_%(id)s.%(ext)s"
    audio_only: bool = False  # Nếu True, xuất chỉ âm thanh (.mp3)

    # Callbacks để gửi tín hiệu tiến trình về UI
    progress_hook: Optional[Callable[[Dict[str, Any]], None]] = None
    postprocessor_hook: Optional[Callable[[Dict[str, Any]], None]] = None

    def __post_init__(self) -> None:
        """Tự động phát hiện ffmpeg nếu chưa được cấu hình."""
        if not self.ffmpeg_path:
            self.ffmpeg_path = _detect_ffmpeg()


def _detect_ffmpeg() -> str:
    """
    Tự động phát hiện đường dẫn ffmpeg.

    Tìm kiếm theo thứ tự:
    1. Thư mục ứng dụng hiện tại (cho bản đóng gói Nuitka/PyInstaller).
    2. Biến môi trường PATH.

    Returns:
        Đường dẫn thư mục chứa ffmpeg, hoặc chuỗi rỗng nếu không tìm thấy.
    """
    from core.security import get_base_path

    # Kiểm tra trong thư mục ứng dụng và thư mục cha
    app_dir = get_base_path()
    parent_dir = os.path.dirname(app_dir)

    for search_dir in [app_dir, parent_dir]:
        ffmpeg_exe = os.path.join(search_dir, "ffmpeg.exe")
        ffmpeg_bin = os.path.join(search_dir, "ffmpeg")
        if os.path.isfile(ffmpeg_exe) or os.path.isfile(ffmpeg_bin):
            return search_dir

    # Kiểm tra trong PATH
    ffmpeg_in_path = shutil.which("ffmpeg")
    if ffmpeg_in_path:
        return os.path.dirname(ffmpeg_in_path)

    return ""


def build_ydl_opts(config: DownloadConfig, url: str) -> Dict[str, Any]:
    """
    Xây dựng dict tùy chọn cho yt-dlp, tối ưu theo nền tảng.

    Args:
        config: Cấu hình tải.
        url: URL video cần tải.

    Returns:
        Dict tùy chọn yt-dlp.
    """
    # Xác định nền tảng từ URL
    url_lower = url.lower()
    is_tiktok = "tiktok.com" in url_lower
    is_douyin = "douyin.com" in url_lower
    is_facebook = "facebook.com" in url_lower or "fb.watch" in url_lower or "fb.com" in url_lower

    # Tùy chọn cơ bản
    opts: Dict[str, Any] = {
        "outtmpl": os.path.join(config.output_dir, config.file_template),
        "noplaylist": True,
        "ignoreerrors": False,
        "no_warnings": False,
        "quiet": True,
        "no_color": True,
        "retries": 3,
        "fragment_retries": 5,
        "continuedl": True,        # Resume tải dở
        "noprogress": True,
        "socket_timeout": 30,
        "extractor_retries": 3,
        "file_access_retries": 3,
        # Tùy chọn mạng nâng cao
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        },
    }

    # Cấu hình ffmpeg
    if config.ffmpeg_path:
        opts["ffmpeg_location"] = config.ffmpeg_path

    # Cấu hình cookie
    if config.cookie_file and os.path.isfile(config.cookie_file):
        opts["cookiefile"] = config.cookie_file

    # Cấu hình theo nền tảng
    if is_tiktok or is_douyin:
        opts.update(_get_tiktok_douyin_opts())
    elif is_facebook:
        opts.update(_get_facebook_opts())
    else:
        # Cấu hình mặc định cho các nền tảng khác: ưu tiên H.264 (avc1) + AAC
        opts["format"] = (
            "bestvideo[vcodec^=avc1][ext=mp4]+bestaudio[acodec^=mp4a]/"
            "bestvideo[vcodec*=avc]+bestaudio/"
            "bestvideo[vcodec*=h264]+bestaudio/"
            "best[vcodec*=avc]/"
            "best[ext=mp4]/best"
        )
        opts["merge_output_format"] = "mp4"
        opts["postprocessor_args"] = {
            "ffmpeg": ["-c:v", "copy", "-c:a", "aac"]
        }

    # Gắn hooks tiến trình
    if config.progress_hook:
        opts["progress_hooks"] = [config.progress_hook]

    if config.postprocessor_hook:
        opts["postprocessor_hooks"] = [config.postprocessor_hook]

    # Chế độ chỉ âm thanh (.mp3)
    if config.audio_only:
        opts["format"] = "bestaudio/best"
        # Xóa cấu hình video nếu đã set
        opts.pop("merge_output_format", None)
        opts.pop("postprocessor_args", None)
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
        # Cập nhật template để đổi đuôi sang .mp3
        opts["outtmpl"] = os.path.join(config.output_dir, config.file_template)

    return opts


def _get_tiktok_douyin_opts() -> Dict[str, Any]:
    """
    Tùy chọn tối ưu cho TikTok / Douyin.

    Ép buộc ưu tiên video chuẩn H.264 (avc1/h264) thay vì H.265 (hevc)
    và âm thanh AAC trong container MP4 để tương thích Windows Media Player mặc định.
    """
    return {
        # 1. Ép buộc ưu tiên video chuẩn H.264 (avc1/h264) thay vì H.265 (hevc)
        "format": (
            "bestvideo[vcodec^=avc1][ext=mp4]+bestaudio[acodec^=mp4a]/"
            "bestvideo[vcodec*=avc]+bestaudio/"
            "bestvideo[vcodec*=h264]+bestaudio/"
            "best[vcodec*=avc]/"
            "best[ext=mp4]/best"
        ),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        # Đảm bảo container xuất ra là MP4 chuẩn
        "postprocessors": [
            {
                "key": "FFmpegVideoRemuxer",
                "preferedformat": "mp4",
            }
        ],
        # 2. Đảm bảo codec video là copy (h264) và codec audio là AAC
        "postprocessor_args": {
            "ffmpeg": ["-c:v", "copy", "-c:a", "aac"]
        },
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.tiktok.com/",
        },
    }


def _get_facebook_opts() -> Dict[str, Any]:
    """
    Tùy chọn tối ưu cho Facebook.

    Ưu tiên H.264 + AAC để tương thích mọi máy Windows.
    """
    return {
        "format": (
            "bestvideo[vcodec^=avc1][ext=mp4]+bestaudio[acodec^=mp4a]/"
            "bestvideo[vcodec*=avc]+bestaudio/"
            "bestvideo[vcodec*=h264]+bestaudio/"
            "best[vcodec*=avc]/"
            "bestvideo+bestaudio/best"
        ),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [
            {
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }
        ],
        "postprocessor_args": {
            "ffmpeg": ["-c:v", "copy", "-c:a", "aac"]
        },
    }


def ensure_h264_compatibility(video_path: str, ffmpeg_dir: str = "") -> None:
    """
    Kiểm tra nếu video là HEVC (H.265) thì tự động chuyển về H.264 tương thích mọi máy Windows.
    Đảm bảo video xem được trên Windows Media Player mặc định không bị lỗi codec.
    """
    if not video_path or not os.path.isfile(video_path):
        return

    # Bỏ qua nếu là file âm thanh
    if video_path.lower().endswith((".mp3", ".m4a", ".wav", ".aac")):
        return

    temp_path = ""
    try:
        # Tự động tìm đường dẫn ffprobe / ffmpeg
        if not ffmpeg_dir:
            ffmpeg_dir = _detect_ffmpeg()

        ffprobe_bin = (
            os.path.join(ffmpeg_dir, "ffprobe.exe")
            if ffmpeg_dir and os.path.isfile(os.path.join(ffmpeg_dir, "ffprobe.exe"))
            else "ffprobe"
        )
        ffmpeg_bin = (
            os.path.join(ffmpeg_dir, "ffmpeg.exe")
            if ffmpeg_dir and os.path.isfile(os.path.join(ffmpeg_dir, "ffmpeg.exe"))
            else "ffmpeg"
        )

        # Lấy thông tin codec video bằng ffprobe
        cmd_probe = f'"{ffprobe_bin}" -v error -select_streams v:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 "{video_path}"'
        codec = subprocess.check_output(
            cmd_probe,
            shell=True,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=20,
        ).strip().lower()

        if codec in ["hevc", "h265"]:
            base, ext = os.path.splitext(video_path)
            temp_path = f"{base}_h264{ext}"
            cmd_convert = (
                f'"{ffmpeg_bin}" -y -i "{video_path}" '
                f'-c:v libx264 -preset fast -crf 22 -c:a copy "{temp_path}"'
            )
            subprocess.run(
                cmd_convert,
                shell=True,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=600,
            )

            # Ghi đè file cũ
            if os.path.isfile(temp_path) and os.path.getsize(temp_path) > 0:
                os.replace(temp_path, video_path)
    except Exception:
        # Nếu có lỗi thì dọn dẹp file tạm (nếu có) và giữ nguyên file gốc
        if temp_path and os.path.isfile(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def download_douyin_video(config: DownloadConfig, url: str) -> dict[str, Any]:
    """
    Tải trực tiếp video hoặc album ảnh Douyin không logo qua CDN.
    Khắc phục triệt để lỗi 403 Forbidden của yt-dlp đối với Douyin.
    """
    import re
    import requests as _requests

    result: dict[str, Any] = {
        "success": False,
        "url": url,
        "title": "",
        "file_path": "",
        "error": "",
    }

    # 1. Trích xuất ID bài đăng (aweme_id)
    aweme_id = ""
    for pat in [r"/video/(\d+)", r"/note/(\d+)", r"(\d{15,22})"]:
        m = re.search(pat, url)
        if m:
            aweme_id = m.group(1)
            break

    if not aweme_id:
        try:
            ua_probe = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
            r = _requests.head(url, allow_redirects=True, timeout=10, headers={"User-Agent": ua_probe})
            for pat in [r"/video/(\d+)", r"/note/(\d+)", r"(\d{15,22})"]:
                m = re.search(pat, r.url)
                if m:
                    aweme_id = m.group(1)
                    break
        except Exception:
            pass

    if not aweme_id:
        result["error"] = "Không thể trích xuất ID video Douyin từ liên kết."
        return result

    # 2. Lấy thông tin chi tiết qua API Douyin (ABogusManager + x-tt-argus)
    try:
        from core.channel_scrapers import parse_cookie_file
        from f2.apps.douyin.utils import ABogusManager, TokenManager
        from f2.apps.douyin.model import PostDetail
        from f2.apps.douyin.api import DouyinAPIEndpoints

        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        params = PostDetail(aweme_id=aweme_id)
        endpoint = ABogusManager.model_2_endpoint(ua, DouyinAPIEndpoints.POST_DETAIL, params.model_dump())

        cookie_dict = parse_cookie_file(config.cookie_file)
        if "ttwid" not in cookie_dict:
            try:
                cookie_dict["ttwid"] = TokenManager.gen_ttwid()
            except Exception:
                pass
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookie_dict.items() if k)

        headers = {
            "User-Agent": ua,
            "Referer": f"https://www.douyin.com/video/{aweme_id}",
            "Cookie": cookie_str,
            "Accept": "application/json, text/plain, */*",
            "x-tt-argus": "1",
        }

        session = None
        try:
            from curl_cffi import requests as cffi_requests
            session = cffi_requests.Session(impersonate="chrome120")
        except Exception:
            session = _requests.Session()

        resp = session.get(endpoint, headers=headers, timeout=15)
        if resp.status_code != 200:
            result["error"] = f"Douyin API trả về HTTP {resp.status_code}"
            return result

        data = resp.json()
        detail = data.get("aweme_detail") or {}
        if not detail:
            result["error"] = "Không tìm thấy thông tin video từ Douyin (video có thể bị ẩn hoặc xóa)."
            return result

    except Exception as e:
        result["error"] = f"Lỗi lấy dữ liệu Douyin: {e}"
        return result

    # 3. Chuẩn bị thư mục và tên file
    os.makedirs(config.output_dir, exist_ok=True)
    raw_title = detail.get("desc") or f"douyin_{aweme_id}"
    safe_title = "".join(c for c in raw_title if c not in '\\/:*?"<>|\r\n').strip()[:60] or f"douyin_{aweme_id}"
    result["title"] = safe_title

    images = detail.get("images") or []
    is_image_album = bool(images) or (detail.get("aweme_type") == 68)

    # 4. TRƯỜNG HỢP A: BÀI ĐĂNG ALBUM ẢNH (Image Note / 图集)
    if is_image_album:
        music_urls = (
            detail.get("video", {}).get("play_addr", {}).get("url_list")
            or detail.get("music", {}).get("play_url", {}).get("url_list")
            or []
        )

        # A1. Nếu chỉ cần âm thanh (.mp3)
        if config.audio_only:
            if not music_urls:
                result["error"] = "Bài đăng ảnh này không có file âm thanh nền."
                return result

            mp3_path = os.path.join(config.output_dir, f"{safe_title}_{aweme_id}.mp3")
            try:
                r_m = _requests.get(music_urls[0], timeout=20)
                with open(mp3_path, "wb") as f:
                    f.write(r_m.content)
                result["success"] = True
                result["file_path"] = mp3_path
                if config.progress_hook:
                    config.progress_hook({"status": "finished", "filename": mp3_path})
                return result
            except Exception as e:
                result["error"] = f"Lỗi tải âm thanh album ảnh: {e}"
                return result

        # A2. Tải toàn bộ ảnh chất lượng cao + nhạc nền
        downloaded_imgs = []
        for idx, img in enumerate(images):
            u_list = img.get("url_list") or []
            img_url = u_list[-1] if u_list else ""
            for u in u_list:
                if any(ext in u for ext in [".jpeg", ".jpg", ".png"]):
                    img_url = u
                    break
            if img_url:
                try:
                    r_i = _requests.get(img_url, timeout=20)
                    suffix = f"_{idx+1}" if len(images) > 1 else ""
                    img_fp = os.path.join(config.output_dir, f"{safe_title}_{aweme_id}{suffix}.jpg")
                    with open(img_fp, "wb") as f:
                        f.write(r_i.content)
                    downloaded_imgs.append(img_fp)
                except Exception:
                    pass

        # Tải nhạc nền nếu có
        saved_audio = ""
        if music_urls:
            try:
                r_m = _requests.get(music_urls[0], timeout=20)
                saved_audio = os.path.join(config.output_dir, f"{safe_title}_{aweme_id}_audio.mp3")
                with open(saved_audio, "wb") as f:
                    f.write(r_m.content)
            except Exception:
                pass

        # Tự động dùng ffmpeg ghép thành video .mp4 hoàn chỉnh nếu có ảnh và nhạc
        mp4_out = os.path.join(config.output_dir, f"{safe_title}_{aweme_id}.mp4")
        if downloaded_imgs and saved_audio:
            ffmpeg_dir = config.ffmpeg_path or _detect_ffmpeg()
            ffmpeg_bin = os.path.join(ffmpeg_dir, "ffmpeg.exe") if ffmpeg_dir and os.path.isfile(os.path.join(ffmpeg_dir, "ffmpeg.exe")) else "ffmpeg"
            try:
                cmd = (
                    f'"{ffmpeg_bin}" -y -loop 1 -i "{downloaded_imgs[0]}" -i "{saved_audio}" '
                    f'-c:v libx264 -tune stillimage -c:a aac -b:a 192k -pix_fmt yuv420p -shortest "{mp4_out}"'
                )
                subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
                if os.path.isfile(mp4_out) and os.path.getsize(mp4_out) > 0:
                    result["success"] = True
                    result["file_path"] = mp4_out
                    if config.progress_hook:
                        config.progress_hook({"status": "finished", "filename": mp4_out})
                    return result
            except Exception:
                pass

        # Nếu không ghép được thành video thì trả về đường dẫn ảnh đầu tiên
        if downloaded_imgs:
            result["success"] = True
            result["file_path"] = downloaded_imgs[0]
            if config.progress_hook:
                config.progress_hook({"status": "finished", "filename": downloaded_imgs[0]})
            return result

        result["error"] = "Không tải được file ảnh từ bài đăng Douyin này."
        return result

    # 5. TRƯỜNG HỢP B: VIDEO MP4 THÔNG THƯỜNG
    video_obj = detail.get("video") or {}
    play_addr = video_obj.get("play_addr") or {}
    raw_urls = play_addr.get("url_list") or []

    # Nếu không có trong play_addr, tìm trong bit_rate
    if not raw_urls and "bit_rate" in video_obj:
        for br in video_obj.get("bit_rate") or []:
            if isinstance(br, dict) and "play_addr" in br:
                raw_urls = br["play_addr"].get("url_list") or []
                if raw_urls:
                    break

    if not raw_urls:
        result["error"] = "Không tìm thấy luồng video có thể tải cho video Douyin này."
        return result

    # Chọn URL video chất lượng cao không watermark (thay playwm thành play)
    target_video_url = raw_urls[0].replace("playwm", "play")

    ext = "mp3" if config.audio_only else "mp4"
    out_file = os.path.join(config.output_dir, f"{safe_title}_{aweme_id}.{ext}")

    try:
        if config.audio_only:
            # Tải audio từ music nếu có
            music_obj = detail.get("music") or {}
            m_urls = music_obj.get("play_url", {}).get("url_list") or []
            if m_urls:
                r_m = _requests.get(m_urls[0], timeout=30)
                with open(out_file, "wb") as f:
                    f.write(r_m.content)
                result["success"] = True
                result["file_path"] = out_file
                if config.progress_hook:
                    config.progress_hook({"status": "finished", "filename": out_file})
                return result

        # Tải luồng video MP4 trực tiếp
        with _requests.get(target_video_url, stream=True, timeout=30, headers={"User-Agent": ua, "Referer": "https://www.douyin.com/"}) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(out_file, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if config.progress_hook and total_size > 0:
                            pct = f"{(downloaded / total_size) * 100:.1f}%"
                            config.progress_hook({
                                "status": "downloading",
                                "_percent_str": pct,
                                "_speed_str": "CDN",
                                "filename": out_file,
                            })

        # Nếu audio_only và đã tải MP4: convert sang mp3
        if config.audio_only and out_file.endswith(".mp4"):
            mp3_file = os.path.splitext(out_file)[0] + ".mp3"
            ffmpeg_dir = config.ffmpeg_path or _detect_ffmpeg()
            ffmpeg_bin = os.path.join(ffmpeg_dir, "ffmpeg.exe") if ffmpeg_dir and os.path.isfile(os.path.join(ffmpeg_dir, "ffmpeg.exe")) else "ffmpeg"
            cmd_a = f'"{ffmpeg_bin}" -y -i "{out_file}" -vn -c:a libmp3lame -q:a 2 "{mp3_file}"'
            try:
                subprocess.run(cmd_a, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
                if os.path.isfile(mp3_file):
                    os.remove(out_file)
                    out_file = mp3_file
            except Exception:
                pass
        elif not config.audio_only:
            ensure_h264_compatibility(out_file, config.ffmpeg_path)

        result["success"] = True
        result["file_path"] = out_file
        if config.progress_hook:
            config.progress_hook({"status": "finished", "filename": out_file})
        return result

    except Exception as e:
        result["error"] = f"Lỗi tải video Douyin: {e}"
        return result


def download_single_video(config: DownloadConfig, url: str) -> dict[str, Any]:
    """
    Tải một video đơn lẻ.

    Args:
        config: Cấu hình tải.
        url: URL video cần tải.

    Returns:
        Dict chứa thông tin kết quả.
    """
    # ── ĐỊNH TUYẾN RIÊNG CHO DOUYIN (VƯỢT LỖI 403 YT-DLP) ──
    url_lower = (url or "").lower()
    if "douyin.com" in url_lower or "v.douyin.com" in url_lower:
        douyin_res = download_douyin_video(config, url)
        if douyin_res.get("success"):
            return douyin_res
        # Nếu có thông báo lỗi cụ thể, ưu tiên trả về
        if douyin_res.get("error"):
            return douyin_res

    import yt_dlp

    opts = build_ydl_opts(config, url)

    # Thu thập đường dẫn file đã hoàn tất từ hook
    downloaded_files: list[str] = []

    def _track_finished_file(d: dict[str, Any]) -> None:
        if d.get("status") == "finished":
            fn = d.get("filename")
            if fn and fn not in downloaded_files:
                downloaded_files.append(fn)

    # Gắn hook theo dõi file
    prog_hooks = opts.get("progress_hooks", [])
    opts["progress_hooks"] = prog_hooks + [_track_finished_file]

    result: dict[str, Any] = {
        "success": False,
        "url": url,
        "title": "",
        "file_path": "",
        "error": "",
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info:
                result["success"] = True
                result["title"] = info.get("title", "Không rõ tiêu đề")

                # Tìm đường dẫn file video đầu ra
                output_file = ""

                # 1. Kiểm tra requested_downloads (yt-dlp chuẩn)
                req_downloads = info.get("requested_downloads") or []
                for rd in req_downloads:
                    fp = rd.get("filepath") or rd.get("_filename")
                    if fp and os.path.isfile(fp):
                        output_file = fp
                        break

                # 2. Kiểm tra filepath / _filename trực tiếp từ info
                if not output_file:
                    fp = info.get("filepath") or info.get("_filename")
                    if fp and os.path.isfile(fp):
                        output_file = fp

                # 3. Kiểm tra prepare_filename từ ydl
                if not output_file:
                    try:
                        cand = ydl.prepare_filename(info)
                        if os.path.isfile(cand):
                            output_file = cand
                        else:
                            cand_mp4 = os.path.splitext(cand)[0] + ".mp4"
                            if os.path.isfile(cand_mp4):
                                output_file = cand_mp4
                    except Exception:
                        pass

                # 4. Kiểm tra các file đã ghi nhận qua hooks
                if not output_file and downloaded_files:
                    for fp in reversed(downloaded_files):
                        if os.path.isfile(fp):
                            output_file = fp
                            break
                        fp_mp4 = os.path.splitext(fp)[0] + ".mp4"
                        if os.path.isfile(fp_mp4):
                            output_file = fp_mp4
                            break

                # Tự động kiểm tra và chuyển đổi H.264 nếu video dính HEVC
                if output_file and not config.audio_only:
                    ensure_h264_compatibility(output_file, config.ffmpeg_path)

                result["file_path"] = output_file
            else:
                result["error"] = "Không thể trích xuất thông tin video."
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        # Dịch một số lỗi phổ biến sang Tiếng Việt
        if "Video unavailable" in error_msg or "not available" in error_msg:
            result["error"] = "Video không khả dụng hoặc đã bị xóa."
        elif "Private video" in error_msg:
            result["error"] = "Video riêng tư - cần cookie xác thực."
        elif "Sign in" in error_msg or "login" in error_msg.lower():
            result["error"] = "Yêu cầu đăng nhập - hãy cung cấp file cookie."
        else:
            result["error"] = f"Lỗi tải: {error_msg}"
    except Exception as e:
        result["error"] = f"Lỗi không xác định: {str(e)}"

    return result


def scan_channel_videos(
    channel_url: str,
    max_videos: int = 50,
    cookie_file: str = "",
    progress_callback: Optional[Callable[[str], None]] = None,
) -> list[dict[str, Any]]:
    """
    Quét danh sách video từ Kênh / Hồ sơ người dùng.

    Tự động định tuyến giải pháp:
    - Douyin   : Cổng API bóc tách mở TikWM (HOÀN TOÀN KHÔNG CẦN COOKIE).
    - Facebook : Sử dụng mbasic.facebook.com endpoint.
    - Nền tảng khác: Dùng yt-dlp với extract_flat='in_playlist'.

    Args:
        channel_url: URL trang cá nhân hoặc kênh.
        max_videos: Số video tối đa cần quét.
        cookie_file: Đường dẫn file cookie Netscape (.txt).
        progress_callback: Callback nhận thông báo tiến trình.

    Returns:
        Danh sách video dict chuẩn hóa.
    """
    from core.channel_scrapers import (
        is_douyin_channel,
        is_facebook_channel,
        scan_douyin_channel,
        scan_facebook_channel,
    )

    u_lower = (channel_url or "").lower()
    # Kiểm tra kênh Douyin: TUYỆT ĐỐI KHÔNG dùng yt-dlp vì bị chặn chữ ký a_bogus.
    # Dùng cổng API mở TikWM hoàn toàn không cần cookie và không bắt đăng nhập.
    if is_douyin_channel(channel_url) or "douyin.com" in u_lower or "v.douyin.com" in u_lower:
        return scan_douyin_channel(
            channel_url=channel_url,
            max_videos=max_videos,
            cookie_file=cookie_file,
            progress_cb=progress_callback,
        )

    if is_facebook_channel(channel_url):
        return scan_facebook_channel(
            channel_url=channel_url,
            max_videos=max_videos,
            cookie_file=cookie_file,
            progress_cb=progress_callback,
        )

    # Mặc định dùng yt-dlp
    import yt_dlp
    opts: dict[str, Any] = {
        "extract_flat": "in_playlist",
        "playlistend": max_videos,
        "quiet": True,
        "no_warnings": True,
        "no_color": True,
        "ignoreerrors": True,
        "socket_timeout": 30,
    }
    if cookie_file and os.path.isfile(cookie_file):
        opts["cookiefile"] = cookie_file

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)
        if not info:
            return []
        entries = info.get("entries") or []
        res = []
        for e in entries:
            if not e:
                continue
            res.append({
                "id": e.get("id", ""),
                "title": e.get("title") or e.get("fulltitle") or "",
                "url": e.get("url") or e.get("webpage_url", ""),
                "duration": e.get("duration", 0),
                "view_count": e.get("view_count", 0),
                "like_count": e.get("like_count", 0),
                "upload_date": e.get("upload_date", ""),
            })
            if len(res) >= max_videos:
                break
        return res
