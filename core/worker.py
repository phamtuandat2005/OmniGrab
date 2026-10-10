"""
core/worker.py - QThread xử lý tải đa luồng nền.

Đảm bảo:
- UI không bị đơ khi đang tải.
- Phát tín hiệu pyqtSignal về UI với thông điệp Tiếng Việt.
- Hỗ trợ dừng tải an toàn (Graceful Stop).
- Tải đồng thời nhiều video bằng ThreadPoolExecutor.
- Quét danh sách video từ Kênh/Hồ sơ bằng ScanChannelWorker.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional

# pyrefly: ignore [missing-import]
from PyQt6.QtCore import QThread, pyqtSignal

from core.downloader import DownloadConfig, download_single_video


class DownloadWorker(QThread):
    """
    Luồng nền xử lý tải hàng loạt video.

    Signals:
        status_updated(str): Cập nhật trạng thái tổng quan.
        progress_updated(float, str): Tiến trình tổng thể (%) và chi tiết.
        item_finished(str, bool, str): URL, thành công/thất bại, chi tiết.
        log_message(str): Thông điệp nhật ký với mốc thời gian.
        batch_finished(int, int): Tổng thành công, tổng thất bại.
    """

    # === Tín hiệu giao tiếp với UI ===
    status_updated = pyqtSignal(str)
    progress_updated = pyqtSignal(float, str)
    item_finished = pyqtSignal(str, bool, str)
    log_message = pyqtSignal(str)
    batch_finished = pyqtSignal(int, int)

    def __init__(
        self,
        urls: List[str],
        output_dir: str,
        cookie_file: str = "",
        max_workers: int = 2,
        audio_only: bool = False,
        file_template: str = "%(extractor)s_%(title).40s_%(id)s.%(ext)s",
        parent: Optional[Any] = None,
    ) -> None:
        """
        Khởi tạo luồng tải.

        Args:
            urls: Danh sách URL cần tải.
            output_dir: Thư mục lưu video.
            cookie_file: Đường dẫn file cookie (tùy chọn).
            max_workers: Số luồng tải đồng thời.
            parent: QObject cha.
        """
        super().__init__(parent)
        self._urls = urls
        self._output_dir = output_dir
        self._cookie_file = cookie_file
        self._max_workers = max_workers
        self._audio_only = audio_only
        self._file_template = file_template
        self._stop_requested = False
        self._failed_urls: List[str] = []

    @property
    def failed_urls(self) -> List[str]:
        """Danh sách URL tải thất bại."""
        return self._failed_urls.copy()

    def request_stop(self) -> None:
        """Yêu cầu dừng tải an toàn."""
        self._stop_requested = True
        self._log("⚠ Đã nhận yêu cầu dừng tải. Đang chờ các video hiện tại hoàn tất...")

    def run(self) -> None:
        """Điểm vào chính của luồng nền."""
        total = len(self._urls)
        success_count = 0
        fail_count = 0
        self._failed_urls = []

        self._log(f"🚀 Bắt đầu tải {total} video với {self._max_workers} luồng đồng thời.")
        self.status_updated.emit("Đang chuẩn bị tải video...")

        completed = 0

        try:
            with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
                # Submit tất cả các tác vụ tải
                future_to_url: Dict[Future[dict[str, Any]], str] = {}

                for url in self._urls:
                    if self._stop_requested:
                        break

                    config = DownloadConfig(
                        output_dir=self._output_dir,
                        cookie_file=self._cookie_file,
                        audio_only=self._audio_only,
                        file_template=self._file_template,
                        progress_hook=self._make_progress_hook(url),
                    )

                    future = executor.submit(download_single_video, config, url)
                    future_to_url[future] = url

                # Thu thập kết quả
                for future in as_completed(future_to_url):
                    if self._stop_requested and completed > 0:
                        # Hủy các tác vụ chưa bắt đầu
                        for pending_future in future_to_url:
                            pending_future.cancel()
                        break

                    url = future_to_url[future]
                    completed += 1

                    try:
                        result = future.result(timeout=300)  # Timeout 5 phút/video

                        if result["success"]:
                            success_count += 1
                            title = result.get("title", "")
                            file_path = result.get("file_path", "")
                            self.item_finished.emit(url, True, file_path)
                            self._log(
                                f"✅ [{completed}/{total}] Tải thành công: "
                                f"{title[:50] if title else url}"
                            )
                        else:
                            fail_count += 1
                            error = result.get("error", "Lỗi không xác định")
                            self._failed_urls.append(url)
                            self.item_finished.emit(url, False, error)
                            self._log(f"❌ [{completed}/{total}] Thất bại: {url}\n   → {error}")

                    except Exception as e:
                        fail_count += 1
                        error_msg = f"Lỗi luồng xử lý: {str(e)}"
                        self._failed_urls.append(url)
                        self.item_finished.emit(url, False, error_msg)
                        self._log(f"❌ [{completed}/{total}] Thất bại: {url}\n   → {error_msg}")

                    # Cập nhật tiến trình tổng thể
                    percent = (completed / total) * 100
                    detail = f"{completed}/{total} video đã xử lý"
                    self.progress_updated.emit(percent, detail)
                    self.status_updated.emit(f"Đang tải: {detail}")

        except Exception as e:
            self._log(f"❌ Lỗi nghiêm trọng: {str(e)}")

        # Kết thúc
        if self._stop_requested:
            remaining = total - completed
            self._log(
                f"⏹ Đã dừng tải. Kết quả: {success_count} thành công, "
                f"{fail_count} thất bại, {remaining} bị bỏ qua."
            )
        else:
            self._log(
                f"🏁 Hoàn tất! {success_count} thành công, {fail_count} thất bại "
                f"trên tổng {total} video."
            )

        self.status_updated.emit("Hoàn tất quá trình tải.")
        self.batch_finished.emit(success_count, fail_count)

    def _make_progress_hook(self, url: str):
        """
        Tạo progress hook cho một URL cụ thể.

        Gửi tín hiệu tiến trình từng video về UI.
        """
        def hook(d: Dict[str, Any]) -> None:
            status = d.get("status", "")

            if status == "downloading":
                percent_str = d.get("_percent_str", "").strip()
                speed_str = d.get("_speed_str", "N/A").strip()
                eta_str = d.get("_eta_str", "").strip()

                if percent_str:
                    detail = f"⬇ {percent_str} | Tốc độ: {speed_str}"
                    if eta_str:
                        detail += f" | Còn lại: {eta_str}"
                    self.status_updated.emit(detail)

            elif status == "finished":
                filename = d.get("filename", "")
                self.status_updated.emit("Đang xử lý hậu kỳ (ghép âm thanh/video)...")

        return hook

    def _log(self, message: str) -> None:
        """
        Phát thông điệp nhật ký kèm mốc thời gian.

        Args:
            message: Nội dung thông điệp.
        """
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        self.log_message.emit(f"{timestamp} {message}")


class ScanChannelWorker(QThread):
    """
    Luồng nền quét danh sách video từ Kênh / Hồ sơ TikTok, Douyin, Facebook. (v3.0)

    Dùng yt-dlp với extract_flat='in_playlist' để lấy metadata nhanh.
    Hỗ trợ bộ lọc Viral: min_views, min_likes, duration_filter, date_filter.

    Signals:
        scan_progress(str): Thông báo tiến trình quét.
        video_found(dict): Mỗi video ĐẠT bộ lọc (title, duration, views, likes, upload_date, url).
        scan_finished(list): Toàn bộ danh sách video đạt bộ lọc sau khi quét xong.
        scan_error(str): Thông báo lỗi nếu quét thất bại.
    """

    scan_progress = pyqtSignal(str)
    video_found = pyqtSignal(dict)
    scan_finished = pyqtSignal(list)
    scan_error = pyqtSignal(str)

    # Hằng số bộ lọc thời lượng
    DURATION_ALL = "Tất cả"
    DURATION_SHORT = "Dưới 60 giây (Shorts/Reels)"
    DURATION_LONG = "Trên 60 giây"

    # Hằng số bộ lọc ngày đăng
    DATE_ALL = "Tất cả"
    DATE_3DAYS = "3 ngày qua"
    DATE_7DAYS = "7 ngày qua"
    DATE_30DAYS = "30 ngày qua"

    def __init__(
        self,
        channel_url: str,
        max_videos: int = 50,
        cookie_file: str = "",
        min_views: int = 0,
        min_likes: int = 0,
        duration_filter: str = "Tất cả",
        date_filter: str = "Tất cả",
        parent=None,
    ) -> None:
        """
        Khởi tạo luồng quét kênh v3.0 với bộ lọc Viral.

        Args:
            channel_url: URL kênh / trang cá nhân cần quét.
            max_videos: Số video tối đa cần quét từ nguồn.
            cookie_file: Đường dẫn file cookie (tùy chọn).
            min_views: Số lượt xem tối thiểu (0 = không lọc).
            min_likes: Số lượt thích tối thiểu (0 = không lọc).
            duration_filter: Bộ lọc thời lượng (hằng số DURATION_*).
            date_filter: Bộ lọc ngày đăng (hằng số DATE_*).
            parent: QObject cha.
        """
        super().__init__(parent)
        self._channel_url = channel_url
        self._max_videos = max_videos
        self._cookie_file = cookie_file
        self._min_views = min_views
        self._min_likes = min_likes
        self._duration_filter = duration_filter
        self._date_filter = date_filter

    # ── Tiện ích định dạng số đẹp ──

    @staticmethod
    def _fmt_number(n) -> str:
        """Format số thành dạng dễ đọc: 1500 → 1.5K, 1200000 → 1.2M."""
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

    @staticmethod
    def _fmt_duration(duration_sec) -> str:
        """Chuyển giây thành MM:SS hoặc HH:MM:SS."""
        if duration_sec is None:
            return "--:--"
        try:
            secs = int(duration_sec)
        except (ValueError, TypeError):
            return "--:--"
        mins, s = divmod(secs, 60)
        h, m = divmod(mins, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    @staticmethod
    def _fmt_upload_date(upload_date: str) -> str:
        """Chuyển YYYYMMDD → DD/MM/YYYY."""
        if not upload_date or len(upload_date) != 8:
            return "--/--/----"
        try:
            return f"{upload_date[6:8]}/{upload_date[4:6]}/{upload_date[:4]}"
        except Exception:
            return upload_date

    # ── Kiểm tra bộ lọc ──

    def _passes_filters(self, entry: dict) -> bool:
        """Kiểm tra xem entry có đạt tất cả tiêu chí lọc không."""
        from datetime import date, timedelta

        # Lượt xem
        views = entry.get("view_count") or entry.get("views") or 0
        try:
            views = int(views)
        except (ValueError, TypeError):
            views = 0
        if self._min_views > 0 and views < self._min_views:
            return False

        # Lượt thích
        likes = entry.get("like_count") or entry.get("likes") or 0
        try:
            likes = int(likes)
        except (ValueError, TypeError):
            likes = 0
        if self._min_likes > 0 and likes < self._min_likes:
            return False

        # Thời lượng
        if self._duration_filter != self.DURATION_ALL:
            dur = entry.get("duration")
            try:
                dur = int(dur) if dur is not None else None
            except (ValueError, TypeError):
                dur = None
            if self._duration_filter == self.DURATION_SHORT:
                if dur is None or dur >= 60:
                    return False
            elif self._duration_filter == self.DURATION_LONG:
                if dur is None or dur < 60:
                    return False

        # Ngày đăng
        if self._date_filter != self.DATE_ALL:
            upload_date = entry.get("upload_date") or ""
            if len(upload_date) == 8:
                try:
                    vid_date = date(
                        int(upload_date[:4]),
                        int(upload_date[4:6]),
                        int(upload_date[6:8]),
                    )
                    days_map = {self.DATE_3DAYS: 3, self.DATE_7DAYS: 7, self.DATE_30DAYS: 30}
                    cutoff = date.today() - timedelta(days=days_map.get(self._date_filter, 9999))
                    if vid_date < cutoff:
                        return False
                except Exception:
                    pass  # Không lọc nếu không parse được
            else:
                # Không có ngày đăng → loại bỏ khi đang lọc theo ngày
                return False

        return True

    def _process_and_emit(self, collected: list) -> None:
        """Lọc và phát tín hiệu cho các video tìm được."""
        total = len(collected)
        if total == 0:
            self.scan_error.emit("Không tìm thấy video nào trong kênh này.")
            return

        has_filter = (
            self._min_views > 0 or self._min_likes > 0
            or self._duration_filter != self.DURATION_ALL
            or self._date_filter != self.DATE_ALL
        )
        self.scan_progress.emit(
            f"Đang xử lý {total} video" +
            (" và áp dụng bộ lọc..." if has_filter else "...")
        )

        passed = 0
        videos: list[dict] = []
        for idx, entry in enumerate(collected):
            # Áp dụng bộ lọc
            if has_filter and not self._passes_filters(entry):
                self.scan_progress.emit(
                    f"Kiểm tra {idx + 1}/{total} (đã lọc: {passed})..."
                )
                continue

            passed += 1

            # Xây dựng URL & metadata
            video_url = entry.get("url") or entry.get("webpage_url", "")
            video_id = entry.get("id", "")
            title = entry.get("title") or entry.get("fulltitle") or f"Video #{idx + 1}"

            duration_val = entry.get("duration")
            duration_sec = entry.get("duration_sec")
            if duration_sec is None and isinstance(duration_val, (int, float)):
                duration_sec = int(duration_val)

            views = entry.get("views_raw") if entry.get("views_raw") is not None else (entry.get("view_count") or entry.get("views") or 0)
            likes = entry.get("likes_raw") if entry.get("likes_raw") is not None else (entry.get("like_count") or entry.get("likes") or 0)
            upload_date_raw = str(entry.get("upload_date_raw") or entry.get("upload_date") or "")

            # Format chuỗi hiển thị nếu chưa được format
            duration_str = entry.get("duration") if isinstance(entry.get("duration"), str) and ":" in str(entry.get("duration")) else self._fmt_duration(duration_sec)
            views_str = entry.get("views") if isinstance(entry.get("views"), str) and any(c in str(entry.get("views")) for c in ["K", "M", "--"]) else self._fmt_number(views)
            likes_str = entry.get("likes") if isinstance(entry.get("likes"), str) and any(c in str(entry.get("likes")) for c in ["K", "M", "--"]) else self._fmt_number(likes)
            date_str = entry.get("upload_date") if isinstance(entry.get("upload_date"), str) and "/" in str(entry.get("upload_date")) else self._fmt_upload_date(upload_date_raw)

            video_data = {
                "title": title,
                "duration": duration_str,
                "duration_sec": int(duration_sec) if duration_sec else 0,
                "views": views_str,
                "views_raw": int(views) if str(views).isdigit() else 0,
                "likes": likes_str,
                "likes_raw": int(likes) if str(likes).isdigit() else 0,
                "upload_date": date_str,
                "upload_date_raw": upload_date_raw,
                "url": video_url,
                "id": video_id,
            }
            videos.append(video_data)
            self.video_found.emit(video_data)
            self.scan_progress.emit(
                f"Kiểm tra {idx + 1}/{total} — Đạt bộ lọc: {passed} video"
            )

        self.scan_finished.emit(videos)
        filter_note = f" (sau khi lọc từ {total})" if has_filter and passed < total else ""
        self.scan_progress.emit(
            f"✅ Quét hoàn tất! Tìm thấy {len(videos)} video{filter_note}."
        )

    def run(self) -> None:
        """Điểm vào chính — thực hiện quét playlist/channel với bộ lọc."""
        import yt_dlp
        from core.security import get_base_path
        from core.channel_scrapers import (
            is_douyin_channel,
            is_facebook_channel,
            scan_douyin_channel,
            scan_facebook_channel,
        )
        import os
        import shutil

        self.scan_progress.emit(f"Đang quét kênh: {self._channel_url}")

        # ── 1. Giải pháp chuyên biệt cho Kênh Douyin (TikWM API - Không cần Cookie) ──
        if is_douyin_channel(self._channel_url):
            self.scan_progress.emit("Đang dùng cổng API mở quét kênh Douyin (Không cần Cookie)...")
            try:
                raw_videos = scan_douyin_channel(
                    channel_url=self._channel_url,
                    max_videos=self._max_videos,
                    cookie_file=self._cookie_file,
                    progress_cb=self.scan_progress.emit,
                )
                self._process_and_emit(raw_videos)
            except Exception as e:
                self.scan_error.emit(str(e))
            return

        # ── 2. Giải pháp chuyên biệt cho Facebook (mbasic endpoint) ──
        if is_facebook_channel(self._channel_url):
            self.scan_progress.emit("Đang dùng bộ quét Facebook chuyên biệt (mbasic endpoint)...")
            try:
                raw_videos = scan_facebook_channel(
                    channel_url=self._channel_url,
                    max_videos=self._max_videos,
                    cookie_file=self._cookie_file,
                    progress_cb=self.scan_progress.emit,
                )
                self._process_and_emit(raw_videos)
            except Exception as e:
                self.scan_error.emit(str(e))
            return

        # ── 3. Quét thông thường bằng yt-dlp (YouTube, TikTok...) ──
        # Tìm ffmpeg
        app_dir = get_base_path()
        ffmpeg_dir = ""
        for search_dir in [app_dir, os.path.dirname(app_dir)]:
            if os.path.isfile(os.path.join(search_dir, "ffmpeg.exe")) or \
               os.path.isfile(os.path.join(search_dir, "ffmpeg")):
                ffmpeg_dir = search_dir
                break
        if not ffmpeg_dir:
            found = shutil.which("ffmpeg")
            if found:
                ffmpeg_dir = os.path.dirname(found)

        ydl_opts: dict = {
            "extract_flat": "in_playlist",
            "playlistend": self._max_videos,
            "quiet": True,
            "no_warnings": True,
            "no_color": True,
            "ignoreerrors": True,
            "socket_timeout": 30,
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            },
        }

        if ffmpeg_dir:
            ydl_opts["ffmpeg_location"] = ffmpeg_dir
        if self._cookie_file and os.path.isfile(self._cookie_file):
            ydl_opts["cookiefile"] = self._cookie_file

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self.scan_progress.emit("Đang trích xuất thông tin playlist / kênh...")
                info = ydl.extract_info(self._channel_url, download=False)

                if info is None:
                    url_lower = self._channel_url.lower()
                    if ("tiktok.com" in url_lower or "douyin.com" in url_lower or "facebook.com" in url_lower or "fb.com" in url_lower) and not self._cookie_file:
                        self.scan_error.emit(
                            "Kênh bị chặn do chưa có Cookie xác thực. "
                            "TikTok yêu cầu phiên đăng nhập để duyệt danh sách video."
                        )
                    else:
                        self.scan_error.emit(
                            "Không thể truy cập kênh. Hãy kiểm tra lại URL hoặc cung cấp Cookie hợp lệ."
                        )
                    return

                entries = info.get("entries") or []
                collected: list = []
                for i, entry in enumerate(entries):
                    if entry is None:
                        continue
                    collected.append(entry)
                    if i + 1 >= self._max_videos:
                        break

                self._process_and_emit(collected)

        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            err_lower = error_msg.lower()
            if (
                "private" in err_lower
                or "login" in err_lower
                or "sign in" in err_lower
                or "secondary user id" in err_lower
                or "blocked" in err_lower
                or "10204" in err_lower
            ):
                self.scan_error.emit(
                    "Kênh yêu cầu xác thực Cookie. Nền tảng chặn quét tự động nếu không có phiên đăng nhập."
                )
            else:
                self.scan_error.emit(f"Lỗi khi quét kênh: {error_msg[:200]}")
        except Exception as e:
            self.scan_error.emit(f"Lỗi không xác định: {str(e)[:200]}")
