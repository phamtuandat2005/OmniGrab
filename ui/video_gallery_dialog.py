"""
ui/video_gallery_dialog.py — Thư viện Xem video đã tải xuống (YouTube Grid Feed & Inline Player).

Thiết kế theo chuẩn YouTube Home Feed:
  - Không dùng màn hình xem riêng biệt chia đôi.
  - Hiển thị theo lưới các ô video (Card) chuẩn tỉ lệ 16:9, chia làm 2 Tab rõ ràng:
      * Tab 1: Video chưa dịch (Video gốc)
      * Tab 2: Video đã dịch (Video AI lồng tiếng)
  - Xem trực tiếp ngay trên ô nhỏ (Inline Playback trong Card):
      * Bấm vào ô là video phát ngay tại chỗ trong ô nhỏ đó.
      * Có thanh trượt tua, nút Play/Pause, Âm lượng, Thời lượng.
  - Có nút "Phóng to" (Maximize) và "Thu nhỏ" (Minimize):
      * Nút phóng to trên mỗi ô: mở rộng video lên toàn màn hình / chế độ rạp phim.
      * Nút thu nhỏ: thu gọn video quay trở lại ô lưới nhỏ mà không bị ngắt quãng.
  - Trích xuất ảnh thumbnail thực tế và huy hiệu thời lượng (Duration Badge: 05:35, 1:40:08)
    như YouTube bằng ffmpeg/ffprobe chạy ngầm mượt mà.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# pyrefly: ignore [missing-import]
from PyQt6 import sip
# pyrefly: ignore [missing-import]
from PyQt6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt, QThread, QUrl, pyqtSignal
# pyrefly: ignore [missing-import]
from PyQt6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QFont,
    QIcon,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPixmap,
    QResizeEvent,
    QShortcut,
)
# pyrefly: ignore [missing-import]
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
# pyrefly: ignore [missing-import]
from PyQt6.QtMultimediaWidgets import QVideoWidget
# pyrefly: ignore [missing-import]
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ui.icons import get_svg_icon, get_svg_pixmap
from ui.styles import COLORS, btn_primary_style, btn_secondary_style, btn_stop_style


VALID_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov", ".avi"}
DUBBED_TAGS = ("_dubbed", "_vi", "_translated", "_voice", "[dub]", "[lồng tiếng]", "[longtieng]", "_longtieng")


def _is_valid(obj: Optional[QObject]) -> bool:
    """Kiểm tra an toàn xem đối tượng Qt C++ còn sống hay đã bị xoá."""
    if obj is None:
        return False
    try:
        return not sip.isdeleted(obj)
    except Exception:
        return False


def _get_ffmpeg_bin() -> str:
    if "FFMPEG_BINARY" in os.environ and os.path.isfile(os.environ["FFMPEG_BINARY"]):
        return os.environ["FFMPEG_BINARY"]
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for c_dir in [base, os.path.join(base, "_internal"), getattr(sys, "_MEIPASS", "")]:
        if c_dir and os.path.isdir(c_dir):
            p = os.path.join(c_dir, "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
            if os.path.isfile(p):
                return p
    return shutil.which("ffmpeg") or "ffmpeg"


def _get_ffprobe_bin() -> str:
    if "FFPROBE_BINARY" in os.environ and os.path.isfile(os.environ["FFPROBE_BINARY"]):
        return os.environ["FFPROBE_BINARY"]
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for c_dir in [base, os.path.join(base, "_internal"), getattr(sys, "_MEIPASS", "")]:
        if c_dir and os.path.isdir(c_dir):
            p = os.path.join(c_dir, "ffprobe.exe" if sys.platform == "win32" else "ffprobe")
            if os.path.isfile(p):
                return p
    return shutil.which("ffprobe") or "ffprobe"


def format_clock_ms(ms: int) -> str:
    """Chuyển milliseconds sang mm:ss hoặc hh:mm:ss."""
    if ms < 0:
        ms = 0
    total_seconds = int(ms // 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def format_clock_sec(seconds: float) -> str:
    """Chuyển giây sang mm:ss hoặc hh:mm:ss."""
    if seconds <= 0:
        return "--:--"
    total_sec = int(seconds)
    hours = total_sec // 3600
    mins = (total_sec % 3600) // 60
    secs = total_sec % 60
    if hours > 0:
        return f"{hours}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def format_file_size(bytes_size: int) -> str:
    """Định dạng dung lượng file theo đơn vị KB / MB / GB."""
    if bytes_size <= 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024.0 or unit == "GB":
            return f"{bytes_size:.1f} {unit}" if unit != "B" else f"{int(bytes_size)} B"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} GB"


def format_mtime(timestamp: float) -> str:
    """Định dạng ngày giờ sửa đổi."""
    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return ""


@dataclass
class VideoFileInfo:
    path: str
    filename: str
    title: str
    size_bytes: int
    modified_time: float
    is_dubbed: bool
    duration_sec: float = 0.0
    thumbnail_path: Optional[str] = None


def scan_downloaded_videos(directory: str) -> Tuple[List[VideoFileInfo], List[VideoFileInfo]]:
    """
    Quét thư mục tải xuống và phân loại thành:
    (danh_sách_video_chưa_dịch, danh_sách_video_đã_dịch)
    """
    raw_list: List[VideoFileInfo] = []
    dubbed_list: List[VideoFileInfo] = []

    if not directory or not os.path.isdir(directory):
        return raw_list, dubbed_list

    found_files: List[str] = []
    try:
        for root, dirs, files in os.walk(directory):
            rel = os.path.relpath(root, directory)
            if rel != "." and rel.count(os.sep) >= 2:
                continue
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in VALID_EXTENSIONS:
                    found_files.append(os.path.join(root, f))
    except Exception:
        pass

    for fpath in found_files:
        try:
            stat = os.stat(fpath)
            fname = os.path.basename(fpath)
            stem = os.path.splitext(fname)[0]
            stem_lower = stem.lower()
            parent_dir = os.path.basename(os.path.dirname(fpath)).lower()

            is_dubbed = False
            if any(tag in stem_lower for tag in DUBBED_TAGS):
                is_dubbed = True
            elif parent_dir in ("dubbed", "long_tieng", "translated", "lồng tiếng"):
                is_dubbed = True

            clean_title = stem
            for tag in DUBBED_TAGS:
                clean_title = clean_title.replace(tag, "").replace(tag.upper(), "")
            clean_title = clean_title.strip(" _-")
            if not clean_title:
                clean_title = stem

            item = VideoFileInfo(
                path=fpath,
                filename=fname,
                title=clean_title,
                size_bytes=stat.st_size,
                modified_time=stat.st_mtime,
                is_dubbed=is_dubbed,
            )
            if is_dubbed:
                dubbed_list.append(item)
            else:
                raw_list.append(item)
        except Exception:
            continue

    raw_list.sort(key=lambda x: x.modified_time, reverse=True)
    dubbed_list.sort(key=lambda x: x.modified_time, reverse=True)
    return raw_list, dubbed_list


# ══════════════════════════════════════════════════════════════════════
# TIẾN TRÌNH TRÍCH XUẤT THUMBNAIL & THỜI LƯỢNG CHẠY NGẦM (ASYNC)
# ══════════════════════════════════════════════════════════════════════

class ThumbnailWorker(QThread):
    """Trích xuất ảnh đại diện và đo thời lượng video ngầm để không đơ giao diện."""

    meta_ready = pyqtSignal(str, str, float)  # video_path, thumb_path, duration_sec

    def __init__(self, video_paths: List[str], parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.video_paths = video_paths
        self._is_running = True
        self.cache_dir = Path.home() / ".omnigrab_cache" / "thumbnails"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ffmpeg_bin = _get_ffmpeg_bin()
        self.ffprobe_bin = _get_ffprobe_bin()

    def stop(self) -> None:
        self._is_running = False

    def run(self) -> None:
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        for vpath in self.video_paths:
            if not self._is_running:
                break
            if not os.path.isfile(vpath):
                continue

            try:
                # Key cache theo đường dẫn và thời gian sửa đổi
                mtime = os.path.getmtime(vpath)
                h = hashlib.md5(f"{vpath}_{mtime}".encode("utf-8")).hexdigest()
                thumb_file = str(self.cache_dir / f"{h}.jpg")

                duration_sec = 0.0

                # 1. Đo thời lượng qua ffprobe
                try:
                    p_probe = subprocess.run(
                        [
                            self.ffprobe_bin,
                            "-v", "error",
                            "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1",
                            vpath,
                        ],
                        startupinfo=startupinfo,
                        capture_output=True,
                        text=True,
                        timeout=3,
                    )
                    if p_probe.returncode == 0 and p_probe.stdout.strip():
                        duration_sec = float(p_probe.stdout.strip())
                except Exception:
                    pass

                # 2. Sinh ảnh thumbnail nếu chưa có
                if not os.path.isfile(thumb_file) or os.path.getsize(thumb_file) == 0:
                    seek_pos = "00:00:02"
                    if duration_sec > 5:
                        seek_pos = str(int(min(duration_sec * 0.15, 15)))

                    subprocess.run(
                        [
                            self.ffmpeg_bin,
                            "-ss", seek_pos,
                            "-i", vpath,
                            "-vframes", "1",
                            "-vf", "scale=480:-1",
                            "-q:v", "3",
                            thumb_file,
                            "-y",
                        ],
                        startupinfo=startupinfo,
                        capture_output=True,
                        timeout=5,
                    )

                if os.path.isfile(thumb_file) and os.path.getsize(thumb_file) > 0:
                    self.meta_ready.emit(vpath, thumb_file, duration_sec)
                elif duration_sec > 0:
                    self.meta_ready.emit(vpath, "", duration_sec)

            except Exception:
                continue


# ══════════════════════════════════════════════════════════════════════
# WIDGET THẺ VIDEO CHUẨN YOUTUBE FEED (XEM TRỰC TIẾP TRÊN Ô NHỎ)
# ══════════════════════════════════════════════════════════════════════

class YouTubeVideoCard(QFrame):
    """
    Thẻ video chuẩn giao diện YouTube:
      - Ô 16:9 chứa Thumbnail có duration badge, nút Play và nút Phóng to.
      - Có thể phát trực tiếp video ngay trong ô nhỏ này (Inline Playback).
      - Phần thông tin bên dưới: Avatar kênh/loại, Tiêu đề (2 dòng), Dung lượng, Ngày tải.
    """

    play_requested = pyqtSignal(object)       # self
    maximize_requested = pyqtSignal(object)   # self
    stop_requested = pyqtSignal(object)       # self

    def __init__(self, video: VideoFileInfo, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.video = video
        self.is_active_playing = False
        self._cached_pixmap: Optional[QPixmap] = None

        self.setObjectName("YouTubeCard")
        self.setFixedWidth(340)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        main_l = QVBoxLayout(self)
        main_l.setContentsMargins(10, 10, 10, 12)
        main_l.setSpacing(10)

        # ── 1. KHUNG VIDEO 16:9 (320 x 180 px) ──
        self.video_box = QFrame()
        self.video_box.setObjectName("VideoBox")
        self.video_box.setFixedSize(320, 180)
        self.video_box.setCursor(Qt.CursorShape.PointingHandCursor)

        self.vb_layout = QVBoxLayout(self.video_box)
        self.vb_layout.setContentsMargins(0, 0, 0, 0)
        self.vb_layout.setSpacing(0)

        # Container cho lớp Thumbnail (Khi chưa phát)
        self.thumb_container = QWidget(self.video_box)
        self.thumb_container.setFixedSize(320, 180)
        tc_l = QVBoxLayout(self.thumb_container)
        tc_l.setContentsMargins(0, 0, 0, 0)

        # Ảnh Thumbnail hoặc Poster dự phòng
        self.lbl_thumbnail = QLabel()
        self.lbl_thumbnail.setFixedSize(320, 180)
        self.lbl_thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_thumbnail.setScaledContents(True)
        self._set_placeholder_thumbnail()
        tc_l.addWidget(self.lbl_thumbnail)

        # Lớp phủ: Nút Phóng to ở góc trên phải
        self.btn_quick_max = QPushButton(self.thumb_container)
        self.btn_quick_max.setIcon(get_svg_icon("maximize", "#ffffff", size=14))
        self.btn_quick_max.setToolTip("Phóng to xem màn hình lớn")
        self.btn_quick_max.setFixedSize(28, 28)
        self.btn_quick_max.move(284, 8)
        self.btn_quick_max.setStyleSheet("""
            QPushButton {
                background-color: rgba(15, 23, 42, 0.75);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3b82f6;
                border: 1px solid #60a5fa;
            }
        """)
        self.btn_quick_max.clicked.connect(lambda: self.maximize_requested.emit(self))

        # Lớp phủ: Nút tròn Play ở chính giữa (chuẩn YouTube)
        self.btn_center_play = QPushButton(self.thumb_container)
        self.btn_center_play.setIcon(get_svg_icon("play", "#ffffff", size=24))
        self.btn_center_play.setFixedSize(52, 52)
        self.btn_center_play.move(134, 64)
        self.btn_center_play.setStyleSheet("""
            QPushButton {
                background-color: rgba(15, 23, 42, 0.82);
                border: 2px solid rgba(255, 255, 255, 0.35);
                border-radius: 26px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                border: 2px solid #ffffff;
            }
        """)
        self.btn_center_play.clicked.connect(lambda: self.play_requested.emit(self))

        # Lớp phủ: Huy hiệu thời lượng (Duration Badge ở góc dưới phải)
        self.lbl_duration_pill = QLabel("--:--", self.thumb_container)
        self.lbl_duration_pill.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 0.85);
                color: #ffffff;
                font-size: 11px;
                font-weight: 700;
                padding: 2px 6px;
                border-radius: 4px;
            }
        """)
        self.lbl_duration_pill.move(265, 152)

        self.vb_layout.addWidget(self.thumb_container)

        # Khung chứa video widget khi đang phát trực tiếp trong ô nhỏ
        self.player_host_widget = QWidget()
        self.player_host_widget.setFixedSize(320, 180)
        self.player_host_layout = QVBoxLayout(self.player_host_widget)
        self.player_host_layout.setContentsMargins(0, 0, 0, 0)
        self.player_host_layout.setSpacing(0)
        self.player_host_widget.hide()
        self.vb_layout.addWidget(self.player_host_widget)

        # Bấm chuột vào khung thumbnail -> Phát ngay tại ô nhỏ
        self.thumb_container.mousePressEvent = self._on_thumb_click

        main_l.addWidget(self.video_box)

        # ── 2. THANH ĐIỀU KHIỂN MINI (INLINE CONTROLS) ──
        # Xuất hiện ngay dưới video khi đang phát trực tiếp trên ô nhỏ
        self.mini_controls = QFrame()
        self.mini_controls.setObjectName("MiniControls")
        self.mini_controls.setFixedWidth(320)
        mc_l = QVBoxLayout(self.mini_controls)
        mc_l.setContentsMargins(4, 4, 4, 4)
        mc_l.setSpacing(4)

        # Thanh tua thời gian mini
        self.mini_slider = QSlider(Qt.Orientation.Horizontal)
        self.mini_slider.setRange(0, 0)
        self.mini_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: #334155;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #ef4444;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 2px solid #ef4444;
                width: 10px;
                height: 10px;
                margin: -3px 0;
                border-radius: 5px;
            }
        """)
        mc_l.addWidget(self.mini_slider)

        # Hàng nút: Play/Pause, Thời lượng, Âm lượng, Phóng to, Dừng
        btn_bar = QHBoxLayout()
        btn_bar.setContentsMargins(0, 0, 0, 0)
        btn_bar.setSpacing(6)

        self.btn_mini_play = QPushButton()
        self.btn_mini_play.setIcon(get_svg_icon("pause", "#ffffff", size=14))
        self.btn_mini_play.setFixedSize(28, 28)
        self.btn_mini_play.setStyleSheet(btn_primary_style())
        btn_bar.addWidget(self.btn_mini_play)

        self.lbl_mini_time = QLabel("00:00 / 00:00")
        self.lbl_mini_time.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; font-weight: 600;")
        btn_bar.addWidget(self.lbl_mini_time)

        btn_bar.addStretch(1)

        self.btn_mini_mute = QPushButton()
        self.btn_mini_mute.setIcon(get_svg_icon("volume", COLORS["text_secondary"], size=14))
        self.btn_mini_mute.setFixedSize(26, 26)
        self.btn_mini_mute.setStyleSheet(btn_secondary_style())
        btn_bar.addWidget(self.btn_mini_mute)

        # Nút PHÓNG TO (Xem to hơn)
        self.btn_mini_max = QPushButton()
        self.btn_mini_max.setIcon(get_svg_icon("maximize", COLORS["text_secondary"], size=14))
        self.btn_mini_max.setToolTip("Phóng to xem toàn màn hình")
        self.btn_mini_max.setFixedSize(26, 26)
        self.btn_mini_max.setStyleSheet(btn_secondary_style())
        self.btn_mini_max.clicked.connect(lambda: self.maximize_requested.emit(self))
        btn_bar.addWidget(self.btn_mini_max)

        # Nút Dừng phát
        self.btn_mini_stop = QPushButton()
        self.btn_mini_stop.setIcon(get_svg_icon("x", COLORS["text_secondary"], size=14))
        self.btn_mini_stop.setToolTip("Đóng video đang phát")
        self.btn_mini_stop.setFixedSize(26, 26)
        self.btn_mini_stop.setStyleSheet(btn_secondary_style())
        self.btn_mini_stop.clicked.connect(lambda: self.stop_requested.emit(self))
        btn_bar.addWidget(self.btn_mini_stop)

        mc_l.addLayout(btn_bar)
        self.mini_controls.hide()
        main_l.addWidget(self.mini_controls)

        # ── 3. THÔNG TIN VIDEO (METADATA DƯỚI VIDEO CHUẨN YOUTUBE) ──
        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 2, 0, 0)
        meta_row.setSpacing(10)
        meta_row.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Avatar tròn phân biệt loại video (Gốc / Đã dịch)
        avatar = QFrame()
        avatar.setFixedSize(36, 36)
        avatar_bg = "#2563eb" if self.video.is_dubbed else "#334155"
        avatar.setStyleSheet(f"""
            QFrame {{
                background-color: {avatar_bg};
                border-radius: 18px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }}
        """)
        av_l = QVBoxLayout(avatar)
        av_l.setContentsMargins(0, 0, 0, 0)
        av_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic_lbl = QLabel()
        ic_name = "film" if self.video.is_dubbed else "video"
        ic_lbl.setPixmap(get_svg_pixmap(ic_name, size=18, color="#ffffff"))
        av_l.addWidget(ic_lbl)
        meta_row.addWidget(avatar)

        # Cột Tiêu đề và thông số
        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(3)

        self.lbl_title = QLabel(self.video.title if self.video.title else self.video.filename)
        self.lbl_title.setWordWrap(True)
        self.lbl_title.setMaximumHeight(38)
        self.lbl_title.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['text_primary']};
                font-weight: 700;
                font-size: 13px;
                line-height: 1.2;
            }}
        """)
        self.lbl_title.setToolTip(self.video.filename)
        info_col.addWidget(self.lbl_title)

        # Thông tin dung lượng và ngày giờ
        meta_txt = f"{format_file_size(self.video.size_bytes)}  •  {format_mtime(self.video.modified_time)}"
        lbl_meta = QLabel(meta_txt)
        lbl_meta.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        info_col.addWidget(lbl_meta)

        # Badge tag trạng thái
        badge_box = QHBoxLayout()
        badge_box.setSpacing(6)
        tag_lbl = QLabel("ĐÃ DỊCH AI" if self.video.is_dubbed else "CHƯA DỊCH (GỐC)")
        tag_color = "#3b82f6" if self.video.is_dubbed else "#64748b"
        tag_bg = "rgba(59, 130, 246, 0.15)" if self.video.is_dubbed else "rgba(100, 116, 139, 0.15)"
        tag_lbl.setStyleSheet(f"""
            QLabel {{
                color: {tag_color};
                background-color: {tag_bg};
                border: 1px solid {tag_color};
                border-radius: 3px;
                padding: 1px 5px;
                font-size: 9.5px;
                font-weight: 700;
            }}
        """)
        badge_box.addWidget(tag_lbl)
        badge_box.addStretch(1)
        info_col.addLayout(badge_box)

        meta_row.addLayout(info_col, 1)

        # Nút 3 chấm tùy chọn (More actions)
        btn_more = QPushButton()
        btn_more.setIcon(get_svg_icon("more-vertical", COLORS["text_secondary"], size=16))
        btn_more.setFixedSize(24, 24)
        btn_more.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
        """)
        btn_more.clicked.connect(lambda: self._show_context_menu(btn_more))
        meta_row.addWidget(btn_more)

        main_l.addLayout(meta_row)

    def _apply_style(self) -> None:
        self.setStyleSheet(f"""
            QFrame#YouTubeCard {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
            QFrame#YouTubeCard:hover {{
                border: 1px solid {COLORS['accent_primary']};
            }}
            QFrame#VideoBox {{
                background-color: #000000;
                border-radius: 8px;
            }}
            QFrame#MiniControls {{
                background-color: {COLORS['bg_secondary']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
            }}
        """)

    def _set_placeholder_thumbnail(self) -> None:
        """Tạo ảnh bìa giả lập phong cách video YouTube khi chưa có thumbnail."""
        pixmap = QPixmap(320, 180)
        pixmap.fill(QColor("#0f172a"))
        painter = QPainter(pixmap)
        # Họa tiết sóng nhẹ hoặc watermark
        painter.setPen(QColor(51, 65, 85, 120))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.drawText(QRect(0, 0, 320, 180), Qt.AlignmentFlag.AlignCenter, "OmniGrab Video")
        painter.end()
        self.lbl_thumbnail.setPixmap(pixmap)

    def update_metadata(self, thumb_path: str, duration_sec: float) -> None:
        """Cập nhật thumbnail thật và badge thời lượng khi chạy ngầm xong."""
        try:
            if duration_sec > 0:
                self.video.duration_sec = duration_sec
                time_str = format_clock_sec(duration_sec)
                self.lbl_duration_pill.setText(time_str)
                self.lbl_duration_pill.adjustSize()
                pill_w = self.lbl_duration_pill.width()
                self.lbl_duration_pill.move(320 - pill_w - 8, 180 - self.lbl_duration_pill.height() - 8)

            if thumb_path and os.path.isfile(thumb_path):
                pix = QPixmap(thumb_path)
                if not pix.isNull():
                    self._cached_pixmap = pix.scaled(
                        320, 180,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self.lbl_thumbnail.setPixmap(self._cached_pixmap)
        except RuntimeError:
            pass

    def set_playing_mode(self, is_playing: bool) -> None:
        """Chuyển đổi giao diện giữa chế độ xem Thumbnail và Xem trực tiếp trên ô nhỏ."""
        self.is_active_playing = is_playing
        try:
            if is_playing:
                self.thumb_container.hide()
                self.player_host_widget.show()
                self.mini_controls.show()
                self.setStyleSheet(f"""
                    QFrame#YouTubeCard {{
                        background-color: {COLORS['bg_card']};
                        border: 2px solid {COLORS['accent_primary']};
                        border-radius: 10px;
                    }}
                """)
            else:
                self.player_host_widget.hide()
                self.mini_controls.hide()
                self.thumb_container.show()
                self._apply_style()
        except RuntimeError:
            pass

    def _on_thumb_click(self, event: QMouseEvent) -> None:
        # Nếu người dùng không click trúng nút con (như nút phóng to), kích hoạt phát
        self.play_requested.emit(self)

    def _show_context_menu(self, source_btn: QWidget) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {COLORS['bg_secondary']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 16px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {COLORS['accent_primary']};
                color: #ffffff;
            }}
        """)

        act_max = menu.addAction(get_svg_icon("maximize", "#ffffff"), "Phóng to xem toàn màn hình")
        act_open_def = menu.addAction(get_svg_icon("external-link", COLORS["text_secondary"]), "Mở bằng trình phát ngoài")
        act_open_folder = menu.addAction(get_svg_icon("folder-open", COLORS["text_secondary"]), "Mở thư mục chứa video")
        act_copy_path = menu.addAction(get_svg_icon("clipboard", COLORS["text_secondary"]), "Sao chép đường dẫn file")

        pos = source_btn.mapToGlobal(QPoint(0, source_btn.height()))
        selected = menu.exec(pos)
        if selected == act_max:
            self.maximize_requested.emit(self)
        elif selected == act_open_def:
            try:
                os.startfile(self.video.path)
            except Exception:
                pass
        elif selected == act_open_folder:
            try:
                subprocess.Popen(f'explorer /select,"{os.path.normpath(self.video.path)}"')
            except Exception:
                pass
        elif selected == act_copy_path:
            QApplication.clipboard().setText(self.video.path)


# ══════════════════════════════════════════════════════════════════════
# MÀN HÌNH CHÍNH: VideoGalleryDialog (YouTube Grid Feed & Player)
# ══════════════════════════════════════════════════════════════════════

class VideoGalleryDialog(QDialog):
    """
    Thư viện video đã tải xuống chuẩn giao diện YouTube:
      - 2 Tab rõ ràng: Video chưa dịch (Gốc) & Video đã dịch (AI Voice).
      - Không có màn hình xem riêng biệt; mỗi video là 1 ô nhỏ xem trực tiếp ngay trên ô đó.
      - Có nút "Phóng to" (Maximize) và "Thu nhỏ" (Minimize) để phóng to xem toàn màn hình và thu nhỏ về ô.
    """

    def __init__(
        self,
        downloads_dir: str,
        initial_video_path: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.downloads_dir = downloads_dir
        self.current_video_path: str = ""
        self.active_card: Optional[YouTubeVideoCard] = None

        self._raw_videos: List[VideoFileInfo] = []
        self._dubbed_videos: List[VideoFileInfo] = []
        self._cards_raw: List[YouTubeVideoCard] = []
        self._cards_dubbed: List[YouTubeVideoCard] = []

        self._thumb_worker: Optional[ThumbnailWorker] = None
        self._is_seeking = False
        self._is_maximized_view = False

        self.setWindowTitle("Xem video đã tải xuống — OmniGrab Player")
        self.setWindowIcon(get_svg_icon("film", COLORS["brand"]))
        self.resize(1180, 760)
        self.setMinimumSize(880, 560)

        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMinMaxButtonsHint
            | Qt.WindowType.WindowCloseButtonHint
        )

        self._init_player()
        self._build_ui()
        self._apply_styles()
        self._bind_shortcuts()

        self.refresh_videos(select_path=initial_video_path)

    def _init_player(self) -> None:
        """Khởi tạo trình phát media chung duy nhất để tối ưu hiệu năng."""
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.85)

        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #000000; border-radius: 6px;")
        self.player.setVideoOutput(self.video_widget)

        self.player.positionChanged.connect(self._on_player_position_changed)
        self.player.durationChanged.connect(self._on_player_duration_changed)
        self.player.playbackStateChanged.connect(self._on_player_state_changed)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Sử dụng QStackedWidget để chuyển đổi giữa:
        # [0]: Màn hình Lưới video 2 Tab (YouTube Grid Feed)
        # [1]: Màn hình Phóng to xem lớn (Expanded View) có nút Thu nhỏ
        self.stack = QStackedWidget(self)

        # ══════════════════════════════════════════════════════════════
        # VIEW 0: MÀN HÌNH LƯỚI VIDEO (YOUTUBE GRID 2 TAB)
        # ══════════════════════════════════════════════════════════════
        self.view_grid = QWidget()
        vg_layout = QVBoxLayout(self.view_grid)
        vg_layout.setContentsMargins(0, 0, 0, 0)
        vg_layout.setSpacing(10)

        # Thanh tiêu đề và công cụ trên cùng
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        lbl_head = QLabel("Thư viện video đã tải xuống")
        lbl_head.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 16px; font-weight: 700;")
        top_bar.addWidget(lbl_head)

        top_bar.addStretch(1)

        # Ô tìm kiếm video theo tên
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Tìm kiếm video theo tên...")
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.setFixedWidth(260)
        self.txt_search.textChanged.connect(self._on_search_changed)
        top_bar.addWidget(self.txt_search)

        # Nút Mở thư mục
        btn_folder = QPushButton("Thư mục")
        btn_folder.setIcon(get_svg_icon("folder-open", COLORS["text_secondary"]))
        btn_folder.setStyleSheet(btn_secondary_style())
        btn_folder.clicked.connect(self._open_downloads_folder)
        top_bar.addWidget(btn_folder)

        # Nút Làm mới
        btn_refresh = QPushButton("Làm mới")
        btn_refresh.setIcon(get_svg_icon("refresh", COLORS["text_secondary"]))
        btn_refresh.setStyleSheet(btn_secondary_style())
        btn_refresh.clicked.connect(lambda: self.refresh_videos())
        top_bar.addWidget(btn_refresh)

        vg_layout.addLayout(top_bar)

        # 2 Tab: Video chưa dịch & Video đã dịch
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # Tab 1: Video chưa dịch
        self.scroll_raw = QScrollArea()
        self.scroll_raw.setWidgetResizable(True)
        self.container_raw = QWidget()
        self.grid_raw = QGridLayout(self.container_raw)
        self.grid_raw.setContentsMargins(8, 12, 8, 12)
        self.grid_raw.setSpacing(16)
        self.grid_raw.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll_raw.setWidget(self.container_raw)
        self.tabs.addTab(self.scroll_raw, get_svg_icon("video", COLORS["text_secondary"]), "Video chưa dịch (0)")

        # Tab 2: Video đã dịch
        self.scroll_dubbed = QScrollArea()
        self.scroll_dubbed.setWidgetResizable(True)
        self.container_dubbed = QWidget()
        self.grid_dubbed = QGridLayout(self.container_dubbed)
        self.grid_dubbed.setContentsMargins(8, 12, 8, 12)
        self.grid_dubbed.setSpacing(16)
        self.grid_dubbed.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll_dubbed.setWidget(self.container_dubbed)
        self.tabs.addTab(self.scroll_dubbed, get_svg_icon("film", "#3b82f6"), "Video đã dịch (0)")

        vg_layout.addWidget(self.tabs, 1)
        self.stack.addWidget(self.view_grid)

        # ══════════════════════════════════════════════════════════════
        # VIEW 1: MÀN HÌNH PHÓNG TO (EXPANDED / THEATER PLAYER)
        # ══════════════════════════════════════════════════════════════
        self.view_expanded = QWidget()
        ve_layout = QVBoxLayout(self.view_expanded)
        ve_layout.setContentsMargins(0, 0, 0, 0)
        ve_layout.setSpacing(8)

        # Thanh điều hướng trên cùng của màn hình Phóng to
        exp_top = QHBoxLayout()
        exp_top.setSpacing(12)

        # NÚT THU NHỎ QUAN TRỌNG (Minimize button)
        self.btn_back_to_grid = QPushButton("Thu nhỏ về ô lưới (Esc)")
        self.btn_back_to_grid.setIcon(get_svg_icon("minimize", "#ffffff", size=16))
        self.btn_back_to_grid.setStyleSheet(btn_primary_style())
        self.btn_back_to_grid.setFixedHeight(34)
        self.btn_back_to_grid.clicked.connect(self._minimize_to_card)
        exp_top.addWidget(self.btn_back_to_grid)

        self.lbl_exp_title = QLabel("Đang xem video")
        self.lbl_exp_title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 14px; font-weight: 700;")
        exp_top.addWidget(self.lbl_exp_title, 1)

        ve_layout.addLayout(exp_top)

        # Khung chứa video phóng to (Full width/height)
        self.expanded_video_frame = QFrame()
        self.expanded_video_frame.setStyleSheet("background-color: #000000; border-radius: 8px;")
        self.evf_layout = QVBoxLayout(self.expanded_video_frame)
        self.evf_layout.setContentsMargins(0, 0, 0, 0)
        ve_layout.addWidget(self.expanded_video_frame, 1)

        # Thanh điều khiển đầy đủ ở chế độ phóng to
        exp_ctrl = QFrame()
        exp_ctrl.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
            }}
        """)
        ec_layout = QVBoxLayout(exp_ctrl)
        ec_layout.setContentsMargins(10, 8, 10, 8)
        ec_layout.setSpacing(6)

        # Thanh tua lớn
        self.exp_slider = QSlider(Qt.Orientation.Horizontal)
        self.exp_slider.setRange(0, 0)
        self.exp_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 6px;
                background: {COLORS['bg_input_border']};
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {COLORS['accent_primary']};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: #ffffff;
                border: 2px solid {COLORS['accent_primary']};
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }}
        """)
        self.exp_slider.sliderPressed.connect(self._on_slider_pressed)
        self.exp_slider.sliderReleased.connect(self._on_slider_released)
        self.exp_slider.sliderMoved.connect(self._on_slider_moved)
        ec_layout.addWidget(self.exp_slider)

        # Hàng nút Play, 5s, Âm lượng, Thu nhỏ
        exp_btns = QHBoxLayout()
        exp_btns.setSpacing(8)

        self.btn_exp_play = QPushButton("Tạm dừng")
        self.btn_exp_play.setIcon(get_svg_icon("pause", "#ffffff"))
        self.btn_exp_play.setStyleSheet(btn_primary_style())
        self.btn_exp_play.setFixedWidth(100)
        self.btn_exp_play.clicked.connect(self._toggle_play)
        exp_btns.addWidget(self.btn_exp_play)

        btn_rew = QPushButton("5s")
        btn_rew.setIcon(get_svg_icon("rewind-5", COLORS["text_secondary"]))
        btn_rew.setFixedWidth(60)
        btn_rew.setStyleSheet(btn_secondary_style())
        btn_rew.clicked.connect(lambda: self._seek_relative(-5000))
        exp_btns.addWidget(btn_rew)

        btn_fwd = QPushButton("5s")
        btn_fwd.setIcon(get_svg_icon("forward-5", COLORS["text_secondary"]))
        btn_fwd.setFixedWidth(60)
        btn_fwd.setStyleSheet(btn_secondary_style())
        btn_fwd.clicked.connect(lambda: self._seek_relative(5000))
        exp_btns.addWidget(btn_fwd)

        self.lbl_exp_time = QLabel("00:00 / 00:00")
        self.lbl_exp_time.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px; font-weight: 600; min-width: 95px;")
        exp_btns.addWidget(self.lbl_exp_time)

        exp_btns.addStretch(1)

        self.btn_exp_mute = QPushButton()
        self.btn_exp_mute.setIcon(get_svg_icon("volume", COLORS["text_secondary"]))
        self.btn_exp_mute.setFixedSize(30, 30)
        self.btn_exp_mute.setStyleSheet(btn_secondary_style())
        self.btn_exp_mute.clicked.connect(self._toggle_mute)
        exp_btns.addWidget(self.btn_exp_mute)

        self.exp_vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.exp_vol_slider.setRange(0, 100)
        self.exp_vol_slider.setValue(85)
        self.exp_vol_slider.setFixedWidth(80)
        self.exp_vol_slider.valueChanged.connect(self._on_volume_changed)
        exp_btns.addWidget(self.exp_vol_slider)

        # Nút Thu nhỏ ở hàng điều khiển
        btn_min_ctrl = QPushButton("Thu nhỏ")
        btn_min_ctrl.setIcon(get_svg_icon("minimize", COLORS["text_secondary"]))
        btn_min_ctrl.setStyleSheet(btn_secondary_style())
        btn_min_ctrl.clicked.connect(self._minimize_to_card)
        exp_btns.addWidget(btn_min_ctrl)

        ec_layout.addLayout(exp_btns)
        ve_layout.addWidget(exp_ctrl)

        self.stack.addWidget(self.view_expanded)

        root.addWidget(self.stack)

    def _apply_styles(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['bg_primary']};
                color: {COLORS['text_primary']};
            }}
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QTabWidget::pane {{
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                background-color: {COLORS['bg_primary']};
            }}
            QTabBar::tab {{
                background-color: {COLORS['bg_secondary']};
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']};
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 8px 18px;
                margin-right: 4px;
                font-weight: 600;
                font-size: 13px;
            }}
            QTabBar::tab:selected {{
                background-color: {COLORS['bg_card']};
                color: {COLORS['accent_primary']};
                border-bottom: 2px solid {COLORS['accent_primary']};
            }}
            QLineEdit {{
                background-color: {COLORS['bg_input']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 10px;
                color: {COLORS['text_primary']};
            }}
            QLineEdit:focus {{
                border: 1px solid {COLORS['accent_primary']};
            }}
        """)

    def _bind_shortcuts(self) -> None:
        # Phím Space: Play / Pause
        shortcut_space = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        shortcut_space.activated.connect(self._toggle_play)

        # Phím Esc: Nếu đang phóng to thì Thu nhỏ về ô. Nếu đang ở ô lưới thì đóng dialog.
        shortcut_esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        shortcut_esc.activated.connect(self._on_escape_pressed)

        # Phím F: Bật/Tắt Phóng to thu nhỏ
        shortcut_f = QShortcut(QKeySequence(Qt.Key.Key_F), self)
        shortcut_f.activated.connect(self._toggle_maximize_state)

    # ─────────────────────────────────────────────────────────────────
    # QUÉT & TẢI DANH SÁCH VIDEO (CẬP NHẬT 2 TAB)
    # ─────────────────────────────────────────────────────────────────

    def refresh_videos(self, select_path: Optional[str] = None) -> None:
        """Quét thư mục downloads_dir và xây dựng lại các thẻ video chuẩn YouTube."""
        if self._thumb_worker and self._thumb_worker.isRunning():
            self._thumb_worker.stop()
            self._thumb_worker.wait(500)

        self._raw_videos, self._dubbed_videos = scan_downloaded_videos(self.downloads_dir)

        self.tabs.setTabText(0, f"Video chưa dịch ({len(self._raw_videos)})")
        self.tabs.setTabText(1, f"Video đã dịch ({len(self._dubbed_videos)})")

        self._rebuild_grid_tab(self.grid_raw, self._raw_videos, is_dubbed=False)
        self._rebuild_grid_tab(self.grid_dubbed, self._dubbed_videos, is_dubbed=True)

        # Kích hoạt worker trích xuất thumbnail & duration ngầm
        all_paths = [v.path for v in self._raw_videos + self._dubbed_videos]
        if all_paths:
            self._thumb_worker = ThumbnailWorker(all_paths, self)
            self._thumb_worker.meta_ready.connect(self._on_thumbnail_meta_ready)
            self._thumb_worker.start()

        if select_path and os.path.isfile(select_path):
            card = self._find_card_by_path(select_path)
            if card:
                self.play_card(card)

    def _rebuild_grid_tab(self, grid_layout: QGridLayout, videos: List[VideoFileInfo], is_dubbed: bool) -> None:
        """Tạo các ô thẻ video sắp xếp dạng lưới theo số cột tự co giãn."""
        cards_list = self._cards_dubbed if is_dubbed else self._cards_raw

        # Nếu thẻ đang phát thuộc danh sách sắp bị dọn dẹp, dừng phát và tháo video_widget an toàn
        if self.active_card and (self.active_card in cards_list):
            self.stop_playback()

        # Dọn dẹp widget cũ mà không làm xoá nhầm video_widget
        while grid_layout.count():
            item = grid_layout.takeAt(0)
            w = item.widget()
            if w:
                if w == self.video_widget or (self.video_widget and w.isAncestorOf(self.video_widget)):
                    self._detach_video_widget()
                w.deleteLater()

        cards_list.clear()

        query = self.txt_search.text().strip().lower()
        matched_videos = [v for v in videos if not query or query in v.title.lower() or query in v.filename.lower()]

        if not matched_videos:
            empty_box = QWidget()
            eb_l = QVBoxLayout(empty_box)
            eb_l.setContentsMargins(40, 60, 40, 60)
            eb_l.setAlignment(Qt.AlignmentFlag.AlignCenter)

            ic = QLabel()
            ic.setPixmap(get_svg_pixmap("film" if is_dubbed else "video", size=48, color=COLORS["text_muted"]))
            ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            eb_l.addWidget(ic)

            lbl_empty = QLabel("Chưa có video nào trong danh sách này" if not query else "Không tìm thấy video phù hợp với từ khóa")
            lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_empty.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px; font-weight: 600; margin-top: 10px;")
            eb_l.addWidget(lbl_empty)

            grid_layout.addWidget(empty_box, 0, 0, 1, 3)
            return

        # Tính toán số cột lưới dựa trên chiều rộng cửa sổ hiện tại
        view_w = self.width() - 80
        cols = max(1, min(4, view_w // 360))

        for idx, vid in enumerate(matched_videos):
            card = YouTubeVideoCard(vid)
            card.play_requested.connect(self.play_card)
            card.maximize_requested.connect(self.maximize_card)
            card.stop_requested.connect(self.stop_playback)

            # Kết nối mini slider trên ô nhỏ
            card.mini_slider.sliderPressed.connect(self._on_slider_pressed)
            card.mini_slider.sliderReleased.connect(self._on_slider_released)
            card.mini_slider.sliderMoved.connect(self._on_slider_moved)
            card.btn_mini_play.clicked.connect(self._toggle_play)
            card.btn_mini_mute.clicked.connect(self._toggle_mute)

            cards_list.append(card)
            row = idx // cols
            col = idx % cols
            grid_layout.addWidget(card, row, col)

    def _find_card_by_path(self, path: str) -> Optional[YouTubeVideoCard]:
        for c in self._cards_raw + self._cards_dubbed:
            if _is_valid(c):
                try:
                    if os.path.abspath(c.video.path) == os.path.abspath(path):
                        return c
                except Exception:
                    pass
        return None

    def _on_thumbnail_meta_ready(self, vpath: str, thumb_path: str, duration_sec: float) -> None:
        """Cập nhật ảnh thumbnail và thời lượng cho thẻ tương ứng khi worker hoàn tất."""
        for card in self._cards_raw + self._cards_dubbed:
            if _is_valid(card):
                try:
                    if os.path.abspath(card.video.path) == os.path.abspath(vpath):
                        card.update_metadata(thumb_path, duration_sec)
                except (RuntimeError, Exception):
                    pass

    # ─────────────────────────────────────────────────────────────────
    # PHÁT VIDEO TRỰC TIẾP TRÊN Ô NHỎ (INLINE PLAYBACK)
    # ─────────────────────────────────────────────────────────────────

    def play_card(self, card: YouTubeVideoCard) -> None:
        """Phát trực tiếp video ngay trong ô nhỏ của thẻ được chọn."""
        if not _is_valid(card) or not os.path.isfile(card.video.path):
            return

        # Nếu đang phát đúng thẻ này, chỉ cần toggle Play / Pause
        if self.active_card == card and self.current_video_path == card.video.path:
            self._toggle_play()
            return

        # Dừng thẻ cũ trước khi chuyển sang thẻ mới
        if self.active_card and self.active_card != card:
            if _is_valid(self.active_card):
                try:
                    self.active_card.set_playing_mode(False)
                except RuntimeError:
                    pass

        self.active_card = card
        self.current_video_path = card.video.path

        # Nếu đang ở màn hình Phóng to, đưa về màn hình ô lưới trước
        if self._is_maximized_view:
            self.stack.setCurrentIndex(0)
            self._is_maximized_view = False

        # Chuyển video_widget vào đúng khung player_host_layout của thẻ
        self._attach_video_widget_to(card.player_host_widget, card.player_host_layout)
        card.set_playing_mode(True)

        self.player.setSource(QUrl.fromLocalFile(card.video.path))
        self.player.play()

    def _detach_video_widget(self) -> None:
        """Đưa video_widget về lại khung an toàn của dialog để không bao giờ bị xoá theo thẻ."""
        if _is_valid(self.video_widget) and _is_valid(self.expanded_video_frame):
            try:
                if self.video_widget.parent() != self.expanded_video_frame:
                    self.video_widget.setParent(self.expanded_video_frame)
                    self.evf_layout.addWidget(self.video_widget)
                    self.player.setVideoOutput(self.video_widget)
                self.video_widget.hide()
            except RuntimeError:
                pass

    def stop_playback(self, card: Optional[YouTubeVideoCard] = None) -> None:
        """Dừng phát và trả ô video về trạng thái thumbnail ban đầu."""
        try:
            self.player.stop()
        except Exception:
            pass

        self._detach_video_widget()

        if self.active_card and _is_valid(self.active_card):
            try:
                self.active_card.set_playing_mode(False)
            except RuntimeError:
                pass

        self.active_card = None
        self.current_video_path = ""

    def _attach_video_widget_to(self, parent_widget: QWidget, target_layout: QVBoxLayout) -> None:
        """Gắn video_widget vào container mục tiêu (giữa ô nhỏ hoặc khung phóng to)."""
        if not _is_valid(parent_widget) or not _is_valid(self.video_widget):
            return
        try:
            if self.video_widget.parent() != parent_widget:
                self.video_widget.setParent(parent_widget)
                target_layout.addWidget(self.video_widget)
                self.player.setVideoOutput(self.video_widget)
            self.video_widget.show()
        except RuntimeError:
            pass

    # ─────────────────────────────────────────────────────────────────
    # CHỨC NĂNG PHÓNG TO VÀ THU NHỎ (MAXIMIZE & MINIMIZE)
    # ─────────────────────────────────────────────────────────────────

    def maximize_card(self, card: YouTubeVideoCard) -> None:
        """Phóng to video đang xem lên màn hình lớn (Expanded Mode)."""
        if not _is_valid(card):
            return
        if self.active_card != card or self.current_video_path != card.video.path:
            self.play_card(card)

        self._is_maximized_view = True
        self.stack.setCurrentIndex(1)

        # Di chuyển video_widget vào khung phóng to
        self._attach_video_widget_to(self.expanded_video_frame, self.evf_layout)

        # Cập nhật tiêu đề trên thanh phóng to
        tag = "[ĐÃ DỊCH AI]" if card.video.is_dubbed else "[CHƯA DỊCH]"
        self.lbl_exp_title.setText(f"{tag}  {card.video.title}")

    def _minimize_to_card(self) -> None:
        """Thu nhỏ video từ màn hình phóng to quay trở lại ô nhỏ ban đầu."""
        if not self._is_maximized_view:
            return

        self._is_maximized_view = False
        self.stack.setCurrentIndex(0)

        # Gắn video_widget quay trở lại ô nhỏ của thẻ đang phát
        if self.active_card and _is_valid(self.active_card):
            try:
                self._attach_video_widget_to(self.active_card.player_host_widget, self.active_card.player_host_layout)
                self.active_card.set_playing_mode(True)
            except RuntimeError:
                self.active_card = None

    def _toggle_maximize_state(self) -> None:
        """Phím tắt F để chuyển đổi qua lại giữa Phóng to và Thu nhỏ."""
        if self._is_maximized_view:
            self._minimize_to_card()
        elif self.active_card and _is_valid(self.active_card):
            self.maximize_card(self.active_card)

    def _on_escape_pressed(self) -> None:
        """Xử lý phím Escape: nếu đang phóng to thì thu nhỏ, nếu đang ở ô lưới thì đóng."""
        if self._is_maximized_view:
            self._minimize_to_card()
        else:
            self.close()

    # ─────────────────────────────────────────────────────────────────
    # ĐIỀU KHIỂN MEDIA PLAYER VÀ CẬP NHẬT GIAO DIỆN ĐỒNG THỜI
    # ─────────────────────────────────────────────────────────────────

    def _toggle_play(self) -> None:
        try:
            if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.player.pause()
            else:
                self.player.play()
        except Exception:
            pass

    def _seek_relative(self, delta_ms: int) -> None:
        try:
            dur = self.player.duration()
            cur = self.player.position()
            target = max(0, min(dur, cur + delta_ms))
            self.player.setPosition(target)
        except Exception:
            pass

    def _on_player_position_changed(self, pos_ms: int) -> None:
        try:
            dur_ms = self.player.duration()
            time_text = f"{format_clock_ms(pos_ms)} / {format_clock_ms(dur_ms)}"

            if not self._is_seeking:
                if _is_valid(self.exp_slider):
                    try:
                        self.exp_slider.setValue(pos_ms)
                    except RuntimeError:
                        pass
                if self.active_card and _is_valid(self.active_card):
                    try:
                        if _is_valid(self.active_card.mini_slider):
                            self.active_card.mini_slider.setValue(pos_ms)
                    except RuntimeError:
                        self.active_card = None

            if _is_valid(self.lbl_exp_time):
                try:
                    self.lbl_exp_time.setText(time_text)
                except RuntimeError:
                    pass

            if self.active_card and _is_valid(self.active_card):
                try:
                    if _is_valid(self.active_card.lbl_mini_time):
                        self.active_card.lbl_mini_time.setText(time_text)
                except RuntimeError:
                    self.active_card = None
        except Exception:
            pass

    def _on_player_duration_changed(self, dur_ms: int) -> None:
        try:
            if _is_valid(self.exp_slider):
                try:
                    self.exp_slider.setRange(0, dur_ms)
                except RuntimeError:
                    pass

            if self.active_card and _is_valid(self.active_card):
                try:
                    if _is_valid(self.active_card.mini_slider):
                        self.active_card.mini_slider.setRange(0, dur_ms)
                except RuntimeError:
                    self.active_card = None

            time_text = f"{format_clock_ms(self.player.position())} / {format_clock_ms(dur_ms)}"
            if _is_valid(self.lbl_exp_time):
                try:
                    self.lbl_exp_time.setText(time_text)
                except RuntimeError:
                    pass

            if self.active_card and _is_valid(self.active_card):
                try:
                    if _is_valid(self.active_card.lbl_mini_time):
                        self.active_card.lbl_mini_time.setText(time_text)
                except RuntimeError:
                    self.active_card = None
        except Exception:
            pass

    def _on_player_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        try:
            is_playing = (state == QMediaPlayer.PlaybackState.PlayingState)
            if _is_valid(self.btn_exp_play):
                try:
                    self.btn_exp_play.setText("Tạm dừng" if is_playing else "Phát")
                    self.btn_exp_play.setIcon(get_svg_icon("pause" if is_playing else "play", "#ffffff"))
                except RuntimeError:
                    pass

            if self.active_card and _is_valid(self.active_card):
                try:
                    if _is_valid(self.active_card.btn_mini_play):
                        self.active_card.btn_mini_play.setIcon(get_svg_icon("pause" if is_playing else "play", "#ffffff", size=14))
                except RuntimeError:
                    self.active_card = None
        except Exception:
            pass

    def _on_slider_pressed(self) -> None:
        self._is_seeking = True

    def _on_slider_released(self) -> None:
        self._is_seeking = False
        val = 0
        if self._is_maximized_view and _is_valid(self.exp_slider):
            try:
                val = self.exp_slider.value()
            except RuntimeError:
                pass
        elif self.active_card and _is_valid(self.active_card):
            try:
                if _is_valid(self.active_card.mini_slider):
                    val = self.active_card.mini_slider.value()
            except RuntimeError:
                self.active_card = None
        try:
            self.player.setPosition(val)
        except Exception:
            pass

    def _on_slider_moved(self, val: int) -> None:
        try:
            self.player.setPosition(val)
        except Exception:
            pass

    def _on_volume_changed(self, val: int) -> None:
        try:
            self.audio_output.setVolume(val / 100.0)
            is_muted = (val == 0)
            icon_name = "volume-x" if is_muted else "volume"
            color = COLORS["status_error"] if is_muted else COLORS["text_secondary"]
            if _is_valid(self.btn_exp_mute):
                self.btn_exp_mute.setIcon(get_svg_icon(icon_name, color))
            if self.active_card and _is_valid(self.active_card):
                try:
                    if _is_valid(self.active_card.btn_mini_mute):
                        self.active_card.btn_mini_mute.setIcon(get_svg_icon(icon_name, color, size=14))
                except RuntimeError:
                    self.active_card = None
        except Exception:
            pass

    def _toggle_mute(self) -> None:
        try:
            if self.audio_output.isMuted():
                self.audio_output.setMuted(False)
                icon = get_svg_icon("volume", COLORS["text_secondary"])
                mini_icon = get_svg_icon("volume", COLORS["text_secondary"], size=14)
            else:
                self.audio_output.setMuted(True)
                icon = get_svg_icon("volume-x", COLORS["status_error"])
                mini_icon = get_svg_icon("volume-x", COLORS["status_error"], size=14)

            if _is_valid(self.btn_exp_mute):
                self.btn_exp_mute.setIcon(icon)
            if self.active_card and _is_valid(self.active_card):
                try:
                    if _is_valid(self.active_card.btn_mini_mute):
                        self.active_card.btn_mini_mute.setIcon(mini_icon)
                except RuntimeError:
                    self.active_card = None
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────
    # SỰ KIỆN CO GIÃN CỬA SỔ & TÌM KIẾM
    # ─────────────────────────────────────────────────────────────────

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if not self._is_maximized_view:
            self._relayout_grid(self.grid_raw, self._cards_raw)
            self._relayout_grid(self.grid_dubbed, self._cards_dubbed)

    def _relayout_grid(self, grid_layout: QGridLayout, cards: List[YouTubeVideoCard]) -> None:
        alive_cards = [c for c in cards if _is_valid(c) and c.isVisible()]
        if not alive_cards:
            return
        view_w = self.width() - 80
        cols = max(1, min(4, view_w // 360))

        for c in alive_cards:
            grid_layout.removeWidget(c)

        for idx, card in enumerate(alive_cards):
            row = idx // cols
            col = idx % cols
            grid_layout.addWidget(card, row, col)

    def _on_search_changed(self, text: str) -> None:
        """Lọc thẻ video theo từ khóa tìm kiếm mà không cần tạo lại widget để đảm bảo độ mượt."""
        query = text.strip().lower()
        for is_dubbed, cards, grid in [
            (False, self._cards_raw, self.grid_raw),
            (True, self._cards_dubbed, self.grid_dubbed),
        ]:
            for c in cards:
                if not _is_valid(c):
                    continue
                match = not query or (query in c.video.title.lower() or query in c.video.filename.lower())
                c.setVisible(match)

            # Nếu thẻ đang phát không khớp từ khóa, dừng phát an toàn
            if self.active_card and self.active_card in cards and not self.active_card.isVisible():
                self.stop_playback()

            self._relayout_grid(grid, cards)

    def _on_tab_changed(self, index: int) -> None:
        pass

    def _open_downloads_folder(self) -> None:
        if os.path.isdir(self.downloads_dir):
            try:
                os.startfile(self.downloads_dir)
            except Exception:
                pass

    def closeEvent(self, event) -> None:
        self.stop_playback()
        if self._thumb_worker and self._thumb_worker.isRunning():
            self._thumb_worker.stop()
            self._thumb_worker.wait(300)
        event.accept()
