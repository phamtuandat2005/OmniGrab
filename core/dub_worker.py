"""
core/dub_worker.py - QThread xử lý lồng tiếng AI trong nền.

Không đơ UI. Phát log thời gian thực ra MainWindow.
"""

from __future__ import annotations

from typing import Any, Optional

# pyrefly: ignore [missing-import]
from PyQt6.QtCore import QThread, pyqtSignal

from core.dubber import DubConfig, VideoDubber


class DubWorker(QThread):
    """
    Luồng nền thực hiện lồng tiếng AI Tiếng Việt.

    Signals:
        log_message(str)         : Nhật ký tiến trình.
        dub_progress(int, int)   : Câu hiện tại / tổng số câu.
        dub_finished(str)        : Đường dẫn file video thành phẩm.
        dub_error(str)           : Thông báo lỗi nếu thất bại.
    """

    log_message  = pyqtSignal(str)
    dub_progress = pyqtSignal(int, int)   # (current_seg, total_segs)
    dub_finished = pyqtSignal(str)        # output_video_path
    dub_error    = pyqtSignal(str)        # error message

    def __init__(
        self,
        input_video: str,
        config: DubConfig,
        parent: Optional[Any] = None,
    ) -> None:
        """
        Args:
            input_video : Đường dẫn tuyệt đối tới file MP4 đầu vào.
            config      : Cấu hình lồng tiếng (DubConfig).
            parent      : QObject cha.
        """
        super().__init__(parent)
        self._input_video = input_video
        self._config = config

    def run(self) -> None:
        """Điểm vào chính của luồng lồng tiếng."""
        # Gắn callback log + progress vào config
        self._config.log_callback = self._on_log
        self._config.progress_callback = self._on_progress

        try:
            dubber = VideoDubber(self._config)
            output_path = dubber.process_video(self._input_video)
            self.dub_finished.emit(output_path)
        except Exception as exc:
            self.dub_error.emit(str(exc))

    # ── Callbacks nội bộ ──

    def _on_log(self, message: str) -> None:
        from datetime import datetime
        ts = datetime.now().strftime("[%H:%M:%S]")
        self.log_message.emit(f"{ts} {message}")

    def _on_progress(self, current: int, total: int) -> None:
        self.dub_progress.emit(current, total)
