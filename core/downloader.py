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
          - "file_path" (str): Đường dẫn file đã tải (nếu thành công).
          - "error" (str): Thông báo lỗi (nếu thất bại).
    """
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
