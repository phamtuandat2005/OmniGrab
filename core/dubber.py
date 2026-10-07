"""
core/dubber.py - Module Lồng tiếng / Thuyết minh AI Tiếng Việt.

Quy trình xử lý:
  1. Tách âm thanh gốc từ video (FFmpeg).
  2. Bóc tách mốc thời gian từng câu bằng faster-whisper + VAD.
  3. Dịch sang Tiếng Việt bằng GoogleTranslator (deep-translator).
  4. Tổng hợp giọng đọc tiếng Việt bằng Edge-TTS với Dynamic Pacing.
  5. Ghép trục thời gian: nối audio câu + khoảng lặng.
  6. Ghép vào video gốc với Sidechain Ducking (FFmpeg).

Không yêu cầu API Key. Hoạt động hoàn toàn offline / miễn phí.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Callable, List, Optional

# Vá tương thích PyAV 19+ (loại bỏ tham số metadata_errors mà faster-whisper cũ gọi)
try:
    import av
    _orig_av_open = av.open

    def _safe_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)

    av.open = _safe_av_open
except Exception:
    pass


@dataclass
class DubSegment:
    """Một đoạn thoại đã bóc tách từ STT."""
    start: float           # Thời điểm bắt đầu (giây)
    end: float             # Thời điểm kết thúc (giây)
    original_text: str     # Văn bản gốc (Trung/Anh)
    vn_text: str = ""      # Văn bản đã dịch sang Tiếng Việt
    tts_path: str = ""     # Đường dẫn file âm thanh TTS tạm
    rate_str: str = "+0%"  # Tỷ lệ tốc độ cho Edge-TTS

    @property
    def target_duration(self) -> float:
        """Thời lượng gốc của đoạn thoại (giây)."""
        return max(0.1, self.end - self.start)


@dataclass
class DubConfig:
    """Cấu hình cho một phiên lồng tiếng."""
    source_lang: str = "zh"                         # Ngôn ngữ gốc: 'zh' hoặc 'en'
    voice: str = "vi-VN-HoaiMyNeural"               # Giọng đọc Edge-TTS
    bg_volume: float = 0.12                          # Âm lượng nhạc nền gốc (0.0 - 1.0)
    whisper_model: str = "base"                      # Model Whisper: 'tiny', 'base', 'small'
    ffmpeg_path: str = ""                            # Đường dẫn thư mục ffmpeg
    log_callback: Optional[Callable[[str], None]] = field(default=None, repr=False)
    progress_callback: Optional[Callable[[int, int], None]] = field(default=None, repr=False)


class VideoDubber:
    """
    Lõi xử lý lồng tiếng AI Tiếng Việt theo quy trình tuần tự.

    Sử dụng:
        dubber = VideoDubber(config)
        output_path = dubber.process_video(input_mp4)
    """

    # Số từ tiếng Việt đọc tự nhiên mỗi giây
    _VI_WORDS_PER_SEC = 3.0
    # Tốc độ tối đa cho phép tăng (%)
    _MAX_RATE_PCT = 25

    def __init__(self, config: DubConfig) -> None:
        self._cfg = config
        self._temp_dir: str = ""

    # ─────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────────────────

    def process_video(self, input_video: str) -> str:
        """
        Xử lý toàn bộ quy trình lồng tiếng cho một video MP4.

        Args:
            input_video: Đường dẫn tuyệt đối tới file MP4 đầu vào.

        Returns:
            Đường dẫn tới file MP4 thành phẩm đã lồng tiếng.

        Raises:
            RuntimeError: Nếu bất kỳ bước nào thất bại.
        """
        self._log("🎬 Bắt đầu quy trình lồng tiếng AI Tiếng Việt...")
        self._temp_dir = tempfile.mkdtemp(prefix="omnigrab_dub_")

        try:
            # Bước 1: Tách âm thanh
            self._log("[LỒNG TIẾNG] Đang lọc giọng nói và bóc tách mốc thời gian (VAD)...")
            wav_path = self._extract_audio(input_video)

            # Bước 2: STT + bóc tách mốc thời gian
            segments = self._transcribe(wav_path)
            if not segments:
                raise RuntimeError("Không nhận ra giọng nói nào trong video. Bỏ qua lồng tiếng.")

            self._log(f"[LỒNG TIẾNG] Nhận diện được {len(segments)} đoạn thoại. Đang dịch sang Tiếng Việt...")

            # Bước 3: Dịch
            self._translate_segments(segments)

            # Bước 4 + 5: TTS với Dynamic Pacing + Ghép trục thời gian
            dub_audio = self._build_dubbed_audio(segments, input_video)

            # Bước 6: Ghép vào video với Ducking
            self._log("[LỒNG TIẾNG] Đang ghép âm thanh và xuất video thành phẩm...")
            output_path = self._merge_to_video(input_video, dub_audio)

            self._log(f"✅ Hoàn tất lồng tiếng! File thành phẩm: {os.path.basename(output_path)}")
            return output_path

        except Exception as exc:
            self._log(f"❌ Lỗi lồng tiếng: {exc}")
            raise
        finally:
            self._cleanup()

    # ─────────────────────────────────────────────────────────────────
    # BƯỚC 1: Tách âm thanh
    # ─────────────────────────────────────────────────────────────────

    def _extract_audio(self, video_path: str) -> str:
        """Dùng FFmpeg tách audio thô 16kHz mono WAV từ video."""
        wav_out = os.path.join(self._temp_dir, "source_audio.wav")
        ffmpeg = self._get_ffmpeg_exe()
        cmd = [
            ffmpeg, "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            wav_out,
        ]
        self._run_cmd(cmd, "Tách âm thanh từ video")
        return wav_out

    # ─────────────────────────────────────────────────────────────────
    # BƯỚC 2: STT với faster-whisper + VAD
    # ─────────────────────────────────────────────────────────────────

    def _transcribe(self, wav_path: str) -> List[DubSegment]:
        """Dùng faster-whisper nhận diện giọng nói và trả về danh sách đoạn."""
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except ImportError:
            raise RuntimeError(
                "Thư viện 'faster-whisper' chưa được cài đặt.\n"
                "Hãy chạy: pip install faster-whisper"
            )

        model = WhisperModel(
            self._cfg.whisper_model,
            device="cpu",
            compute_type="int8",
        )

        segments_raw, _ = model.transcribe(
            wav_path,
            language=self._cfg.source_lang,
            vad_filter=True,              # Bộ lọc VAD khử tiếng ồn
            condition_on_previous_text=False,
        )

        result: List[DubSegment] = []
        for seg in segments_raw:
            text = seg.text.strip()
            if text:
                result.append(DubSegment(
                    start=seg.start,
                    end=seg.end,
                    original_text=text,
                ))
        return result

    # ─────────────────────────────────────────────────────────────────
    # BƯỚC 3: Dịch sang Tiếng Việt
    # ─────────────────────────────────────────────────────────────────

    def _translate_segments(self, segments: List[DubSegment]) -> None:
        """Dịch từng đoạn thoại sang Tiếng Việt bằng GoogleTranslator."""
        try:
            from deep_translator import GoogleTranslator  # type: ignore
        except ImportError:
            raise RuntimeError(
                "Thư viện 'deep-translator' chưa được cài đặt.\n"
                "Hãy chạy: pip install deep-translator"
            )

        translator = GoogleTranslator(
            source=self._cfg.source_lang,
            target="vi",
        )

        for i, seg in enumerate(segments):
            try:
                translated = translator.translate(seg.original_text)
                seg.vn_text = translated or seg.original_text
            except Exception as e:
                self._log(f"  ⚠ Lỗi dịch câu {i + 1}: {e} — giữ nguyên bản gốc.")
                seg.vn_text = seg.original_text

    # ─────────────────────────────────────────────────────────────────
    # BƯỚC 4: Dynamic Pacing + TTS Edge-TTS
    # ─────────────────────────────────────────────────────────────────

    def _compute_rate(self, seg: DubSegment) -> str:
        """
        Thuật toán Dynamic Pacing từ VideoLingo.

        Tính tỷ lệ tăng tốc độ để giọng Việt kết thúc đúng nhịp cảnh.
        """
        words = len(seg.vn_text.split())
        estimated = words / self._VI_WORDS_PER_SEC
        if estimated > seg.target_duration and seg.target_duration > 0:
            pct = int(((estimated - seg.target_duration) / seg.target_duration) * 100)
            pct = min(pct, self._MAX_RATE_PCT)
            return f"+{pct}%"
        return "+0%"

    def _run_tts_sync(self, text: str, voice: str, rate: str, out_path: str) -> None:
        """Chạy Edge-TTS đồng bộ (dùng asyncio.run())."""
        try:
            import edge_tts  # type: ignore
        except ImportError:
            raise RuntimeError(
                "Thư viện 'edge-tts' chưa được cài đặt.\n"
                "Hãy chạy: pip install edge-tts"
            )

        async def _do_tts() -> None:
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            await communicate.save(out_path)

        asyncio.run(_do_tts())

    # ─────────────────────────────────────────────────────────────────
    # BƯỚC 5: Ghép trục thời gian (Timeline Audio Assembler)
    # ─────────────────────────────────────────────────────────────────

    def _get_video_duration(self, video_path: str) -> float:
        """Lấy thời lượng video bằng ffprobe."""
        ffprobe = self._get_ffprobe_exe()
        cmd = [
            ffprobe, "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            video_path,
        ]
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
            import json
            info = json.loads(out)
            return float(info["format"]["duration"])
        except Exception:
            return 0.0

    def _build_dubbed_audio(self, segments: List[DubSegment], input_video: str) -> str:
        """
        Tổng hợp TTS từng câu, ghép vào đúng mốc thời gian gốc.
        Khoảng lặng (im lặng) được lấp đầy bằng anullsrc.
        Xuất file MP3 cuối cùng dài đúng bằng video gốc.
        """
        total = len(segments)
        ffmpeg = self._get_ffmpeg_exe()
        video_dur = self._get_video_duration(input_video)

        # Danh sách (path, start, duration) cho từng đoạn TTS
        tts_pieces: List[tuple[str, float, float]] = []

        for i, seg in enumerate(segments):
            self._log(
                f"[LỒNG TIẾNG] Đang dịch và ép tốc độ câu {i + 1}/{total}: "
                f'"{seg.vn_text[:40]}..."' if len(seg.vn_text) > 40 else
                f"[LỒNG TIẾNG] Đang dịch và ép tốc độ câu {i + 1}/{total}..."
            )
            if self._cfg.progress_callback:
                self._cfg.progress_callback(i + 1, total)

            seg.rate_str = self._compute_rate(seg)
            tts_out = os.path.join(self._temp_dir, f"seg_{i:04d}.mp3")

            try:
                self._run_tts_sync(seg.vn_text, self._cfg.voice, seg.rate_str, tts_out)
                if os.path.isfile(tts_out) and os.path.getsize(tts_out) > 0:
                    tts_pieces.append((tts_out, seg.start, seg.end - seg.start))
                    seg.tts_path = tts_out
            except Exception as e:
                self._log(f"  ⚠ Bỏ qua câu {i + 1} do lỗi TTS: {e}")

        # Xây dựng filter_complex để ghép các đoạn TTS vào đúng vị trí thời gian
        # Dùng adelay để shift từng đoạn đến đúng start time
        dub_out = os.path.join(self._temp_dir, "dub_voice.mp3")

        if not tts_pieces:
            # Không có đoạn TTS nào thành công → tạo audio câm
            silence_dur = max(video_dur, 10.0)
            cmd = [
                ffmpeg, "-y",
                "-f", "lavfi",
                "-i", f"anullsrc=r=44100:cl=stereo:duration={silence_dur:.2f}",
                "-c:a", "libmp3lame", "-q:a", "5",
                dub_out,
            ]
            self._run_cmd(cmd, "Tạo audio câm")
            return dub_out

        # Xây dựng filter_complex với adelay cho từng đoạn
        inputs: List[str] = []
        filter_parts: List[str] = []

        # Thêm source silence = toàn bộ duration video
        safe_dur = max(video_dur, 10.0)
        inputs += ["-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:duration={safe_dur:.2f}"]
        filter_parts.append(f"[0:a]volume=0[silence]")

        mix_inputs = ["[silence]"]
        for idx, (path, start_sec, _dur) in enumerate(tts_pieces):
            inputs += ["-i", path]
            delay_ms = int(start_sec * 1000)
            label = f"[v{idx}]"
            filter_parts.append(
                f"[{idx + 1}:a]adelay={delay_ms}|{delay_ms}[v{idx}]"
            )
            mix_inputs.append(label)

        n_inputs = len(mix_inputs)
        filter_parts.append(
            f"{''.join(mix_inputs)}amix=inputs={n_inputs}:duration=first:dropout_transition=0[out]"
        )

        filter_complex = ";".join(filter_parts)

        cmd = [
            ffmpeg, "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-c:a", "libmp3lame", "-q:a", "3",
            dub_out,
        ]
        self._run_cmd(cmd, "Ghép trục thời gian âm thanh")
        return dub_out

    # ─────────────────────────────────────────────────────────────────
    # BƯỚC 6: Ghép vào video + Sidechain Ducking
    # ─────────────────────────────────────────────────────────────────

    def _merge_to_video(self, input_video: str, dub_audio: str) -> str:
        """
        Ghép audio thuyết minh vào video gốc với Sidechain Ducking.

        - Nhạc nền gốc giảm xuống bg_volume% (mặc định 12%).
        - Tiếng thuyết minh ở mức 100%.
        - Không encode lại video: -c:v copy (siêu nhanh).
        """
        base, ext = os.path.splitext(input_video)
        output_path = f"{base}_dubbed_vi{ext}"

        ffmpeg = self._get_ffmpeg_exe()
        bg_vol = self._cfg.bg_volume

        # filter_complex: trộn nhạc nền gốc (giảm âm) + tiếng thuyết minh
        filter_complex = (
            f"[0:a]volume={bg_vol:.2f}[bg];"
            f"[1:a]volume=1.0[voice];"
            f"[bg][voice]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )

        cmd = [
            ffmpeg, "-y",
            "-i", input_video,
            "-i", dub_audio,
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            output_path,
        ]
        self._run_cmd(cmd, "Ghép video + Audio Ducking")
        return output_path

    # ─────────────────────────────────────────────────────────────────
    # TIỆN ÍCH NỘI BỘ
    # ─────────────────────────────────────────────────────────────────

    def _get_ffmpeg_exe(self) -> str:
        """Trả về đường dẫn tuyệt đối tới ffmpeg."""
        if self._cfg.ffmpeg_path:
            candidate = os.path.join(self._cfg.ffmpeg_path, "ffmpeg.exe")
            if os.path.isfile(candidate):
                return candidate
            candidate2 = os.path.join(self._cfg.ffmpeg_path, "ffmpeg")
            if os.path.isfile(candidate2):
                return candidate2
        # Tìm trong PATH
        found = shutil.which("ffmpeg")
        if found:
            return found
        # Thư mục project
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for name in ("ffmpeg.exe", "ffmpeg"):
            candidate = os.path.join(project_dir, name)
            if os.path.isfile(candidate):
                return candidate
        raise RuntimeError(
            "Không tìm thấy ffmpeg! Hãy đảm bảo ffmpeg.exe nằm cùng thư mục với ứng dụng."
        )

    def _get_ffprobe_exe(self) -> str:
        """Trả về đường dẫn tuyệt đối tới ffprobe."""
        if self._cfg.ffmpeg_path:
            candidate = os.path.join(self._cfg.ffmpeg_path, "ffprobe.exe")
            if os.path.isfile(candidate):
                return candidate
        found = shutil.which("ffprobe")
        if found:
            return found
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for name in ("ffprobe.exe", "ffprobe"):
            candidate = os.path.join(project_dir, name)
            if os.path.isfile(candidate):
                return candidate
        # Fallback dùng ffmpeg để probe
        return self._get_ffmpeg_exe().replace("ffmpeg", "ffprobe")

    def _run_cmd(self, cmd: List[str], step_name: str) -> None:
        """Chạy lệnh subprocess và xử lý lỗi."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                check=True,
                timeout=300,
            )
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            raise RuntimeError(f"FFmpeg lỗi tại bước '{step_name}':\n{stderr[-400:]}")
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Bước '{step_name}' bị timeout sau 5 phút.")

    def _cleanup(self) -> None:
        """Xóa toàn bộ file tạm."""
        if self._temp_dir and os.path.isdir(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir, ignore_errors=True)
            except Exception:
                pass
        self._temp_dir = ""

    def _log(self, msg: str) -> None:
        """Gửi log qua callback (nếu có)."""
        if self._cfg.log_callback:
            self._cfg.log_callback(msg)


# ─────────────────────────────────────────────────────────────────────
# KIỂM TRA PHỤ THUỘC
# ─────────────────────────────────────────────────────────────────────

def check_dub_dependencies() -> dict[str, bool]:
    """
    Kiểm tra xem các thư viện lồng tiếng đã được cài chưa.

    Returns:
        Dict {tên_lib: bool} — True = đã cài, False = chưa cài.
    """
    result: dict[str, bool] = {}
    for lib in ("faster_whisper", "edge_tts", "deep_translator"):
        try:
            __import__(lib)
            result[lib] = True
        except ImportError:
            result[lib] = False
    return result
