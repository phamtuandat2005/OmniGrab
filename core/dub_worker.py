"""
core/dub_worker.py - QThread xử lý lồng tiếng AI trong nền bằng OmniDubber.

Không đơ UI. Phát log thời gian thực ra MainWindow.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Optional

# pyrefly: ignore [missing-import]
from PyQt6.QtCore import QThread, pyqtSignal

from core.dubber import DubConfig, OmniDubber


class DubWorker(QThread):
    """
    Luồng nền thực hiện lồng tiếng AI Tiếng Việt.

    Signals:
        sig_segments_loaded(list)        : Phát khi Whisper bóc tách xong toàn bộ danh sách câu thoại gốc.
        sig_sentence_translated(int, str): Phát khi dịch xong từng câu để điền vào Cột 3.
        sig_sentence_completed(int, str) : Phát khi hoàn thành lồng tiếng từng câu để cập nhật Cột 4.
        sig_all_finished(str)            : Phát khi toàn bộ video hoàn tất.

        log_message(str)                 : Nhật ký tiến trình.
        dub_progress(int, int)           : Câu hiện tại / tổng số câu.
        dub_finished(str)                : Đường dẫn file video thành phẩm.
        dub_error(str)                   : Thông báo lỗi nếu thất bại.
    """

    # 0. Phát khi Whisper phát hiện từng câu thoại thô theo thời gian thực (để bảng cập nhật ngay)
    sig_segment_discovered = pyqtSignal(dict)  # {'start': float, 'end': float, 'text': str}

    # 1. Phát khi Whisper bóc tách xong toàn bộ danh sách câu thoại gốc
    sig_segments_loaded = pyqtSignal(list)   # list of dict: [{'start': ..., 'end': ..., 'text': ...}]

    # 2. Phát khi dịch xong từng câu để điền vào Cột 3
    sig_sentence_translated = pyqtSignal(int, str)  # (row_index, vietnamese_text)

    # 3. Phát khi hoàn thành lồng tiếng từng câu để cập nhật Cột 4
    sig_sentence_completed = pyqtSignal(int, str)   # (row_index, status_text)

    # 4. Phát khi toàn bộ video hoàn tất
    sig_all_finished = pyqtSignal(str)              # output_video_path

    # Tín hiệu tương thích ngược
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
        super().__init__(parent)
        self._input_video = input_video
        self._config = config

    def run(self) -> None:
        """Điểm vào chính của luồng lồng tiếng."""
        try:
            base, ext = os.path.splitext(self._input_video)
            output_path = f"{base}_dubbed{ext}"

            dubber = OmniDubber(
                whisper_model_size=self._config.whisper_model or "base",
                gemini_api_key=getattr(self._config, "gemini_api_key", ""),
            )
            success = dubber.process_dubbing(
                input_video=self._input_video,
                output_video=output_path,
                source_lang=self._config.source_lang or "zh",
                voice=self._config.voice or "vi",
                gemini_api_key=getattr(self._config, "gemini_api_key", ""),
                bg_volume=getattr(self._config, "bg_volume", 0.12),
                custom_segments=getattr(self._config, "custom_segments", None),
                progress_callback=self._on_log,
                on_segment_discovered_cb=self._on_segment_discovered,
                on_segments_loaded_cb=self._on_segments_loaded,
                on_sentence_translated_cb=self._on_sentence_translated,
                on_sentence_completed_cb=self._on_sentence_completed,
            )
            if success and os.path.exists(output_path):
                self.sig_all_finished.emit(output_path)
                self.dub_finished.emit(output_path)
            else:
                raise RuntimeError("Tiến trình lồng tiếng không tạo được file thành phẩm.")
        except Exception as exc:
            self.dub_error.emit(str(exc))

    def _on_log(self, message: str) -> None:
        self.log_message.emit(message)

    def _on_segment_discovered(self, seg_dict: dict) -> None:
        self.sig_segment_discovered.emit(seg_dict)

    def _on_segments_loaded(self, segments: list) -> None:
        self.sig_segments_loaded.emit(segments)

    def _on_sentence_translated(self, row: int, vn_text: str) -> None:
        self.sig_sentence_translated.emit(row, vn_text)

    def _on_sentence_completed(self, row: int, status_text: str) -> None:
        self.sig_sentence_completed.emit(row, status_text)


# Alias tương thích tên gọi
DubbingWorker = DubWorker
