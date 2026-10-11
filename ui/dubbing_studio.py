"""
ui/dubbing_studio.py — Studio Lồng tiếng & Soát kịch bản (DubbingStudioWidget)
Màn hình chuyên biệt cho phép:
  - Xem trước video MP4 với trình phát đa phương tiện chuẩn QtMultimedia (Play, Pause, Tua, Âm lượng).
  - Bảng đối chiếu kịch bản 4 cột: Mốc thời gian | Lời thoại gốc | Bản dịch Tiếng Việt (Cho phép sửa) | Trạng thái.
  - Nhấp đúp vào dòng kịch bản để video tự động tua đúng đến mốc thời gian đó.
  - Xuất file phụ đề .srt hoặc xuất video thành phẩm lồng tiếng theo kịch bản đã chỉnh sửa.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# pyrefly: ignore [missing-import]
from PyQt6.QtCore import QObject, QTime, QUrl, Qt, QThread, pyqtSignal
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
    QLineEdit,
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


def is_same_or_related_video(path1: str, path2: str) -> bool:
    """Kiểm tra xem 2 video có phải là cùng một video hoặc bản gốc/bản lồng tiếng của nhau."""
    if not path1 or not path2:
        return False
    try:
        p1 = os.path.normpath(os.path.abspath(path1)).lower()
        p2 = os.path.normpath(os.path.abspath(path2)).lower()
        if p1 == p2:
            return True

        def clean_stem(p: str) -> str:
            stem = os.path.splitext(os.path.basename(p))[0]
            for suffix in ['_dubbed', '_vi', '_subbed', '_translated', '_raw', '_audio']:
                if stem.endswith(suffix):
                    stem = stem[:-len(suffix)]
            return stem

        dir1 = os.path.dirname(p1)
        dir2 = os.path.dirname(p2)
        if dir1 == dir2 and clean_stem(p1) == clean_stem(p2):
            return True
    except Exception:
        pass
    return False


def parse_srt_time_to_seconds(time_str: str) -> float:
    """Chuyển chuỗi thời gian SRT '00:01:23,450' hoặc '00:01:23.450' sang giây float."""
    time_str = time_str.strip().replace(',', '.')
    parts = time_str.split(':')
    if len(parts) == 3:
        h = float(parts[0])
        m = float(parts[1])
        s = float(parts[2])
        return h * 3600.0 + m * 60.0 + s
    elif len(parts) == 2:
        m = float(parts[0])
        s = float(parts[1])
        return m * 60.0 + s
    try:
        return float(time_str)
    except Exception:
        return 0.0


def parse_srt_file(file_path: str) -> List[DubSegment]:
    """Đọc file .srt và chuyển thành danh sách DubSegment."""
    if not file_path or not os.path.isfile(file_path):
        return []
    segments: List[DubSegment] = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        blocks = re.split(r'\n\s*\n', content.strip())
        for block in blocks:
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if len(lines) < 2:
                continue
            time_idx = -1
            for i, line in enumerate(lines):
                if '-->' in line:
                    time_idx = i
                    break
            if time_idx == -1:
                continue
            parts = lines[time_idx].split('-->')
            if len(parts) != 2:
                continue
            start_sec = parse_srt_time_to_seconds(parts[0])
            end_sec = parse_srt_time_to_seconds(parts[1])
            text = "\n".join(lines[time_idx + 1:]).strip()
            if not text:
                continue
            segments.append(DubSegment(
                start=start_sec,
                end=end_sec,
                text_orig=text,
                text_trans=text,
            ))
    except Exception:
        pass
    return segments


def load_segments_from_json(file_path: str) -> List[DubSegment]:
    """Đọc file .omnigrab.json và chuyển thành danh sách DubSegment."""
    if not file_path or not os.path.isfile(file_path):
        return []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        segments: List[DubSegment] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            start = float(item.get('start', 0.0))
            end = float(item.get('end', 0.0))
            text_orig = str(item.get('text_orig', '')).strip()
            text_trans = str(item.get('text_trans', '')).strip()
            segments.append(DubSegment(
                start=start,
                end=end,
                text_orig=text_orig,
                text_trans=text_trans,
            ))
        return segments
    except Exception:
        pass
    return []


def save_segments_to_files(video_path: str, segments: List[DubSegment]) -> None:
    """Tự động lưu kịch bản ra file .omnigrab.json và .srt cùng thư mục với video."""
    if not video_path or not segments:
        return
    try:
        base_dir = os.path.dirname(os.path.abspath(video_path))
        file_stem = os.path.splitext(os.path.basename(video_path))[0]

        # 1. Lưu JSON đầy đủ cả gốc lẫn dịch
        json_path = os.path.join(base_dir, f"{file_stem}.omnigrab.json")
        data = []
        for seg in segments:
            data.append({
                'start': round(float(seg.start), 3),
                'end': round(float(seg.end), 3),
                'text_orig': getattr(seg, 'text_orig', '') or '',
                'text_trans': getattr(seg, 'text_trans', '') or '',
                'status': '🎙️ Đã lồng tiếng',
            })
        with open(json_path, 'w', encoding='utf-8') as jf:
            json.dump(data, jf, ensure_ascii=False, indent=2)

        # 2. Lưu SRT phụ đề
        srt_path = os.path.join(base_dir, f"{file_stem}.srt")
        with open(srt_path, 'w', encoding='utf-8') as sf:
            for idx, seg in enumerate(segments, start=1):
                t_start = format_seconds_to_srt_time(seg.start)
                t_end = format_seconds_to_srt_time(seg.end)
                text = seg.text_trans.strip() if getattr(seg, 'text_trans', None) else seg.text_orig.strip()
                sf.write(f"{idx}\n{t_start} --> {t_end}\n{text}\n\n")
    except Exception:
        pass


def find_subtitles_for_video(video_path: str) -> Optional[str]:
    """Tìm file .omnigrab.json hoặc .srt đã có của video này."""
    if not video_path:
        return None
    try:
        video_path = os.path.abspath(video_path)
        base_dir = os.path.dirname(video_path)
        file_stem = os.path.splitext(os.path.basename(video_path))[0]

        clean_stem = file_stem
        for suffix in ['_dubbed', '_vi', '_subbed', '_translated', '_raw', '_audio']:
            if clean_stem.lower().endswith(suffix):
                clean_stem = clean_stem[:-len(suffix)]
                break

        candidates = [
            os.path.join(base_dir, f"{file_stem}.omnigrab.json"),
            os.path.join(base_dir, f"{clean_stem}.omnigrab.json"),
            os.path.join(base_dir, f"{clean_stem}_dubbed.omnigrab.json"),
            os.path.join(base_dir, f"{file_stem}.srt"),
            os.path.join(base_dir, f"{clean_stem}_dubbed.srt"),
            os.path.join(base_dir, f"{clean_stem}_vi.srt"),
            os.path.join(base_dir, f"{clean_stem}.srt"),
        ]

        videos_dir = str(Path.home() / "Videos")
        candidates.extend([
            os.path.join(videos_dir, f"{file_stem}.omnigrab.json"),
            os.path.join(videos_dir, f"{clean_stem}.omnigrab.json"),
            os.path.join(videos_dir, f"{clean_stem}_dubbed.srt"),
            os.path.join(videos_dir, f"{clean_stem}_vi.srt"),
            os.path.join(videos_dir, f"{clean_stem}.srt"),
        ])

        for cand in candidates:
            if os.path.isfile(cand) and os.path.getsize(cand) > 10:
                return cand
    except Exception:
        pass
    return None


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
            w_lang = "zh" if clean_lang.startswith("zh") else (clean_lang.split("-")[0] if "-" in clean_lang else clean_lang or "zh")

            discovered_count = 0
            def _on_seg_discovered_studio(s):
                nonlocal discovered_count
                discovered_count += 1
                if discovered_count % 5 == 0 or discovered_count == 1:
                    self.progress_status.emit(f"Đang nhận diện giọng nói: mốc {int(s.end)}s (đã bóc tách {discovered_count} câu)...")

            raw_list = dubber.transcribe(
                temp_wav,
                lang=w_lang,
                on_segment_cb=_on_seg_discovered_studio,
            )

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
# CẦU NỐI TIẾN TRÌNH & THÔNG BÁO SANG PANEL PHẢI
# ══════════════════════════════════════════════════════════════════════

class _ForwardingStatusLabel(QObject):
    """
    Cầu nối thông báo: Chuyển tiếp toàn bộ chuỗi thông báo sang panel tiến trình bên phải
    thông qua tín hiệu status_message (không vẽ trực tiếp trên UI Studio để mở rộng không gian).
    """

    def __init__(self, owner: Any) -> None:
        super().__init__(owner)
        self._owner = owner
        self._text = ""
        self._visible = False

    def setText(self, text: str) -> None:
        self._text = str(text or "")
        self._visible = bool(self._text.strip())
        if hasattr(self._owner, "status_message"):
            self._owner.status_message.emit(self._text)

    def text(self) -> str:
        return self._text

    def setVisible(self, visible: bool) -> None:
        self._visible = visible
        if hasattr(self._owner, "status_message"):
            if not visible:
                self._text = ""
                self._owner.status_message.emit("")
            elif self._text:
                self._owner.status_message.emit(self._text)

    def isVisible(self) -> bool:
        return self._visible

    def setStyleSheet(self, style: str) -> None:
        pass


class _ForwardingProgressBar(QObject):
    """
    Cầu nối tiến trình: Chuyển tiếp trạng thái tiến trình sang thanh tiến trình panel bên phải
    thông qua tín hiệu progress_updated (không vẽ QProgressBar trên UI Studio).
    """

    def __init__(self, owner: Any) -> None:
        super().__init__(owner)
        self._owner = owner
        self._min = 0
        self._max = 100
        self._val = 0
        self._visible = False

    def setRange(self, minimum: int, maximum: int) -> None:
        self._min = minimum
        self._max = maximum

    def setFixedHeight(self, h: int) -> None:
        pass

    def setStyleSheet(self, style: str) -> None:
        pass

    def setValue(self, val: int) -> None:
        self._val = val
        if hasattr(self._owner, "progress_updated"):
            self._owner.progress_updated.emit(val, "")

    def value(self) -> int:
        return self._val

    def setVisible(self, visible: bool) -> None:
        self._visible = visible
        if hasattr(self._owner, "progress_updated"):
            if visible:
                val = -1 if (self._min == 0 and self._max == 0) else self._val
                self._owner.progress_updated.emit(val, "")
            else:
                self._owner.progress_updated.emit(0, "")

    def isVisible(self) -> bool:
        return self._visible


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
    video_loaded = pyqtSignal(str)                     # (video_path)
    tiktok_upload_requested = pyqtSignal(str, str)     # (video_path, caption)
    status_message = pyqtSignal(str)                   # Chuyển thông báo sang panel bên phải
    progress_updated = pyqtSignal(int, str)            # Chuyển tiến trình sang panel bên phải

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
        self._tiktok_worker: Optional[Any] = None
        self._btn_upload_tiktok: Optional[QPushButton] = None

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

        # Cầu nối chuyển tiếp tiến trình và thông báo sang Panel bên phải
        # (Không thêm vào layout bên trái để giải phóng toàn bộ diện tích cho Studio)
        self._progress_bar = _ForwardingProgressBar(self)
        self._progress_bar.setRange(0, 0)
        self._lbl_status_msg = _ForwardingStatusLabel(self)

        # ── 3. Dòng soạn thảo Caption & Hashtag TikTok ──
        caption_box = QFrame()
        caption_box.setStyleSheet(f"""
            QFrame {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border']};
                border-radius: 6px;
                padding: 2px 8px;
            }}
        """)
        c_layout = QHBoxLayout(caption_box)
        c_layout.setContentsMargins(6, 4, 6, 4)
        c_layout.setSpacing(8)

        lbl_caption = QLabel("🎵 Caption TikTok:")
        lbl_caption.setStyleSheet(f"color: {c['platform_tiktok']}; font-weight: 600; font-size: 12px;")
        c_layout.addWidget(lbl_caption)

        self._txt_tiktok_caption = QLineEdit()
        self._txt_tiktok_caption.setPlaceholderText("Nhập hoặc bấm '✨ Tạo Caption AI' để tự động tạo Caption giật tít + Hashtag...")
        self._txt_tiktok_caption.setStyleSheet(f"""
            QLineEdit {{
                background-color: {c['bg_input']};
                color: {c['text_primary']};
                border: 1px solid {c['border']};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {c['border_focus']};
            }}
        """)
        c_layout.addWidget(self._txt_tiktok_caption, 1)

        btn_ai_caption = QPushButton("✨ Tạo Caption AI")
        btn_ai_caption.setToolTip("Dùng Gemini AI phân tích kịch bản trên bảng để tạo 1 câu Caption giật tít kèm Hashtag thịnh hành")
        btn_ai_caption.setStyleSheet(self._btn_secondary_style())
        btn_ai_caption.clicked.connect(self._on_generate_ai_caption)
        c_layout.addWidget(btn_ai_caption)

        layout.addWidget(caption_box)

        # ── 4. Thanh chân trang (Footer Bar) ──
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
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {c['btn_green_hover']};
            }}
        """)
        btn_export_dub.clicked.connect(self._on_export_dubbing)
        footer_layout.addWidget(btn_export_dub)

        self._btn_upload_tiktok = QPushButton("📤  ĐĂNG NGAY LÊN TIKTOK")
        self._btn_upload_tiktok.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['platform_tiktok']};
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
        self._btn_upload_tiktok.clicked.connect(self._on_upload_now_tiktok)
        footer_layout.addWidget(self._btn_upload_tiktok)

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
                    self.table.scrollToItem(item)
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

    def _try_load_existing_subtitles(self, video_path: str) -> bool:
        """Tìm và tự động nạp phụ đề / kịch bản đã dịch trước đó của video nếu có."""
        sub_file = find_subtitles_for_video(video_path)
        if not sub_file:
            return False

        segments: List[DubSegment] = []
        if sub_file.endswith(".json"):
            segments = load_segments_from_json(sub_file)
        elif sub_file.endswith(".srt"):
            segments = parse_srt_file(sub_file)

        if not segments:
            return False

        self.set_segments(segments, is_finished=True)
        if self._lbl_status_msg:
            self._lbl_status_msg.setText(f"📋 Đã tự động tải kịch bản đã dịch ({len(segments)} câu thoại)")
            self._lbl_status_msg.setVisible(True)
        return True

    def load_video_to_studio(self, video_path: str, preserve_table: bool = False) -> None:
        """Nạp video lên khung phát QVideoWidget và đồng bộ kịch bản."""
        if not video_path or not os.path.isfile(video_path):
            return

        old_path = self.current_video_path
        is_same_file = (old_path == video_path)
        is_related = is_same_or_related_video(old_path, video_path)

        already_loaded_source = False
        try:
            from PyQt6.QtCore import QUrl
            if is_same_file and self.player.source() == QUrl.fromLocalFile(video_path):
                already_loaded_source = True
        except Exception:
            pass

        self.current_video_path = video_path
        self._lbl_video_title.setText(f"📁 {os.path.basename(video_path)}")

        if not already_loaded_source:
            from PyQt6.QtCore import QUrl
            self.media_player.setSource(QUrl.fromLocalFile(video_path))
            self.media_player.pause()
            self._btn_play.setText("▶  Phát")

        # KIỂM TRA GIỮ LẠI BẢNG KỊCH BẢN:
        # Nếu preserve_table hoặc video liên quan (như bản lồng tiếng vừa tạo xong),
        # và bảng hiện tại đang có dữ liệu câu thoại -> TUYỆT ĐỐI KHÔNG XÓA BẢNG!
        if (preserve_table or is_related) and self.table.rowCount() > 0:
            if self._lbl_status_msg:
                self._lbl_status_msg.setText(f"🎉 Kịch bản đã sẵn sàng ({self.table.rowCount()} câu thoại)")
                self._lbl_status_msg.setVisible(True)
            self.video_loaded.emit(video_path)
            return

        # NẾU LÀ ĐỔI SANG MỘT VIDEO KHÁC (hoặc bảng đang trống):
        # 1. Kiểm tra xem video này đã từng được dịch trước đó chưa (có file .omnigrab.json hoặc .srt)
        loaded = self._try_load_existing_subtitles(video_path)
        if not loaded:
            # Video mới toanh chưa từng dịch: Xóa bảng sạch sẽ để sẵn sàng dịch
            self.table.setRowCount(0)
            self.segments = []
            if self._lbl_status_msg:
                self._lbl_status_msg.setText("")
                self._lbl_status_msg.setVisible(False)
            if self._progress_bar:
                self._progress_bar.setVisible(False)

        self.video_loaded.emit(video_path)

    def load_video(self, video_path: str, preserve_table: bool = False) -> None:
        """Alias tương thích ngược."""
        self.load_video_to_studio(video_path, preserve_table=preserve_table)

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

        # Tự động lưu kịch bản phụ đề ra đĩa cho cả video gốc và video lồng tiếng
        segments = self.get_segments()
        if segments:
            if self.current_video_path:
                save_segments_to_files(self.current_video_path, segments)
            if output_video_path and os.path.isfile(output_video_path):
                save_segments_to_files(output_video_path, segments)

        if output_video_path and os.path.isfile(output_video_path):
            self.load_video_to_studio(output_video_path, preserve_table=True)

    def set_segments(self, segments: List[DubSegment], is_finished: bool = False) -> None:
        """Nạp danh sách DubSegment vào bảng 4 cột."""
        self.segments = segments
        self.on_segments_loaded(segments)
        for row, seg in enumerate(segments):
            text_trans = getattr(seg, 'text_trans', None)
            if text_trans:
                self.on_sentence_translated(row, text_trans)
                if is_finished:
                    self.on_sentence_completed(row, "🎙️ Đã lồng tiếng")

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
        if self.current_video_path:
            save_segments_to_files(self.current_video_path, segments)
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

        if self._tiktok_worker and self._tiktok_worker.isRunning():
            try:
                self._tiktok_worker.terminate()
                self._tiktok_worker.wait(1000)
            except Exception:
                pass
            if self._btn_upload_tiktok:
                self._btn_upload_tiktok.setEnabled(True)
            self._progress_bar.setVisible(False)
            self._lbl_status_msg.setVisible(False)

        main_win = self.window()
        if hasattr(main_win, "stop_dubbing"):
            main_win.stop_dubbing()

    def _on_back_clicked(self) -> None:
        self.back_requested.emit()

    # ─────────────────────────────────────────────────────────────────
    # TỰ ĐỘNG ĐĂNG VIDEO LÊN TIKTOK TỪ STUDIO
    # ─────────────────────────────────────────────────────────────────

    def on_tiktok_posted(self) -> None:
        """Cập nhật trạng thái '🚀 Đã đăng TikTok' cho toàn bộ các dòng trong bảng."""
        for row in range(self.table.rowCount()):
            status_item = QTableWidgetItem("🚀 Đã đăng TikTok")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, self.COL_STATUS, status_item)

    def _on_generate_ai_caption(self) -> None:
        """Dùng Gemini AI phân tích kịch bản trên bảng để tạo 1 câu Caption giật tít kèm Hashtag."""
        segments = self.get_segments()
        main_win = self.window()
        api_key = getattr(main_win, "gemini_api_key", "")
        v_title = Path(self.current_video_path).stem if self.current_video_path else ""

        try:
            from core.tiktok_uploader import generate_tiktok_caption
            self._lbl_status_msg.setText("✨ Đang dùng Gemini phân tích kịch bản để tạo Caption TikTok...")
            self._lbl_status_msg.setVisible(True)
            caption = generate_tiktok_caption(
                script_content=segments,
                api_key=api_key,
                video_title=v_title,
            )
            self._txt_tiktok_caption.setText(caption)
            self._lbl_status_msg.setText(f"✅ Đã tạo Caption: {caption[:50]}...")
        except Exception as e:
            self._lbl_status_msg.setText(f"⚠ Lỗi tạo Caption: {e}")

    def _on_upload_now_tiktok(self) -> None:
        """Đăng ngay video đang mở trong Studio lên kênh TikTok."""
        if not self.current_video_path or not os.path.isfile(self.current_video_path):
            QMessageBox.warning(self, "Chưa chọn video", "Vui lòng mở một video MP4 trước khi đăng lên TikTok.")
            return

        main_win = self.window()
        cookies_path = getattr(main_win, "tiktok_cookies_path", "")
        if not cookies_path or not os.path.isfile(cookies_path):
            f, _ = QFileDialog.getOpenFileName(
                self,
                "Chọn file Cookie TikTok (.txt)",
                "",
                "Cookie files (*.txt *.json);;Tất cả file (*.*)",
            )
            if f and os.path.isfile(f):
                cookies_path = f
                if hasattr(main_win, "tiktok_cookies_path"):
                    main_win.tiktok_cookies_path = f
                    if hasattr(main_win, "_save_settings"):
                        main_win._save_settings()
            else:
                QMessageBox.warning(
                    self,
                    "Chưa có Cookie",
                    "Cần file Cookie TikTok để đăng nhập và đăng video tự động.\n"
                    "Vui lòng vào Menu 'Tệp' ➔ 'Nạp file Cookie TikTok (.txt)...' trước."
                )
                return

        caption = self._txt_tiktok_caption.text().strip()
        if not caption:
            self._on_generate_ai_caption()
            caption = self._txt_tiktok_caption.text().strip()

        privacy = getattr(main_win, "tiktok_privacy", "public")
        headless = getattr(main_win, "tiktok_headless", False)

        if self._btn_upload_tiktok:
            self._btn_upload_tiktok.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._lbl_status_msg.setVisible(True)
        self._lbl_status_msg.setText("🚀 Đang khởi động trình duyệt đăng video lên TikTok...")

        from core.tiktok_uploader import TikTokUploadWorker
        self._tiktok_worker = TikTokUploadWorker(
            video_path=self.current_video_path,
            caption=caption,
            cookies_path=cookies_path,
            privacy=privacy,
            headless=headless,
            parent=self,
        )
        self._tiktok_worker.log_message.connect(self._lbl_status_msg.setText)
        self._tiktok_worker.upload_finished.connect(self._on_tiktok_worker_finished)
        self._tiktok_worker.start()

    def _on_tiktok_worker_finished(self, video_path: str, success: bool, msg: str) -> None:
        if self._btn_upload_tiktok:
            self._btn_upload_tiktok.setEnabled(True)
        self._progress_bar.setVisible(False)

        if success:
            self.on_tiktok_posted()
            self._lbl_status_msg.setText("🎉 Đã đăng thành công video lên kênh TikTok!")
            QMessageBox.information(
                self,
                "Đăng TikTok thành công",
                f"🎉 Đã đăng thành công video lên kênh TikTok:\n{os.path.basename(video_path)}"
            )
        else:
            self._lbl_status_msg.setText(f"❌ Lỗi đăng TikTok: {msg}")
            QMessageBox.warning(
                self,
                "Lỗi đăng TikTok",
                f"Không thể đăng video lên TikTok:\n{msg}"
            )

