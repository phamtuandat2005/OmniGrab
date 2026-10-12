"""
core/dubbing_engine.py — Module hòa âm FFmpeg chuẩn phòng thu cho OmniGrab.

Xử lý trộn âm thanh giữa video gốc và giọng đọc tiếng Việt:
- Giảm âm lượng video gốc xuống mức nền êm dịu (8% - 12%, mặc định 10%) hoặc tắt hẳn (0%).
- Kích âm (boost) giọng đọc tiếng Việt lên 220% kèm bộ lọc chuẩn hóa loudnorm EBU R128.
- Áp dụng bộ lọc amix với cờ normalize=0 để tránh FFmpeg tự động giảm một nửa âm lượng mỗi luồng.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional


def _find_ffmpeg_bin() -> str:
    """Tìm đường dẫn binary ffmpeg an toàn."""
    try:
        from core.dubber import _find_ffmpeg_bin as _dubber_find
        f = _dubber_find()
        if f and os.path.isfile(f):
            return f
    except Exception:
        pass

    # Kiểm tra file ffmpeg.exe cạnh app hoặc trong PATH
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_ffmpeg = os.path.join(base_dir, "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    if os.path.isfile(local_ffmpeg):
        return local_ffmpeg
    return "ffmpeg"


def mix_dubbed_audio(
    video_input_path: str,
    voice_audio_path: str,
    output_path: str,
    bg_volume: float = 0.10,
    voice_volume: float = 2.2,
    mute_original: bool = False,
    ffmpeg_bin: Optional[str] = None,
) -> str:
    """
    Trộn video gốc với giọng đọc tiếng Việt theo tỷ lệ âm lượng chuẩn phòng thu.

    Args:
        video_input_path: Đường dẫn video MP4 gốc.
        voice_audio_path: Đường dẫn file WAV/MP3 giọng đọc tiếng Việt.
        output_path: Đường dẫn video thành phẩm xuất ra.
        bg_volume: Âm lượng video gốc (mặc định 0.10 = 10%).
        voice_volume: Kích âm giọng đọc (mặc định 2.2 = 220%).
        mute_original: Tắt hoàn toàn âm thanh gốc nếu True (bg_volume = 0.0).
        ffmpeg_bin: Đường dẫn binary ffmpeg tùy chỉnh (tự động phát hiện nếu None).

    Returns:
        Đường dẫn file video thành phẩm đã trộn âm thanh.
    """
    if not os.path.isfile(video_input_path):
        raise FileNotFoundError(f"Không tìm thấy video gốc: {video_input_path}")
    if not os.path.isfile(voice_audio_path):
        raise FileNotFoundError(f"Không tìm thấy file giọng đọc: {voice_audio_path}")

    if not ffmpeg_bin:
        ffmpeg_bin = _find_ffmpeg_bin()

    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    # Đảm bảo thư mục đích tồn tại
    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    if mute_original or bg_volume <= 0.0:
        # Nếu tắt hẳn tiếng gốc: chỉ lấy hình ảnh từ [0:v] và âm thanh thuyết minh từ [1:a]
        filter_complex = f"[1:a]volume={voice_volume:.2f},loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
        cmd = [
            ffmpeg_bin, "-y",
            "-i", video_input_path,
            "-i", voice_audio_path,
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            output_path,
        ]
    else:
        # Giảm sâu tiếng gốc xuống mức nền, kích âm giọng thuyết minh lên 220% kèm loudnorm
        # Thêm normalize=0 để FFmpeg không chia đôi âm lượng của mỗi luồng
        filter_complex = (
            f"[0:a]volume={bg_volume:.2f}[bg];"
            f"[1:a]volume={voice_volume:.2f},loudnorm=I=-14:TP=-1.5:LRA=11[voice];"
            f"[bg][voice]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
        )
        cmd = [
            ffmpeg_bin, "-y",
            "-i", video_input_path,
            "-i", voice_audio_path,
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            output_path,
        ]

    result = subprocess.run(cmd, capture_output=True, text=True, errors="replace", **kwargs)
    if result.returncode != 0:
        # Dự phòng: Nếu video gốc là video câm (không có luồng audio [0:a]),
        # bộ lọc [0:a] sẽ báo lỗi. Tự động chuyển sang chế độ ghép chỉ có giọng đọc.
        if "[0:a]" in filter_complex:
            fallback_filter = f"[1:a]volume={voice_volume:.2f},loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
            cmd_fallback = [
                ffmpeg_bin, "-y",
                "-i", video_input_path,
                "-i", voice_audio_path,
                "-filter_complex", fallback_filter,
                "-map", "0:v",
                "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                output_path,
            ]
            res_fb = subprocess.run(cmd_fallback, capture_output=True, text=True, errors="replace", **kwargs)
            if res_fb.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
                return output_path

        raise RuntimeError(f"Lỗi FFmpeg khi trộn âm thanh: {result.stderr.strip() if result.stderr else 'Unknown error'}")

    return output_path
