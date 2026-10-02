"""
core/downloader.py - Cấu hình wrapper yt-dlp tối ưu cho từng nền tảng.

Hỗ trợ:
- TikTok / Douyin: Tải MP4 độ phân giải cao nhất, không watermark.
- Facebook: Tải chất lượng cao nhất, tự động ghép bằng ffmpeg.
- Tùy chọn cookie, thư mục lưu, resume khi gián đoạn.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


@dataclass
class DownloadConfig:
    """Cấu hình cho phiên tải video."""

    output_dir: str = ""
    cookie_file: str = ""
    ffmpeg_path: str = ""
    file_template: str = "%(extractor)s_%(title).40s_%(id)s.%(ext)s"

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
        # Cấu hình mặc định cho các nền tảng khác
        opts["format"] = "bestvideo+bestaudio/best"
        opts["merge_output_format"] = "mp4"

    # Gắn hooks tiến trình
    if config.progress_hook:
        opts["progress_hooks"] = [config.progress_hook]

    if config.postprocessor_hook:
        opts["postprocessor_hooks"] = [config.postprocessor_hook]

    return opts


def _get_tiktok_douyin_opts() -> Dict[str, Any]:
    """
    Tùy chọn tối ưu cho TikTok / Douyin.

    Ưu tiên:
    - Luồng MP4 trực tiếp, không watermark.
    - Độ phân giải cao nhất khả dụng.
    """
    return {
        # Tối ưu: Lấy bản H.264 (avc) để xem trên Windows, ưu tiên bản đã gộp sẵn (best) hoặc tự gộp
        "format": "best[vcodec*=avc]/bestvideo[vcodec*=avc]+bestaudio/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        # Thêm referer để vượt qua kiểm tra nguồn
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

    Ưu tiên:
    - Chất lượng cao nhất (video + audio riêng, ghép bằng ffmpeg).
    - Hỗ trợ video từ nhóm riêng tư (cần cookie).
    """
    return {
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "postprocessors": [
            {
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }
        ],
    }


def download_single_video(config: DownloadConfig, url: str) -> dict[str, Any]:
    """
    Tải một video đơn lẻ.

    Args:
        config: Cấu hình tải.
        url: URL video cần tải.

    Returns:
        Dict chứa thông tin kết quả:
          - "success" (bool): Tải thành công hay không.
          - "url" (str): URL đã tải.
          - "title" (str): Tiêu đề video (nếu có).
          - "error" (str): Thông báo lỗi (nếu thất bại).
    """
    import yt_dlp

    opts = build_ydl_opts(config, url)

    result: dict[str, Any] = {
        "success": False,
        "url": url,
        "title": "",
        "error": "",
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info:
                result["success"] = True
                result["title"] = info.get("title", "Không rõ tiêu đề")
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
