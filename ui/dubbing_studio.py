"""
ui/dubbing_studio.py — Studio Lồng tiếng & Soát kịch bản (DubbingStudioWidget)
Màn hình chuyên biệt cho phép:
  - Xem trước video MP4 với trình phát đa phương tiện chuẩn QtMultimedia (Play, Pause, Tua, Âm lượng).
  - Bảng đối chiếu kịch bản 4 cột: Mốc thời gian | Lời thoại gốc | Bản dịch Tiếng Việt (Cho phép sửa) | Trạng thái.
  - Nhấp đúp vào dòng kịch bản để video tự động tua đúng đến mốc thời gian đó.
  - Xuất file phụ đề .srt hoặc xuất video thành phẩm lồng tiếng theo kịch bản đã chỉnh sửa.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# pyrefly: ignore [missing-import]
from PyQt6.QtCore import QTime, QUrl, Qt, QThread, pyqtSignal
# pyrefly: ignore [missing-import]
from PyQt6.QtGui import QColor, QFont, QIcon
# pyrefly: ignore [missing-import]
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
# pyrefly: ignore [missing-import]
from PyQt6.QtMultimediaWidgets import QVideoWidget
# pyrefly: ignore [missing-import]
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.dubber import DubSegment, OmniDubber, merge_broken_segments, translate_film_context
from ui.styles import COLORS


# ══════════════════════════════════════════════════════════════════════
# TIỆN ÍCH ĐỊNH DẠNG THỜI GIAN
# ══════════════════════════════════════════════════════════════════════

def format_ms_to_clock(ms: int) -> str:
    """Chuyển milliseconds sang chuỗi mm:ss."""
    total_sec = max(0, ms // 1000)
    m = total_sec // 60
    s = total_sec % 60
    return f"{m:02d}:{s:02d}"


def format_seconds_to_timestamp(seconds: float) -> str:
    """Chuyển số giây float sang mm:ss.ms (ví dụ: 01:23.450)."""
    total_sec = max(0, int(seconds))
    millis = int(round((seconds - total_sec) * 1000))
    m = total_sec // 60
    s = total_sec % 60
    return f"{m:02d}:{s:02d}.{millis:03d}"


def format_seconds_to_srt_time(seconds: float) -> str:
    """Chuyển giây sang định dạng SRT chuẩn (00:01:23,450)."""
    total_sec = max(0, int(seconds))
    millis = int(round((seconds - total_sec) * 1000))
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    s = total_sec % 60
    return f"{h:02d}:{m:02d}:{s:02d},{millis:03d}"


# ══════════════════════════════════════════════════════════════════════
# WORKER BÓC TÁCH & DỊCH KỊCH BẢN TRONG NỀN
# ══════════════════════════════════════════════════════════════════════

class StudioTranscribeWorker(QThread):
    """Luồng nền bóc tách thoại (Whisper) & dịch ngữ cảnh (Gemini Flash) cho Studio."""

    log_message = pyqtSignal(str)
    progress_status = pyqtSignal(str)
    finished_segments = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    sig_segments_loaded = pyqtSignal(list)
    sig_sentence_translated = pyqtSignal(int, str)

    def __init__(
        self,
        video_path: str,
        source_lang: str = "zh",
        gemini_api_key: str = "",
        whisper_model: str = "base",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._video_path = video_path
        self._source_lang = source_lang
        self._gemini_api_key = gemini_api_key
        self._whisper_model = whisper_model

    def run(self) -> None:
        try:
            self.progress_status.emit("Đang khởi tạo mô hình nhận diện giọng nói...")
            dubber = OmniDubber(
                whisper_model_size=self._whisper_model,
                gemini_api_key=self._gemini_api_key,
            )

            temp_dir = os.path.join(os.path.dirname(os.path.abspath(self._video_path)), "temp_studio")
            os.makedirs(temp_dir, exist_ok=True)
            base_name = os.path.splitext(os.path.basename(self._video_path))[0]
            temp_wav = os.path.join(temp_dir, f"{base_name}_16k.wav")

            # 1. Trích xuất âm thanh 16kHz
            self.progress_status.emit("Đang bóc tách âm thanh video bằng FFmpeg...")
            import subprocess
            cmd_extract = [
                dubber.ffmpeg,
                "-y",
                "-i", self._video_path,
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                temp_wav,
            ]
            subprocess.run(cmd_extract, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # 2. Nhận diện giọng nói
            self.progress_status.emit("Đang nhận diện lời thoại bằng Whisper...")
            clean_lang = self._source_lang.strip().lower()
            w_lang = "zh" if clean_lang.startswith("zh") else (clean_lang.split("-")[0] if "-" in clean_lang else clean_lang or None)

            whisper_initial_prompt = (
                "这是一部包含对话、剧情、人物互动的中文视频，包含标准标点符号。"
                if w_lang == "zh"
                else None
            )

            raw_segs, _ = dubber.model.transcribe(
                temp_wav,
                language=w_lang,
                vad_filter=True,
                initial_prompt=whisper_initial_prompt,
                condition_on_previous_text=False,
            )
            raw_list = []
            for s in raw_segs:
                raw_list.append(s)
                if len(raw_list) % 5 == 0 or len(raw_list) == 1:
                    self.progress_status.emit(f"Đang nhận diện giọng nói: mốc {int(s.end)}s (đã bóc tách {len(raw_list)} câu)...")

            if not raw_list:
                raise RuntimeError("Không phát hiện được lời thoại trong video.")

            # Gom câu hoàn chỉnh
            merged_segs = merge_broken_segments(raw_list)

            # Phát tín hiệu lên bảng giao diện Studio ngay khi Whisper xong
            seg_dicts = [{'start': s.start, 'end': s.end, 'text': s.text_orig} for s in merged_segs]
            self.sig_segments_loaded.emit(seg_dicts)

            # 3. Dịch ngữ cảnh bằng Gemini Flash API (phát tín hiệu thời gian thực từng câu)
            self.progress_status.emit("Đang dịch kịch bản ngữ cảnh sang Tiếng Việt bằng Gemini Flash API...")
            translate_film_context(
                merged_segs,
                source_lang=self._source_lang,
                gemini_api_key=self._gemini_api_key,
                progress_cb=lambda msg: self.log_message.emit(msg),
                on_sentence_translated_cb=lambda row, txt: self.sig_sentence_translated.emit(row, txt),
            )

            # Dọn dẹp file tạm
            try:
                if os.path.exists(temp_wav):
                    os.remove(temp_wav)
                if os.path.exists(temp_dir):
                    os.rmdir(temp_dir)
            except Exception:
                pass

            self.finished_segments.emit(merged_segs)

        except Exception as e:
            self.error_occurred.emit(str(e))


# ══════════════════════════════════════════════════════════════════════
# GIAO DIỆN CHÍNH: DubbingStudioWidget
# ══════════════════════════════════════════════════════════════════════

class DubbingStudioWidget(QWidget):
    """
    Studio Lồng tiếng & Soát kịch bản (Trang thứ 3 trong QStackedWidget).
    Tích hợp trình phát video MP4 và bảng kịch bản 4 cột tương tác 2 chiều.
    """

    # Các tín hiệu tương tác với MainWindow
    back_requested = pyqtSignal()
    export_dubbing_requested = pyqtSignal(str, list)   # (video_path, list_of_DubSegment)
    export_srt_requested = pyqtSignal(str, list)       # (video_path, list_of_DubSegment)

    # Các cột bảng kịch bản
    COL_TIME = 0
    COL_ORIG = 1
    COL_TRANS = 2
    COL_STATUS = 3

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.current_video_path: str = ""
        self.segments: List[DubSegment] = []
        self._slider_dragging: bool = False
        self._transcribe_worker: Optional[StudioTranscribeWorker] = None

        self._build_ui()
        self._init_player()

    # ─────────────────────────────────────────────────────────────────
    # XÂY DỰNG GIAO DIỆN
    # ─────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        c = COLORS
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        # ── 1. Header Toolbar ──
        header_frame = QFrame()
        header_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border']};
                border-radius: 6px;
                padding: 4px;
            }}
        """)
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(8, 4, 8, 4)
        h_layout.setSpacing(10)

        title_lbl = QLabel("🎬  Studio Lồng tiếng & Soát kịch bản")
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {c['accent_blue']};")
        h_layout.addWidget(title_lbl)

        self._lbl_video_title = QLabel("Chưa mở video nào")
        self._lbl_video_title.setStyleSheet(f"color: {c['text_secondary']}; font-size: 12px;")
        h_layout.addWidget(self._lbl_video_title, 1)

        btn_open = QPushButton("📂  Mở video khác...")
        btn_open.setStyleSheet(self._btn_secondary_style())
        btn_open.clicked.connect(self._on_choose_video)
        h_layout.addWidget(btn_open)

        self._btn_ai_extract: Optional[QPushButton] = None

        layout.addWidget(header_frame)

        # ── 2. Splitter chia 2 nửa: Nửa trên (Video) & Nửa dưới (Kịch bản) ──
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)

        # ── 2.1. Nửa trên: Video Player ──
        video_container = QFrame()
        video_container.setStyleSheet(f"""
            QFrame {{
                background-color: {c['bg_primary']};
                border: 1px solid {c['border']};
                border-radius: 6px;
            }}
        """)
        v_layout = QVBoxLayout(video_container)
        v_layout.setContentsMargins(6, 6, 6, 6)
        v_layout.setSpacing(6)

        # Video viewport
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(200)
        self.video_widget.setStyleSheet(f"background-color: {c['bg_primary']};")
        v_layout.addWidget(self.video_widget, 1)

        # Thanh điều khiển Video
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(4, 0, 4, 0)
        controls_layout.setSpacing(8)

        self._btn_play = QPushButton("▶  Phát")
        self._btn_play.setFixedWidth(85)
        self._btn_play.setStyleSheet(self._btn_secondary_style())
        self._btn_play.clicked.connect(self._toggle_play)
        controls_layout.addWidget(self._btn_play)

        self._btn_stop = QPushButton("⏹")
        self._btn_stop.setFixedWidth(36)
        self._btn_stop.setStyleSheet(self._btn_secondary_style())
        self._btn_stop.clicked.connect(self._stop_video)
        controls_layout.addWidget(self._btn_stop)

        btn_back5 = QPushButton("⏪ -5s")
        btn_back5.setFixedWidth(55)
        btn_back5.setStyleSheet(self._btn_secondary_style())
        btn_back5.clicked.connect(lambda: self._seek_relative(-5000))
        controls_layout.addWidget(btn_back5)

        btn_fwd5 = QPushButton("+5s ⏩")
        btn_fwd5.setFixedWidth(55)
        btn_fwd5.setStyleSheet(self._btn_secondary_style())
        btn_fwd5.clicked.connect(lambda: self._seek_relative(5000))
        controls_layout.addWidget(btn_fwd5)

        # Thanh tua thời gian (Slider)
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 0)
        self._slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 6px;
                background: {c['bg_input_border']};
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {c['accent_blue']};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {c['text_primary']};
                border: 2px solid {c['accent_blue']};
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }}
            QSlider::handle:horizontal:hover {{
                background: #ffffff;
            }}
        """)
        self._slider.sliderPressed.connect(self._on_slider_pressed)
        self._slider.sliderReleased.connect(self._on_slider_released)
        self._slider.sliderMoved.connect(self._on_slider_moved)
        controls_layout.addWidget(self._slider, 1)

        # Nhãn thời gian thực
        self._lbl_time = QLabel("00:00 / 00:00")
        self._lbl_time.setFixedWidth(90)
        self._lbl_time.setStyleSheet(f"color: {c['text_secondary']}; font-size: 11px; font-weight: bold;")
        controls_layout.addWidget(self._lbl_time)

        # Âm lượng
        vol_icon = QLabel("🔊")
        vol_icon.setStyleSheet("font-size: 12px;")
        controls_layout.addWidget(vol_icon)

        self._vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(80)
        self._vol_slider.setFixedWidth(70)
        self._vol_slider.valueChanged.connect(self._on_volume_changed)
        controls_layout.addWidget(self._vol_slider)

        v_layout.addLayout(controls_layout)
        splitter.addWidget(video_container)

        # ── 2.2. Nửa dưới: Bảng kịch bản đối chiếu ──
        table_container = QFrame()
        table_container.setStyleSheet(f"""
            QFrame {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border']};
                border-radius: 6px;
            }}
        """)
        t_layout = QVBoxLayout(table_container)
        t_layout.setContentsMargins(6, 6, 6, 6)
        t_layout.setSpacing(6)

        # Thanh hướng dẫn nhỏ trên bảng
        table_hint = QLabel("💡 Mẹo: Nhấn nút '🎙️ BẮT ĐẦU LỒNG TIẾNG' ở góc dưới bên phải để AI tự động bóc tách, dịch thoại lên bảng và xuất video lồng tiếng cùng lúc. Nhấp đúp vào dòng để tua video.")
        table_hint.setStyleSheet(f"color: {c['accent_cyan']}; font-size: 11px; padding: 2px 4px;")
        t_layout.addWidget(table_hint)

        # Bảng kịch bản 4 cột
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "Mốc thời gian",
            "Lời thoại gốc",
            "Bản dịch Tiếng Việt (Cho phép sửa)",
            "Trạng thái",
        ])
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {c['bg_input']};
                color: {c['text_primary']};
                gridline-color: {c['border']};
                border: none;
                font-size: 12px;
                selection-background-color: #1e3a5f;
                selection-color: #ffffff;
            }}
            QHeaderView::section {{
                background-color: {c['bg_secondary']};
                color: {c['text_secondary']};
                font-weight: bold;
                border: none;
                border-bottom: 2px solid {c['border']};
                border-right: 1px solid {c['border']};
                padding: 6px;
                font-size: 12px;
            }}
            QTableCornerButton::section {{
                background-color: {c['bg_secondary']};
                border: none;
            }}
        """)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.COL_TIME, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_ORIG, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_TRANS, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(self.COL_ORIG, 160)

        # Nhấp đúp dòng để tua video
        self.table.cellDoubleClicked.connect(self._on_table_double_clicked)
        t_layout.addWidget(self.table, 1)

        splitter.addWidget(table_container)
        splitter.setSizes([260, 320])
        layout.addWidget(splitter, 1)

        # Thanh tiến trình bóc tách nếu đang chạy AI
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setVisible(False)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {c['border']};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {c['accent_purple']};
                border-radius: 3px;
            }}
        """)
        layout.addWidget(self._progress_bar)

        self._lbl_status_msg = QLabel("")
        self._lbl_status_msg.setStyleSheet(f"color: {c['accent_orange']}; font-size: 11px;")
        self._lbl_status_msg.setVisible(False)
        layout.addWidget(self._lbl_status_msg)

        # ── 3. Thanh chân trang (Footer Bar) ──
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 4, 0, 0)
        footer_layout.setSpacing(10)

        btn_back = QPushButton("⬅  Quay lại màn hình tải")
        btn_back.setStyleSheet(self._btn_secondary_style())
        btn_back.clicked.connect(self._on_back_clicked)
        footer_layout.addWidget(btn_back)

        footer_layout.addStretch(1)

        btn_export_srt = QPushButton("📝  Xuất file phụ đề .srt")
        btn_export_srt.setStyleSheet(self._btn_accent_style(c['accent_blue']))
        btn_export_srt.clicked.connect(self._on_export_srt)
        footer_layout.addWidget(btn_export_srt)

        btn_export_dub = QPushButton("🎬  Xuất video lồng tiếng")
        btn_export_dub.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['btn_green_bg']};
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid {c['btn_green_border']};
                border-radius: 6px;
                padding: 8px 18px;
            }}
            QPushButton:hover {{
                background-color: {c['btn_green_hover']};
            }}
        """)
        btn_export_dub.clicked.connect(self._on_export_dubbing)
        footer_layout.addWidget(btn_export_dub)

        layout.addLayout(footer_layout)

    # ─────────────────────────────────────────────────────────────────
    # KHỞI TẠO PLAYER
    # ─────────────────────────────────────────────────────────────────

    def _init_player(self) -> None:
        self.player = QMediaPlayer(self)
        self.media_player = self.player  # Alias tham chiếu trực tiếp theo chuẩn yêu cầu
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)

        self.audio_output.setVolume(0.8)

        self.player.positionChanged.connect(self._on_player_position_changed)
        self.player.durationChanged.connect(self._on_player_duration_changed)
        self.player.playbackStateChanged.connect(self._on_player_state_changed)
        self.player.mediaStatusChanged.connect(self._on_player_media_status_changed)

    def _on_player_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._btn_play.setText("▶  Phát")

    def _sync_table_with_video(self, pos_ms: int) -> None:
        sec = pos_ms / 1000.0
        for row in range(self.table.rowCount()):
            item = self.table.item(row, self.COL_TIME)
            if not item:
                continue
            start = item.data(Qt.ItemDataRole.UserRole)
            end = item.data(Qt.ItemDataRole.UserRole + 1)
            if start is not None and end is not None and start <= sec <= end:
                if self.table.currentRow() != row:
                    self.table.blockSignals(True)
                    self.table.selectRow(row)
                    self.table.blockSignals(False)
                break

    # ─────────────────────────────────────────────────────────────────
    # STYLES NÚT BẤM TIỆN ÍCH
    # ─────────────────────────────────────────────────────────────────

    def _btn_secondary_style(self) -> str:
        c = COLORS
        return f"""
            QPushButton {{
                background-color: {c['btn_secondary_bg']};
                color: {c['text_primary']};
                border: 1px solid {c['border']};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {c['btn_secondary_hover']};
                border-color: {c['border_focus']};
            }}
        """

    def _btn_accent_style(self, bg_color: str) -> str:
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: #ffffff;
                font-weight: 600;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """

    # ─────────────────────────────────────────────────────────────────
    # ĐIỀU KHIỂN VIDEO
    # ─────────────────────────────────────────────────────────────────

    def load_video_to_studio(self, video_path: str) -> None:
        """Nạp video lên khung phát QVideoWidget và lưu đường dẫn."""
        if not video_path or not os.path.isfile(video_path):
            return

        is_new = (self.current_video_path != video_path)
        self.current_video_path = video_path
        self._lbl_video_title.setText(f"📁 {os.path.basename(video_path)}")
        from PyQt6.QtCore import QUrl
        # Nạp vào QMediaPlayer để phát trên QVideoWidget
        self.media_player.setSource(QUrl.fromLocalFile(video_path))
        self.media_player.play()
        self.media_player.pause()
        self._btn_play.setText("▶  Phát")

        if is_new:
            self.table.setRowCount(0)
            self._lbl_status_msg.setText("")
            self._lbl_status_msg.setVisible(False)
            self._progress_bar.setVisible(False)

    def load_video(self, video_path: str) -> None:
        """Alias tương thích ngược."""
        self.load_video_to_studio(video_path)

    def _on_choose_video(self) -> None:
        f, _ = QFileDialog.getOpenFileName(
            self, "Chọn video MP4", "",
            "Video MP4 (*.mp4);;Tất cả file (*.*)"
        )
        if f:
            self.load_video_to_studio(f)

    def _toggle_play(self) -> None:
        if not self.current_video_path:
            self._on_choose_video()
            return

        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _stop_video(self) -> None:
        self.player.stop()
        self.player.setPosition(0)
        self._btn_play.setText("▶  Phát")

    def _seek_relative(self, delta_ms: int) -> None:
        new_pos = max(0, min(self.player.duration(), self.player.position() + delta_ms))
        self.player.setPosition(new_pos)

    def _on_player_position_changed(self, pos_ms: int) -> None:
        if not self._slider_dragging:
            self._slider.setValue(pos_ms)
        self._lbl_time.setText(f"{format_ms_to_clock(pos_ms)} / {format_ms_to_clock(self.player.duration())}")
        self._sync_table_with_video(pos_ms)

    def _on_player_duration_changed(self, dur_ms: int) -> None:
        self._slider.setRange(0, dur_ms)
        self._lbl_time.setText(f"{format_ms_to_clock(self.player.position())} / {format_ms_to_clock(dur_ms)}")

    def _on_player_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._btn_play.setText("⏸  Tạm dừng")
        else:
            self._btn_play.setText("▶  Phát")

    def _on_slider_pressed(self) -> None:
        self._slider_dragging = True

    def _on_slider_released(self) -> None:
        self._slider_dragging = False
        self.player.setPosition(self._slider.value())

    def _on_slider_moved(self, pos: int) -> None:
        self.player.setPosition(pos)

    def _on_volume_changed(self, val: int) -> None:
        self.audio_output.setVolume(val / 100.0)

    # ─────────────────────────────────────────────────────────────────
    # BẢNG KỊCH BẢN & TƯƠNG TÁC
    # ─────────────────────────────────────────────────────────────────

    def update_progress_status(self, msg: str) -> None:
        """Cập nhật thông báo tiến trình thời gian thực dưới bảng kịch bản."""
        if not self._progress_bar.isVisible():
            self._progress_bar.setVisible(True)
        if not self._lbl_status_msg.isVisible():
            self._lbl_status_msg.setVisible(True)
        self._lbl_status_msg.setText(msg)

    def on_segment_discovered(self, seg: dict) -> None:
        """Thêm ngay từng câu bóc tách thô khi Whisper nhận diện để bảng không bao giờ bị trống."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        start = float(seg.get('start', 0.0))
        end = float(seg.get('end', 0.0))
        text = str(seg.get('text', '')).strip()

        start_str = f"{int(start//60):02d}:{start%60:04.1f}"
        end_str = f"{int(end//60):02d}:{end%60:04.1f}"
        time_item = QTableWidgetItem(f"{start_str} -> {end_str}")
        time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        time_item.setData(Qt.ItemDataRole.UserRole, start)
        time_item.setData(Qt.ItemDataRole.UserRole + 1, end)
        time_item.setFlags(time_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, 0, time_item)

        orig_item = QTableWidgetItem(text)
        orig_item.setFlags(orig_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, 1, orig_item)

        trans_item = QTableWidgetItem("⏳ Đang nhận diện...")
        trans_item.setFlags(trans_item.flags() | Qt.ItemFlag.ItemIsEditable)
        trans_item.setForeground(QColor(COLORS["accent_blue"]))
        self.table.setItem(row, 2, trans_item)

        status_item = QTableWidgetItem("🎙 Nhận diện")
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, 3, status_item)

        self.table.scrollToItem(orig_item)

    def on_segments_loaded(self, segments: list) -> None:
        """Bước 1: Whisper bóc tách xong -> Xóa bảng cũ và đổ toàn bộ danh sách vào bảng."""
        self.table.setRowCount(0)
        self.table.setRowCount(len(segments))
        if self._lbl_status_msg:
            self._lbl_status_msg.setText("✅ Whisper đã bóc tách xong. Đang dịch kịch bản bằng Gemini Flash...")

        for row, seg in enumerate(segments):
            if isinstance(seg, dict):
                start = float(seg.get('start', 0.0))
                end = float(seg.get('end', 0.0))
                text = str(seg.get('text', ''))
            else:
                start = float(getattr(seg, 'start', 0.0))
                end = float(getattr(seg, 'end', 0.0))
                text = str(getattr(seg, 'text_orig', getattr(seg, 'text', '')))

            # Cột 1: Mốc thời gian (00:01.5 -> 00:04.2)
            start_str = f"{int(start//60):02d}:{start%60:04.1f}"
            end_str = f"{int(end//60):02d}:{end%60:04.1f}"
            time_item = QTableWidgetItem(f"{start_str} -> {end_str}")
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            time_item.setData(Qt.ItemDataRole.UserRole, start)
            time_item.setData(Qt.ItemDataRole.UserRole + 1, end)
            time_item.setFlags(time_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, time_item)

            # Cột 2: Lời thoại gốc
            orig_item = QTableWidgetItem(text)
            orig_item.setFlags(orig_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, orig_item)

            # Cột 3: Bản dịch tạm thời
            trans_item = QTableWidgetItem("⏳ Đang chờ dịch...")
            trans_item.setFlags(trans_item.flags() | Qt.ItemFlag.ItemIsEditable)
            trans_item.setForeground(QColor(COLORS["accent_blue"]))
            self.table.setItem(row, 2, trans_item)

            # Cột 4: Trạng thái
            status_item = QTableWidgetItem("⏳ Chờ xử lý")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 3, status_item)

    def on_sentence_translated(self, row: int, vn_text: str) -> None:
        """Bước 2: Dịch xong câu nào -> Cập nhật ngay câu tiếng Việt vào Cột 3."""
        if row < self.table.rowCount():
            trans_item = QTableWidgetItem(vn_text)
            trans_item.setFlags(trans_item.flags() | Qt.ItemFlag.ItemIsEditable)
            trans_item.setForeground(QColor(COLORS["accent_blue"]))
            self.table.setItem(row, 2, trans_item)

            status_item = QTableWidgetItem("✓ Đã dịch")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 3, status_item)

            # Tự động cuộn đến dòng đang xử lý
            target_item = self.table.item(row, 2)
            if target_item:
                self.table.scrollToItem(target_item)

    def on_sentence_completed(self, row: int, status_text: str = "") -> None:
        """Bước 3: Lồng tiếng xong câu nào -> Cập nhật trạng thái Cột 4."""
        if row < self.table.rowCount():
            display_text = status_text if status_text else "🎙️ Đã lồng tiếng"
            status_item = QTableWidgetItem(display_text)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 3, status_item)

    def on_all_finished(self, output_video_path: str = "") -> None:
        """Bước 4: Toàn bộ video hoàn tất."""
        if self._progress_bar:
            self._progress_bar.setVisible(False)
        if self._lbl_status_msg:
            self._lbl_status_msg.setText("🎉 Đã hoàn tất lồng tiếng video thành công!")

    def set_segments(self, segments: List[DubSegment]) -> None:
        """Nạp danh sách DubSegment vào bảng 4 cột."""
        self.segments = segments
        self.on_segments_loaded(segments)
        for row, seg in enumerate(segments):
            if getattr(seg, 'text_trans', None):
                self.on_sentence_translated(row, seg.text_trans)

    def get_segments(self) -> List[DubSegment]:
        """Thu thập danh sách câu thoại (kèm các sửa đổi của người dùng) từ bảng."""
        updated: List[DubSegment] = []
        for row in range(self.table.rowCount()):
            item_time = self.table.item(row, self.COL_TIME)
            item_orig = self.table.item(row, self.COL_ORIG)
            item_trans = self.table.item(row, self.COL_TRANS)

            if not item_time or not item_orig:
                continue

            start = float(item_time.data(Qt.ItemDataRole.UserRole) or 0.0)
            end = float(item_time.data(Qt.ItemDataRole.UserRole + 1) or (start + 2.0))
            text_orig = item_orig.text().strip()
            text_trans = item_trans.text().strip() if item_trans else ""
            if text_trans.startswith("⏳"):
                text_trans = ""

            seg = DubSegment(
                start=start,
                end=end,
                text_orig=text_orig,
                text_trans=text_trans,
            )
            updated.append(seg)
        return updated

    def _on_table_double_clicked(self, row: int, column: int) -> None:
        """Tính năng: Nhấp đúp vào dòng nào thì video tự động tua đúng đến giây đó."""
        item_time = self.table.item(row, self.COL_TIME)
        if not item_time:
            return

        start_sec = item_time.data(Qt.ItemDataRole.UserRole)
        if start_sec is not None:
            pos_ms = int(float(start_sec) * 1000)
            self.player.setPosition(pos_ms)
            self.player.play()
            self._btn_play.setText("⏸  Tạm dừng")

    # ─────────────────────────────────────────────────────────────────
    # BÓC TÁCH & DỊCH AI
    # ─────────────────────────────────────────────────────────────────

    def _on_extract_script_clicked(self) -> None:
        if not self.current_video_path or not os.path.isfile(self.current_video_path):
            QMessageBox.warning(self, "Chưa có video", "Vui lòng mở một video MP4 trước khi bóc tách thoại.")
            self._on_choose_video()
            return

        # Lấy API Key từ MainWindow (nếu có)
        main_win = self.window()
        api_key = getattr(main_win, "gemini_api_key", "")
        dub_lang = getattr(main_win, "dub_lang", "zh-CN")
        model = getattr(main_win, "whisper_model", "base")

        if self._btn_ai_extract:
            self._btn_ai_extract.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._lbl_status_msg.setVisible(True)
        self._lbl_status_msg.setText("Đang khởi động tiến trình phân tích âm thanh & dịch thoại...")

        self._transcribe_worker = StudioTranscribeWorker(
            video_path=self.current_video_path,
            source_lang=dub_lang,
            gemini_api_key=api_key,
            whisper_model=model,
            parent=self,
        )
        self._transcribe_worker.progress_status.connect(self._lbl_status_msg.setText)
        self._transcribe_worker.sig_segments_loaded.connect(self.on_segments_loaded)
        self._transcribe_worker.sig_sentence_translated.connect(self.on_sentence_translated)
        self._transcribe_worker.finished_segments.connect(self._on_transcribe_finished)
        self._transcribe_worker.error_occurred.connect(self._on_transcribe_error)
        self._transcribe_worker.start()

    def _on_transcribe_finished(self, segments: List[DubSegment]) -> None:
        if self._btn_ai_extract:
            self._btn_ai_extract.setEnabled(True)
        self._progress_bar.setVisible(False)
        self._lbl_status_msg.setVisible(False)
        self.set_segments(segments)
        QMessageBox.information(
            self, "Hoàn tất bóc tách",
            f"🎉 Đã bóc tách và dịch thành công {len(segments)} câu thoại!\n\n"
            "Bạn có thể nhấp đúp vào từng dòng để nghe lại, hoặc sửa trực tiếp câu dịch ở cột 3."
        )

    def _on_transcribe_error(self, err: str) -> None:
        if self._btn_ai_extract:
            self._btn_ai_extract.setEnabled(True)
        self._progress_bar.setVisible(False)
        self._lbl_status_msg.setVisible(False)
        QMessageBox.warning(self, "Lỗi bóc tách kịch bản", f"Không thể phân tích kịch bản:\n{err}")

    # ─────────────────────────────────────────────────────────────────
    # XUẤT PHỤ ĐỀ .SRT & XUẤT VIDEO LỒNG TIẾNG
    # ─────────────────────────────────────────────────────────────────

    def _on_export_srt(self) -> None:
        """Xuất danh sách câu dịch ra file phụ đề SRT."""
        segments = self.get_segments()
        if not segments:
            QMessageBox.warning(self, "Chưa có kịch bản", "Bảng kịch bản đang trống. Hãy phân tích kịch bản trước khi xuất.")
            return

        base_name = Path(self.current_video_path).stem if self.current_video_path else "subtitles"
        default_path = str(Path.home() / "Videos" / f"{base_name}_vi.srt")

        f, _ = QFileDialog.getSaveFileName(
            self, "Xuất file phụ đề .srt", default_path,
            "SubRip Subtitle (*.srt);;Tất cả file (*.*)"
        )
        if not f:
            return

        try:
            with open(f, "w", encoding="utf-8") as out:
                for idx, seg in enumerate(segments, start=1):
                    t_start = format_seconds_to_srt_time(seg.start)
                    t_end = format_seconds_to_srt_time(seg.end)
                    text = seg.text_trans.strip() if seg.text_trans else seg.text_orig.strip()
                    out.write(f"{idx}\n{t_start} --> {t_end}\n{text}\n\n")

            QMessageBox.information(self, "Thành công", f"✅ Đã xuất file phụ đề SRT thành công:\n{f}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi xuất file", f"Không thể lưu file SRT:\n{e}")

    def _on_export_dubbing(self) -> None:
        """Gửi yêu cầu xuất video lồng tiếng theo kịch bản đã duyệt."""
        if not self.current_video_path or not os.path.isfile(self.current_video_path):
            QMessageBox.warning(self, "Chưa chọn video", "Vui lòng chọn video MP4 cần lồng tiếng.")
            return

        segments = self.get_segments()
        self.export_dubbing_requested.emit(self.current_video_path, segments)

    def start_dubbing_process(self) -> None:
        """Bắt đầu bóc tách, dịch và lồng tiếng video trong Studio."""
        if not self.current_video_path or not os.path.isfile(self.current_video_path):
            reply = QMessageBox.question(
                self,
                "Chưa chọn video",
                "Chưa có video nào được nạp vào Studio.\nBạn có muốn mở video MP4 để lồng tiếng ngay không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._on_choose_video()
            return

        # Gọi xuất video lồng tiếng theo kịch bản đã duyệt (hoặc tự động bóc tách + dịch nếu chưa có)
        self._on_export_dubbing()

    def stop_dubbing_process(self) -> None:
        """Dừng tác vụ bóc tách hoặc lồng tiếng trong Studio."""
        if self._transcribe_worker and self._transcribe_worker.isRunning():
            try:
                self._transcribe_worker.terminate()
                self._transcribe_worker.wait(1000)
            except Exception:
                pass
            if self._btn_ai_extract:
                self._btn_ai_extract.setEnabled(True)
            self._progress_bar.setVisible(False)
            self._lbl_status_msg.setVisible(False)

        main_win = self.window()
        if hasattr(main_win, "stop_dubbing"):
            main_win.stop_dubbing()

    def _on_back_clicked(self) -> None:
        self.back_requested.emit()

