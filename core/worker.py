"""
core/worker.py - QThread xử lý tải đa luồng nền.

Đảm bảo:
- UI không bị đơ khi đang tải.
- Phát tín hiệu pyqtSignal về UI với thông điệp Tiếng Việt.
- Hỗ trợ dừng tải an toàn (Graceful Stop).
- Tải đồng thời nhiều video bằng ThreadPoolExecutor.
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
                            self.item_finished.emit(url, True, "")
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
