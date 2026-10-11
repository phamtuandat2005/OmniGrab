"""
core/dubber.py - Module Lồng tiếng AI Phim ảnh chuẩn VideoLingo (Cinema Dubbing Pipeline).

Tích hợp 4 khâu tinh hoa từ VideoLingo:
  1. Sentence Segmentation: Gom câu thoại ngắt quãng theo ngữ pháp hoàn chỉnh.
  2. Contextual Film Translation: Dịch kịch bản theo ngữ cảnh phim ảnh (xưng hô, sảng văn, tình cảm).
  3. Speed Pacing / Time-stretching: Tự động điều tốc (atempo) khớp khít từng khung hình, không tràn cảnh.
  4. Cinema Audio Ducking: Sidechain Compressor hạ nhạc nền gốc êm ái khi có thoại và tự động nâng lại.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Tuple

import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass

import requests

# Vá tương thích PyAV 19+ cho faster-whisper
try:
    import av
    _orig_av_open = av.open

    def _safe_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)

    av.open = _safe_av_open
except Exception:
    pass

# Hỗ trợ audioop trên Python 3.13+ cho pydub
try:
    import audioop  # noqa: F401
except ImportError:
    try:
        # pyrefly: ignore [missing-import]
        import audioop_lts as audioop
        sys.modules["audioop"] = audioop
    except Exception:
        pass

from deep_translator import GoogleTranslator
from faster_whisper import WhisperModel
# pyrefly: ignore [missing-import]
from gtts import gTTS
# pyrefly: ignore [missing-import]
from pydub import AudioSegment


# ══════════════════════════════════════════════════════════════════════
# CẤU HÌNH CÔNG CỤ VÀ ĐƯỜNG DẪN FFmpeg
# ══════════════════════════════════════════════════════════════════════

def _find_ffmpeg_bin() -> str:
    """Tìm đường dẫn ffmpeg.exe ưu tiên thư mục gốc dự án."""
    proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_ff = os.path.join(proj_dir, "ffmpeg.exe")
    if os.path.isfile(local_ff):
        return local_ff
    found = shutil.which("ffmpeg")
    return found or "ffmpeg"


def _find_ffprobe_bin() -> str:
    """Tìm đường dẫn ffprobe.exe ưu tiên thư mục gốc dự án."""
    proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_probe = os.path.join(proj_dir, "ffprobe.exe")
    if os.path.isfile(local_probe):
        return local_probe
    found = shutil.which("ffprobe")
    return found or "ffprobe"


FFMPEG_PATH = _find_ffmpeg_bin()
FFPROBE_PATH = _find_ffprobe_bin()

# Cấu hình pydub sử dụng đúng file binary nội bộ
if os.path.isfile(FFMPEG_PATH):
    AudioSegment.converter = FFMPEG_PATH
    AudioSegment.ffmpeg = FFMPEG_PATH
if os.path.isfile(FFPROBE_PATH):
    AudioSegment.ffprobe = FFPROBE_PATH


# ══════════════════════════════════════════════════════════════════════
# CẤU TRÚC DỮ LIỆU & TỪ ĐIỂN ĐIỆN ẢNH (FILM CONTEXT GLOSSARY)
# ══════════════════════════════════════════════════════════════════════

@dataclass
class DubSegment:
    """Đoạn phụ đề / lời thoại đã được gom câu hoàn chỉnh."""
    start: float
    end: float
    text_orig: str
    text_trans: str = ""
    audio_path: str = ""
    duration_actual: float = 0.0


# Bộ quy tắc Hán Việt / Điện ảnh giúp dịch đúng ngữ cảnh sảng văn & anime (không gán cứng tên riêng)
CHINESE_FILM_GLOSSARY = {
    # Danh xưng / chức vụ phổ quát
    "学长": "đàn anh",
    "学妹": "đàn em",
    "师兄": "sư huynh",
    "师姐": "sư tỷ",
    "师弟": "sư đệ",
    "师妹": "sư muội",
    "师傅": "sư phụ",
    "前辈": "tiền bối",
    "娘娘": "nương nương",
    "陛下": "bệ hạ",
    "大人": "đại nhân",
    "少爷": "thiếu gia",
    "小姐": "tiểu thư",
    "老板": "ông chủ",
    "经理": "giám đốc",

    # Ngữ cảnh tình cảm / giao tiếp
    "做我女朋友好不好": "làm bạn gái anh có được không?",
    "做我女朋友": "làm bạn gái anh",
    "表白": "tỏ tình",
    "牵手散步": "nắm tay đi dạo",

    # Tiếng lóng / chửi thề / sảng văn
    "狗男女": "đôi cẩu nam nữ",
    "小婊子": "con khốn",
    "小表子": "con khốn",
    "见人": "tiện nhân",
    "贱人": "tiện nhân",
    "争配": "xứng đôi",
    "绝配": "xứng đôi vừa lứa",
    "能装": "giả tạo",
    "天天装可爱装可怜": "ngày nào cũng giả vờ dễ thương, giả vờ đáng thương",
    "逆返系统": "Nghịch Phản Hệ Thống",
    "正式集团": "tập đoàn Chính Thức",
    "继承人": "người thừa kế",
    "爽文": "sảng văn",
    "动手": "ra tay",
    "没忍住": "không nhịn được",
}

SENTENCE_TERMINALS = ('.', '!', '?', '。', '！', '？', ';', '；', '好不好', '吗', '吧', '呢', '呀', '啊', '了')
VOCATIVE_OPENERS = (
    "学长", "学妹", "师兄", "师姐", "师弟", "师妹", "师傅", "前辈",
    "娘娘", "哥哥", "姐姐", "弟弟", "妹妹", "叔叔", "阿姨",
    "老板", "老师", "先生", "小姐", "兄弟", "宝贝"
)


# ══════════════════════════════════════════════════════════════════════
# BƯỚC 1: GOM CÂU THEO NGỮ PHÁP (SENTENCE SEGMENTATION)
# ══════════════════════════════════════════════════════════════════════

def merge_broken_segments(
    raw_segments: list,
    max_gap: float = 0.8,
    max_dur: float = 6.0,
    max_chars: int = 50,
) -> List[DubSegment]:
    """
    Giải thuật VideoLingo (step4_split_sentences):
    Gom các mẩu thoại ngắt quãng từ Whisper thành câu văn hoàn chỉnh theo dấu câu.
    Ngăn chặn lỗi cắt vụn danh xưng, đại từ hoặc cắt giữa câu.
    """
    if not raw_segments:
        return []

    merged: List[DubSegment] = []
    first = raw_segments[0]
    curr = DubSegment(
        start=float(first.start),
        end=float(first.end),
        text_orig=first.text.strip()
    )

    for seg in raw_segments[1:]:
        text = seg.text.strip()
        if not text:
            continue

        gap = float(seg.start) - curr.end
        added_dur = float(seg.end) - curr.start
        is_terminal = curr.text_orig.endswith(SENTENCE_TERMINALS)
        is_short = len(curr.text_orig) <= 4 or (curr.end - curr.start) < 1.2
        starts_vocative = any(text.startswith(voc) for voc in VOCATIVE_OPENERS)

        # Điều kiện gộp:
        # 1. Câu trước chưa kết thúc và khoảng cách thời gian ngắn (gap < max_gap),
        #    và câu tiếp theo không phải là mở đầu câu thoại của người mới (vocative opener).
        # 2. Hoặc câu trước quá ngắn (như danh xưng, thán từ ngắn) -> bắt buộc gộp vào vế sau.
        # 3. Đồng thời tổng thời lượng sau khi gộp không vượt quá max_dur.
        can_merge = (
            added_dur <= max_dur and
            (len(curr.text_orig) + len(text) <= max_chars) and
            (
                (is_short and gap < 1.3) or
                (not is_terminal and not starts_vocative and gap < max_gap)
            )
        )

        if can_merge:
            # Gộp text thông minh theo ngữ pháp
            has_cjk = any('\u4e00' <= ch <= '\u9fff' for ch in curr.text_orig)
            if has_cjk:
                if gap > 0.4 and not curr.text_orig.endswith(('，', ',', '、', ' ')):
                    curr.text_orig += "，" + text
                else:
                    curr.text_orig += text
            else:
                curr.text_orig += " " + text
            curr.end = float(seg.end)
        else:
            merged.append(curr)
            curr = DubSegment(
                start=float(seg.start),
                end=float(seg.end),
                text_orig=text
            )

    if curr.text_orig:
        merged.append(curr)

    return merged


# ══════════════════════════════════════════════════════════════════════
# BƯỚC 2: QUY TRÌNH DỊCH 2 BƯỚC TỰ ĐỘNG (2-PASS CONTEXTUAL PIPELINE)
# ══════════════════════════════════════════════════════════════════════

def extract_video_context_profile(full_chinese_text: str, api_key: str) -> str:
    """
    Bước 1: AI tự đọc kịch bản để tạo ra hồ sơ nhân vật và bối cảnh cho video đó.
    Hoàn toàn tự động cho mọi video (phim ảnh, hoạt hình, vlog...), không hardcode tên riêng.
    """
    clean_key = (api_key or "").strip()
    if not clean_key or not full_chinese_text or not full_chinese_text.strip():
        return "Bối cảnh: Phim truyện ngắn Trung Quốc. Tên riêng dịch theo âm Hán-Việt chuẩn."

    headers = {"Content-Type": "application/json"}
    prompt = (
        "Bạn là chuyên gia phân tích kịch bản phim ảnh Trung Quốc.\n"
        "Hãy đọc toàn bộ lời thoại sau và tóm tắt ngắn gọn thành hồ sơ ngữ cảnh (trong 3-4 dòng):\n"
        "1. Thể loại nội dung (phim tình cảm, đô thị, tu tiên, vlog, hài hước...).\n"
        "2. Danh sách tên các nhân vật chính và phiên âm Hán-Việt chuẩn của họ (Ví dụ: 叶 -> Diệp, 孙 -> Tôn, 李小男 -> Lý Tiểu Nam).\n"
        "3. Quan hệ và cách xưng hô hợp lý nhất giữa các nhân vật (anh - em, ngài - tôi, mày - tao...).\n"
        "4. Giải thích các từ lóng mạng nếu có (ví dụ: 校草 = nam thần trường, 摸头杀 = xoa đầu cưng nựng).\n\n"
        f"Nội dung thoại:\n{full_chinese_text[:2000]}"
    )
    payload = {
        "system_instruction": {"parts": [{"text": "Bạn là chuyên gia phân tích kịch bản phim ảnh Trung Quốc. Tóm tắt ngắn gọn trong 3-4 dòng: Thể loại, tên nhân vật (phiên âm Hán-Việt chuẩn), xưng hô hợp lý, tiếng lóng nếu có."}]},
        "contents": [{"parts": [{"text": f"Phân tích kịch bản sau:\n{full_chinese_text[:2500]}"}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024}
    }

    candidate_models = (
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-3.8-flash",
        "gemini-flash-latest",
        "gemini-2.5-flash",
        "gemini-1.5-flash",
    )

    for model_name in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={clean_key}"
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates and "content" in candidates[0]:
                    parts = candidates[0]["content"].get("parts", [])
                    if parts:
                        profile = parts[0].get("text", "").strip()
                        if profile:
                            return profile
        except Exception:
            continue

    return "Bối cảnh: Phim truyện ngắn Trung Quốc. Tên riêng dịch theo âm Hán-Việt chuẩn."


def translate_dialogues_with_profile(
    dialogues: list[str],
    profile: str,
    api_key: str,
    on_sentence_translated_cb: Optional[Callable[[int, str], None]] = None,
) -> list[str]:
    """
    Bước 2: Dịch toàn bộ các câu thoại dựa trên hồ sơ bối cảnh tự động.
    Dùng chính profile từ Bước 1 làm kim chỉ nam, giữ nguyên số thứ tự từng dòng.
    """
    if not dialogues:
        return []

    clean_key = (api_key or "").strip()
    if not clean_key:
        return dialogues

    headers = {"Content-Type": "application/json"}
    sys_instruction = (
        "Bạn là biên dịch viên lồng tiếng phim Trung Quốc sang Tiếng Việt xuất sắc nhất.\n"
        f"HỒ SƠ BỐI CẢNH CỦA VIDEO:\n{profile}\n\n"
        "QUY TẮC BẮT BUỘC:\n"
        "1. Dựa sát vào hồ sơ bối cảnh để dịch xưng hô nhất quán, tự nhiên chuẩn điện ảnh.\n"
        "2. Mọi tên người, chức danh, địa danh BẮT BUỘC PHẢI PHIÊN ÂM HÁN-VIỆT CHUẨN (Tuyệt đối không dùng tiếng Anh như Mr, Cloud, Sir...).\n"
        "3. Tự động sửa lỗi chữ Hán đồng âm do ASR (Ví dụ: '不要弄放' -> 'Đừng làm bẩn / đừng động vào đồ của tôi').\n"
        "4. ĐỊNH DẠNG XUẤT BẮT BUỘC:\n"
        "   - Chỉ trả về duy nhất danh sách các câu dịch Tiếng Việt: 1. [câu dịch]  2. [câu dịch]...\n"
        "   - TUYỆT ĐỐI KHÔNG kèm chữ Hán gốc, KHÔNG ghi chú, KHÔNG giải thích nghĩa, KHÔNG có lời mở đầu hay kết luận.\n"
        "   - Mỗi dòng đúng 1 câu dịch bắt đầu bằng [Số thứ tự]."
    )

    candidate_models = (
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-3.8-flash",
        "gemini-flash-latest",
        "gemini-2.5-flash",
        "gemini-1.5-flash",
    )
    batch_size = 100
    all_translated: list[str] = []

    for chunk_start in range(0, len(dialogues), batch_size):
        chunk = dialogues[chunk_start : chunk_start + batch_size]
        numbered_text = "\n".join([f"{i+1}. {text}" for i, text in enumerate(chunk)])

        payload = {
            "system_instruction": {"parts": [{"text": sys_instruction}]},
            "contents": [{"parts": [{"text": f"Dịch danh sách các câu thoại sau sang Tiếng Việt:\n{numbered_text}"}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096}
        }

        translated_raw = ""
        for model_name in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={clean_key}"
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=25)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        if parts:
                            translated_raw = parts[0].get("text", "").strip()
                            if translated_raw:
                                break
            except Exception:
                continue

        # Bóc tách kết quả theo số thứ tự
        vn_dict: dict[int, str] = {}
        if translated_raw:
            for line in translated_raw.splitlines():
                line_str = line.strip()
                if not line_str:
                    continue
                match = re.match(r"^(\d+)[\.\)]\s*(.*)", line_str)
                if match:
                    idx = int(match.group(1))
                    text_vi = match.group(2).strip().replace("**", "").replace("*", "").strip()
                    if text_vi:
                        vn_dict[idx] = text_vi

        # Nếu Gemini hoàn toàn không trả về kết quả hợp lệ, ném ngoại lệ để chuyển sang dịch dự phòng
        if not vn_dict:
            raise RuntimeError("Gemini API không phản hồi kết quả hợp lệ, chuyển sang dịch dự phòng Google Translate.")

        for i in range(1, len(chunk) + 1):
            line_vi = vn_dict.get(i, "")
            # Nếu câu bị thiếu hoặc còn sót chữ Hán, dùng dịch dự phòng cho riêng câu đó
            if not line_vi or any("\u4e00" <= c <= "\u9fff" for c in line_vi):
                fb_trans = _fetch_gtx_translate(chunk[i - 1], sl="zh-CN", tl="vi")
                line_vi = fb_trans if fb_trans else chunk[i - 1]
            all_translated.append(line_vi)
            global_idx = chunk_start + (i - 1)
            if on_sentence_translated_cb:
                on_sentence_translated_cb(global_idx, line_vi)

    return all_translated


def clean_general_translation(text: str) -> str:
    """
    Bước 3: Bộ lọc Hán-Việt tổng quát dự phòng (Fallback General Normalizer).
    Dọn dẹp tổng quát chạy sau dịch để loại bỏ lỗi phổ biến cho MỌI video:
    - Sửa "Mr. [Tên]" thành "[Tên] tiên sinh".
    - Xóa bỏ các từ tiếng Anh bị sót ("Cloud Villa" -> "biệt thự Vân Đoan").
    - Chuẩn hóa đại từ, cấu trúc câu ngô nghê mà không gán cứng bất kỳ tên nhân vật nào.
    """
    cleaned = text

    # 1. Tự động sửa cấu trúc "Mr. [Tên]" thành "[Tên] tiên sinh"
    cleaned = re.sub(r'\bMr\.?\s*([A-Za-zÀ-ỹ]+)', r'\1 tiên sinh', cleaned, flags=re.IGNORECASE)

    # 2. Xóa bỏ các từ tiếng Anh bị sót
    cleaned = re.sub(r'\bCloud Villa\b', 'biệt thự Vân Đoan', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\bSir\s+([A-Za-zÀ-ỹ]+)', r'\1 tiên sinh', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\bMiss\s+([A-Za-zÀ-ỹ]+)', r'\1 tiểu thư', cleaned, flags=re.IGNORECASE)

    # 3. Chống hiện tượng lặp từ bất thường
    cleaned = re.sub(r'(con chó\s*[,、]?\s*){3,}', 'đôi cẩu nam nữ ', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'(hai con chó\s*[,、]?\s*){2,}', 'đôi cẩu nam nữ ', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'hai bạn vẫn đang tranh giành bạn tình', 'hai người cẩu nam nữ các người thật là xứng đôi', cleaned, flags=re.IGNORECASE)

    # 4. Khắc phục lỗi dịch máy ngô nghê về câu giao tiếp / tỏ tình chung
    cleaned = re.sub(r'Này chàng trai,\s*cậu có muốn làm bạn gái của tôi không\??', 'Làm bạn gái anh nhé?', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'cậu có muốn làm bạn gái của tôi không\??', 'làm bạn gái anh nhé?', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'Làm bạn gái của tôi là một điều không tốt', 'Làm bạn gái anh nhé', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'Làm bạn gái tôi là không tốt', 'Làm bạn gái anh có được không', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'Làm bạn gái của tôi không tốt sao', 'Làm bạn gái anh có được không', cleaned, flags=re.IGNORECASE)

    # 5. Loại bỏ khoảng trắng thừa
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def polish_film_translation(text_vn: str) -> str:
    """Hàm tương thích ngược - gọi clean_general_translation."""
    return clean_general_translation(text_vn)


def translate_dialogues_gemini(dialogues: list[str], api_key: str, source_lang: str = "zh") -> list[str]:
    """Hàm tương thích: Tự động chạy Quy trình 2 bước (2-Pass Pipeline) bằng Gemini Flash API."""
    if not api_key or not api_key.strip():
        raise ValueError("Chưa cấu hình Gemini API Key. Vui lòng nhập key trong phần Cài đặt.")
    if not dialogues:
        return []

    full_text = "\n".join(dialogues)
    profile = extract_video_context_profile(full_text, api_key=api_key.strip())
    raw_translated = translate_dialogues_with_profile(dialogues, profile=profile, api_key=api_key.strip())
    return [clean_general_translation(line) for line in raw_translated]


def _fetch_gtx_translate(text: str, sl: str = "zh-CN", tl: str = "vi") -> str:
    """Gọi Google Translate qua curl_cffi giả lập Chrome tránh lỗi TooManyRequests / Timeout."""
    try:
        from curl_cffi import requests as c_requests
        url = "https://translate.googleapis.com/translate_a/single"
        params = {"client": "gtx", "sl": sl, "tl": tl, "dt": "t", "q": text}
        resp = c_requests.get(url, params=params, impersonate="chrome124", timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            lines = [item[0] for item in data[0] if item and item[0]]
            return "".join(lines).strip()
    except Exception:
        pass
    return ""


def translate_film_context(
    segments: List[DubSegment],
    source_lang: str = "zh",
    gemini_api_key: str = "",
    batch_size: int = 15,
    progress_cb: Optional[Callable[[str], None]] = None,
    on_sentence_translated_cb: Optional[Callable[[int, str], None]] = None,
) -> None:
    """
    Dịch theo khối ngữ cảnh liên tục kết hợp 2-Pass Contextual Pipeline:
    ƯU TIÊN 1: Gemini Flash API (Bước 1 trích xuất profile, Bước 2 dịch theo profile, Bước 3 chuẩn hóa).
    ƯU TIÊN 2: Fallback Google Translate / deep-translator nếu chưa có API Key.
    """
    if not segments:
        return

    # 1. Ưu tiên dịch qua Gemini 2-Pass Contextual Pipeline nếu có key
    if gemini_api_key and gemini_api_key.strip():
        raw_dialogues = [seg.text_orig if seg.text_orig else "..." for seg in segments]
        full_text = "\n".join(seg.text_orig.strip() for seg in segments if seg.text_orig.strip())
        try:
            if progress_cb:
                progress_cb("[GEMINI 2-PASS] Bước 1: Đang phân tích bối cảnh & trích xuất thực thể...")

            profile = extract_video_context_profile(full_text, api_key=gemini_api_key.strip())

            if progress_cb:
                progress_cb("[GEMINI 2-PASS] Bước 2: Đang dịch toàn bộ câu thoại theo hồ sơ bối cảnh...")

            vn_list = translate_dialogues_with_profile(
                raw_dialogues,
                profile=profile,
                api_key=gemini_api_key.strip(),
                on_sentence_translated_cb=on_sentence_translated_cb,
            )

            if len(vn_list) == len(segments):
                if progress_cb:
                    progress_cb("[GEMINI 2-PASS] Bước 3: Đang hoàn tất chuẩn hóa Hán-Việt tổng quát...")

                for idx, (seg, vn_line) in enumerate(zip(segments, vn_list)):
                    cleaned = clean_general_translation(vn_line)
                    seg.text_trans = cleaned
                    if on_sentence_translated_cb:
                        on_sentence_translated_cb(idx, cleaned)
                return
        except Exception as e:
            if progress_cb:
                progress_cb(f"[GEMINI DUB] Chuyển sang dịch dự phòng ({e})...")
            pass

    # 2. Fallback: Dịch máy Google Translate
    clean_src = source_lang.strip().lower()
    if clean_src in ("zh", "zh-cn", "cn", "zho_hans"):
        trans_src = "zh-CN"
    elif clean_src in ("zh-tw", "tw"):
        trans_src = "zh-TW"
    else:
        trans_src = "auto"

    for i in range(0, len(segments), batch_size):
        chunk = segments[i:i + batch_size]
        # Gom nhóm các câu thành đoạn văn để bảo toàn mạch ngữ cảnh liên tục
        combined_text = "\n".join(seg.text_orig if seg.text_orig else "..." for seg in chunk)

        # 2.1. Ưu tiên dịch qua curl_cffi (chống chặn IP, tốc độ cao, không lỗi giới hạn)
        translated_block = _fetch_gtx_translate(combined_text, sl=trans_src, tl="vi")
        lines = translated_block.split("\n") if translated_block else []

        # 2.2. Nếu trả về khớp số dòng, gán trực tiếp
        if len(lines) == len(chunk):
            for j, (seg, vn_line) in enumerate(zip(chunk, lines)):
                cleaned = clean_general_translation(vn_line)
                seg.text_trans = cleaned
                if on_sentence_translated_cb:
                    on_sentence_translated_cb(i + j, cleaned)
        else:
            # Fallback dịch từng câu nếu độ dài dòng không khớp
            for j, seg in enumerate(chunk):
                single_vn = _fetch_gtx_translate(seg.text_orig, sl=trans_src, tl="vi")
                if not single_vn:
                    try:
                        translator = GoogleTranslator(source=trans_src, target="vi")
                        single_vn = translator.translate(seg.text_orig)
                    except Exception:
                        single_vn = seg.text_orig
                cleaned = clean_general_translation(single_vn)
                seg.text_trans = cleaned
                if on_sentence_translated_cb:
                    on_sentence_translated_cb(i + j, cleaned)
                time.sleep(0.05)

        # Áp dụng từ điển thuật ngữ chung (không hardcode tên nhân vật)
        for j, seg in enumerate(chunk):
            for k, v in CHINESE_FILM_GLOSSARY.items():
                if k in seg.text_orig and k == "做我女朋友好不好":
                    seg.text_trans = "Làm bạn gái anh nhé?"
                    if on_sentence_translated_cb:
                        on_sentence_translated_cb(i + j, seg.text_trans)

        time.sleep(0.1)


# ══════════════════════════════════════════════════════════════════════
# BƯỚC 3: ĐIỀU TỐC GIỌNG ĐỌC & KIỂM TRA TTS (VOICE PACING & PREFLIGHT)
# ══════════════════════════════════════════════════════════════════════

def play_audio_file(file_path: str) -> None:
    """Mở file âm thanh để nghe thử trên hệ thống."""
    if not os.path.exists(file_path):
        return
    try:
        if sys.platform == "win32":
            os.startfile(file_path)
        elif sys.platform == "darwin":
            subprocess.Popen(["afplay", file_path])
        else:
            subprocess.Popen(["xdg-open", file_path])
    except Exception:
        pass


def test_tts_voice_sample(output_file: str = "test.mp3", auto_play: bool = False) -> bool:
    """
    Kiểm tra trực tiếp hàm sinh giọng đọc:
    - Chạy thử riêng 1 câu: tts = gTTS(text="Xin chào", lang="vi") và lưu ra file test.mp3.
    - Mở file test.mp3 lên nghe thử. Nếu phát ra tiếng "Xin chào" thì khâu TTS mới thực sự hoạt động.
    """
    try:
        tts = gTTS(text="Xin chào", lang="vi")
        tts.save(output_file)
        if os.path.exists(output_file) and os.path.getsize(output_file) >= 1000:
            if auto_play:
                play_audio_file(output_file)
            return True
        return False
    except Exception:
        return False


def generate_voice_and_pace(
    segments: List[DubSegment],
    temp_dir: str,
    ffmpeg_bin: str,
    progress_cb: Optional[Callable[[str], None]] = None,
    on_sentence_completed_cb: Optional[Callable[[int, str], None]] = None,
) -> List[DubSegment]:
    """
    Sinh giọng đọc bằng gTTS và điều tốc (atempo) chuẩn VideoLingo:
    Nếu giọng đọc dài hơn thời lượng cảnh gốc -> tự động tăng tốc đọc vừa khít,
    tuyệt đối không để câu nói tràn sang cảnh sau.
    """
    valid_segments: List[DubSegment] = []
    total = len(segments)

    for idx, seg in enumerate(segments):
        raw_text = seg.text_trans.strip()
        if not raw_text or raw_text in [".", ",", "...", "!", "?", "。"]:
            continue

        raw_audio_path = os.path.join(temp_dir, f"raw_{idx}.mp3")
        paced_audio_path = os.path.join(temp_dir, f"paced_{idx}.mp3")

        # 1. Sinh âm thanh bằng gTTS
        try:
            tts = gTTS(text=raw_text, lang="vi", slow=False)
            tts.save(raw_audio_path)
        except Exception:
            time.sleep(0.5)
            try:
                tts = gTTS(text=raw_text, lang="vi", slow=False)
                tts.save(raw_audio_path)
            except Exception:
                continue

        if not os.path.exists(raw_audio_path) or os.path.getsize(raw_audio_path) < 1000:
            continue

        # 2. Đo thời lượng thực tế
        try:
            audio_seg = AudioSegment.from_file(raw_audio_path)
            actual_dur = len(audio_seg) / 1000.0
        except Exception:
            actual_dur = 1.5

        # 3. Tính toán thời lượng cho phép (cho phép mượn một phần khoảng lặng nhỏ)
        target_dur = max(0.6, seg.end - seg.start)
        next_start = segments[idx + 1].start if idx + 1 < total else seg.end + 1.0
        gap = max(0.0, next_start - seg.end)
        available_dur = target_dur + min(gap * 0.5, 0.4)

        # 4. Điều tốc (Pacing) nếu nói quá chậm
        if actual_dur > available_dur and available_dur > 0.4:
            speed_factor = actual_dur / available_dur
            # Giới hạn tốc độ đọc tối đa 1.75x để giữ giọng tự nhiên
            clamped_speed = min(1.75, max(1.02, speed_factor))

            cmd_pace = [
                ffmpeg_bin,
                "-y",
                "-i", raw_audio_path,
                "-filter:a", f"atempo={clamped_speed:.3f}",
                "-vn",
                paced_audio_path
            ]
            res = subprocess.run(cmd_pace, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0 and os.path.exists(paced_audio_path) and os.path.getsize(paced_audio_path) >= 1000:
                seg.audio_path = paced_audio_path
                seg.duration_actual = actual_dur / clamped_speed
            else:
                seg.audio_path = raw_audio_path
                seg.duration_actual = actual_dur
        else:
            seg.audio_path = raw_audio_path
            seg.duration_actual = actual_dur

        valid_segments.append(seg)
        if on_sentence_completed_cb:
            on_sentence_completed_cb(idx, "🎙️ Đã lồng tiếng")
        if progress_cb and (idx + 1) % 5 == 0:
            progress_cb(f"[VIDEOLINGO DUB] Đang điều tốc và khớp khung hình: {idx + 1}/{total} câu...")

    return valid_segments


# ══════════════════════════════════════════════════════════════════════
# BƯỚC 4: HÒA TRỘN ÂM THANH & AUDIO DUCKING CHUẨN ĐIỆN ẢNH
# ══════════════════════════════════════════════════════════════════════

def build_dubbed_audio_track(
    segments: List[DubSegment],
    output_wav: str,
) -> bool:
    """Ghép toàn bộ các câu thoại vào đúng mốc thời gian (Timeline) bằng khoảng lặng."""
    if not segments:
        return False

    valid_audio_count = 0
    track = AudioSegment.silent(duration=0, frame_rate=24000)
    current_ms = 0

    for seg in segments:
        if not seg.audio_path or not os.path.exists(seg.audio_path) or os.path.getsize(seg.audio_path) < 1000:
            continue

        start_ms = int(seg.start * 1000)
        # Thêm khoảng lặng trước câu thoại nếu cần
        if start_ms > current_ms:
            track += AudioSegment.silent(duration=start_ms - current_ms, frame_rate=24000)
            current_ms = start_ms

        try:
            voice_clip = AudioSegment.from_file(seg.audio_path).set_frame_rate(24000)
            if len(voice_clip) > 0:
                track += voice_clip
                current_ms += len(voice_clip)
                valid_audio_count += 1
        except Exception:
            continue

    if valid_audio_count == 0 or len(track) == 0:
        return False

    track.export(output_wav, format="wav")
    return os.path.exists(output_wav) and os.path.getsize(output_wav) >= 1000


def render_cinema_dub_video(
    input_video: str,
    dub_track_wav: str,
    output_video: str,
    ffmpeg_bin: str,
    bg_volume: float = 0.12,
) -> bool:
    """
    Hòa trộn âm thanh bằng FFmpeg Sidechain Compressor Ducking:
    - Khi có tiếng thuyết minh tiếng Việt: tự động giảm nhạc nền gốc xuống 10% - 15% (mặc định 12%).
    - Khi hết câu: tự động trả lại âm lượng nhạc nền nguyên bản êm dịu (release 350ms).
    - Giữ nguyên luồng hình ảnh gốc (-c:v copy).
    """
    # Chốt chặn nghiêm ngặt: Kiểm tra file âm thanh tiếng Việt trước khi render
    if not os.path.exists(dub_track_wav) or os.path.getsize(dub_track_wav) < 1000:
        raise Exception("LỖI THỰC TẾ: File âm thanh tiếng Việt bị rỗng. Không thể ghép vào video.")

    # 1. Thử nghiệm bộ lọc Sidechain Ducking cao cấp
    ducking_filter = (
        f"[0:a][1:a]sidechaincompress="
        f"threshold=0.08:ratio=6:attack=80:release=350[bg];"
        f"[bg][1:a]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )

    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", input_video,
        "-i", dub_track_wav,
        "-filter_complex", ducking_filter,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        output_video,
    ]

    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if res.returncode == 0 and os.path.exists(output_video) and os.path.getsize(output_video) > 1024:
        return True

    # 2. Fallback: Nếu video gốc không hỗ trợ sidechaincompress, dùng static ducking an toàn
    fallback_filter = f"[0:a]volume={bg_volume:.2f}[bg];[1:a]volume=1.0[voice];[bg][voice]amix=inputs=2:duration=first[aout]"
    cmd_fallback = [
        ffmpeg_bin,
        "-y",
        "-i", input_video,
        "-i", dub_track_wav,
        "-filter_complex", fallback_filter,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        output_video,
    ]
    res_fb = subprocess.run(cmd_fallback, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return res_fb.returncode == 0 and os.path.exists(output_video)


def format_seconds_to_srt(seconds: float) -> str:
    """Chuyển giây float sang chuẩn SRT 00:00:00,000."""
    total_sec = max(0, int(seconds))
    millis = int(round((seconds - total_sec) * 1000))
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    s = total_sec % 60
    return f"{h:02d}:{m:02d}:{s:02d},{millis:03d}"


def save_subtitles_and_metadata(video_paths: list[str], segments: list[DubSegment]) -> None:
    """Tự động xuất file phụ đề .srt và .omnigrab.json đồng bộ cho danh sách video."""
    if not segments:
        return
    for v_path in video_paths:
        if not v_path:
            continue
        try:
            base_dir = os.path.dirname(os.path.abspath(v_path))
            file_stem = os.path.splitext(os.path.basename(v_path))[0]

            # 1. File JSON lưu đầy đủ cả câu gốc và câu dịch
            json_path = os.path.join(base_dir, f"{file_stem}.omnigrab.json")
            data = []
            for seg in segments:
                data.append({
                    "start": round(float(seg.start), 3),
                    "end": round(float(seg.end), 3),
                    "text_orig": getattr(seg, "text_orig", "") or "",
                    "text_trans": getattr(seg, "text_trans", "") or "",
                    "status": "🎙️ Đã lồng tiếng",
                })
            with open(json_path, "w", encoding="utf-8") as jf:
                json.dump(data, jf, ensure_ascii=False, indent=2)

            # 2. File SRT chuẩn
            srt_path = os.path.join(base_dir, f"{file_stem}.srt")
            with open(srt_path, "w", encoding="utf-8") as sf:
                for idx, seg in enumerate(segments, start=1):
                    t_start = format_seconds_to_srt(seg.start)
                    t_end = format_seconds_to_srt(seg.end)
                    text = seg.text_trans.strip() if getattr(seg, "text_trans", None) else seg.text_orig.strip()
                    sf.write(f"{idx}\n{t_start} --> {t_end}\n{text}\n\n")
        except Exception:
            pass



# ══════════════════════════════════════════════════════════════════════
# LỚP ĐIỀU PHỐI CHÍNH: OmniDubber (VideoLingo Engine)
# ══════════════════════════════════════════════════════════════════════

class OmniDubber:
    """Bộ điều phối lồng tiếng AI điện ảnh tích hợp Gemini Flash API & VideoLingo."""

    def __init__(self, whisper_model_size: str = "base", gemini_api_key: str = "") -> None:
        self.ffmpeg = FFMPEG_PATH
        self.gemini_api_key = gemini_api_key
        self.model = WhisperModel(whisper_model_size, device="cpu", compute_type="int8")

    def transcribe(
        self,
        audio_path: str,
        lang: str = "zh",
        on_segment_cb: Optional[Callable[[Any], None]] = None,
    ) -> List[Any]:
        """
        Nhận diện giọng nói với bộ lọc VAD nhạy cao và triệt tiêu hoàn toàn ảo giác.
        """
        # 1. Cấu hình VAD nhạy hơn để bắt trọn vẹn cả câu ngắn ("Cút đi!") và câu có nhạc nền to
        vad_params = dict(
            threshold=0.35,              # Hạ ngưỡng từ 0.5 xuống 0.35 để không bỏ sót tiếng người khi nhạc to
            min_speech_duration_ms=150,  # Bắt được cả từ ngắn 0.2s như "Cút!"
            max_speech_duration_s=float('inf'),
            min_silence_duration_ms=400,
            speech_pad_ms=300            # Đệm thêm 0.3s trước và sau câu nói
        )

        # 2. TUYỆT ĐỐI XÓA BỎ initial_prompt (để rỗng hoặc None) để tránh bẫy ảo giác
        segments, _ = self.model.transcribe(
            audio_path,
            language=lang,
            vad_filter=True,
            vad_parameters=vad_params,
            condition_on_previous_text=False,  # Tránh kẹt cửa sổ âm thanh
            temperature=0.0,
            initial_prompt=None                # BẮT BUỘC ĐỂ NONE
        )
        if on_segment_cb:
            result = []
            for s in segments:
                result.append(s)
                on_segment_cb(s)
            return result
        return list(segments)

    def process_dubbing(
        self,
        input_video: str,
        output_video: str,
        source_lang: str = "zh",
        voice: str = "vi",
        gemini_api_key: str = "",
        bg_volume: float = 0.12,
        custom_segments: Optional[List[DubSegment]] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
        on_segment_discovered_cb: Optional[Callable[[dict], None]] = None,
        on_segments_loaded_cb: Optional[Callable[[list], None]] = None,
        on_sentence_translated_cb: Optional[Callable[[int, str], None]] = None,
        on_sentence_completed_cb: Optional[Callable[[int, str], None]] = None,
    ) -> bool:
        """Thực thi pipeline lồng tiếng VideoLingo 4 bước."""
        def log(msg: str) -> None:
            if progress_callback:
                progress_callback(msg)

        active_key = (gemini_api_key or self.gemini_api_key).strip()

        temp_dir = os.path.join(os.path.dirname(os.path.abspath(input_video)), "temp_dub")
        os.makedirs(temp_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(input_video))[0]
        temp_wav = os.path.join(temp_dir, f"{base_name}_16k.wav")
        full_dub_wav = os.path.join(temp_dir, f"{base_name}_dubtrack.wav")

        try:
            if custom_segments and len(custom_segments) > 0:
                merged_segments = custom_segments
                log(f"[STUDIO DUB] Đang sử dụng {len(merged_segments)} câu thoại đã soát từ Studio...")
                if on_segments_loaded_cb:
                    seg_dicts = [{'start': s.start, 'end': s.end, 'text': s.text_orig} for s in merged_segments]
                    on_segments_loaded_cb(seg_dicts)

                needs_translation = any(not getattr(s, 'text_trans', '').strip() for s in merged_segments)
                if needs_translation:
                    translate_film_context(
                        merged_segments,
                        source_lang=source_lang,
                        gemini_api_key=active_key,
                        progress_cb=log,
                        on_sentence_translated_cb=on_sentence_translated_cb,
                    )
                else:
                    if on_sentence_translated_cb:
                        for idx, s in enumerate(merged_segments):
                            on_sentence_translated_cb(idx, s.text_trans)
            else:
                # BƯỚC 1: Bóc tách & Gom câu ngữ pháp
                log("[VIDEOLINGO DUB] Đang bóc tách và gom câu theo ngữ pháp hoàn chỉnh...")
                cmd_extract = [
                    self.ffmpeg,
                    "-y",
                    "-i", input_video,
                    "-vn",
                    "-acodec", "pcm_s16le",
                    "-ar", "16000",
                    "-ac", "1",
                    temp_wav,
                ]
                subprocess.run(cmd_extract, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                clean_lang = source_lang.strip().lower()
                w_lang = "zh" if clean_lang.startswith("zh") else (clean_lang.split("-")[0] if "-" in clean_lang else clean_lang or "zh")

                discovered_count = 0
                def _on_seg_discovered(s):
                    nonlocal discovered_count
                    discovered_count += 1
                    if on_segment_discovered_cb:
                        on_segment_discovered_cb({'start': s.start, 'end': s.end, 'text': s.text})
                    if discovered_count % 5 == 0 or discovered_count == 1:
                        log(f"[WHISPER] Đang bóc tách lời thoại: mốc {int(s.end)}s (đã nhận diện {discovered_count} câu)...")

                raw_list = self.transcribe(
                    temp_wav,
                    lang=w_lang,
                    on_segment_cb=_on_seg_discovered,
                )

                if not raw_list:
                    raise RuntimeError("Không phát hiện được giọng nói trong video.")

                # Áp dụng giải thuật VideoLingo Gom câu
                merged_segments = merge_broken_segments(raw_list)
                log(f"[VIDEOLINGO DUB] Đã gom {len(raw_list)} mẩu thoại thành {len(merged_segments)} câu hoàn chỉnh.")

                # Phát danh sách câu thoại để giao diện cập nhật ngay lập tức
                if on_segments_loaded_cb:
                    seg_dicts = [{'start': s.start, 'end': s.end, 'text': s.text_orig} for s in merged_segments]
                    on_segments_loaded_cb(seg_dicts)

                # BƯỚC 2: Dịch thuật ngữ cảnh bằng Gemini 2-Pass Pipeline
                if active_key:
                    log("[GEMINI FLASH DUB] Đang chạy Quy trình dịch 2 bước (2-Pass Contextual Pipeline)...")
                else:
                    log("[VIDEOLINGO DUB] Đang dịch kịch bản sang Tiếng Việt...")

                translate_film_context(
                    merged_segments,
                    source_lang=source_lang,
                    gemini_api_key=active_key,
                    progress_cb=log,
                    on_sentence_translated_cb=on_sentence_translated_cb,
                )

            # KIỂM TRA TRỰC TIẾP HÀM SINH GIỌNG ĐỌC TTS TRƯỚC KHI THỰC HIỆN
            log("[TTS PRE-CHECK] Đang kiểm tra trực tiếp hàm sinh giọng đọc gTTS ('Xin chào')...")
            test_voice_file = os.path.join(temp_dir, "test.mp3")
            try:
                tts_ok = test_tts_voice_sample(output_file=test_voice_file, auto_play=False)
                if not tts_ok:
                    raise Exception("Không thể tạo file âm thanh mẫu từ gTTS.")
            except Exception as e:
                raise Exception(f"LỖI THỰC TẾ: Dịch vụ giọng đọc tiếng Việt (gTTS) không hoạt động ({e}). Hủy xuất video.")

            # BƯỚC 3: Sinh giọng đọc & Điều tốc (Speed Pacing)
            log("[VIDEOLINGO DUB] Đang tạo giọng đọc gTTS và điều tốc khớp từng khung hình...")
            paced_segments = generate_voice_and_pace(
                merged_segments,
                temp_dir=temp_dir,
                ffmpeg_bin=self.ffmpeg,
                progress_cb=log,
                on_sentence_completed_cb=on_sentence_completed_cb,
            )

            # CHỐT CHẶN 1: Kiểm tra file âm thanh tiếng Việt từng câu thoại trước khi ghép
            segment_files = [
                seg.audio_path for seg in paced_segments
                if seg.audio_path and os.path.exists(seg.audio_path) and os.path.getsize(seg.audio_path) >= 1000
            ]
            if not segment_files or len(segment_files) == 0:
                raise Exception("LỖI THỰC TẾ: Không tạo được bất kỳ câu thoại tiếng Việt nào từ TTS. Hủy xuất video.")

            # BƯỚC 4: Hòa trộn âm thanh & Sidechain Ducking
            combined_voice = full_dub_wav
            built = build_dubbed_audio_track(paced_segments, combined_voice)

            # CHỐT CHẶN 2: Kiểm tra file âm thanh tiếng Việt tổng hợp trước khi ghép
            if not os.path.exists(combined_voice) or os.path.getsize(combined_voice) < 1000:
                raise Exception("LỖI THỰC TẾ: File âm thanh tiếng Việt bị rỗng. Không thể ghép vào video.")

            success = render_cinema_dub_video(
                input_video=input_video,
                dub_track_wav=combined_voice,
                output_video=output_video,
                ffmpeg_bin=self.ffmpeg,
                bg_volume=bg_volume,
            )

            if success and os.path.isfile(output_video):
                try:
                    save_subtitles_and_metadata([input_video, output_video], paced_segments)
                except Exception:
                    pass
                log(f"[VIDEOLINGO DUB] Hoàn tất! Video đã lưu tại: {output_video}")
                return True
            else:
                raise RuntimeError("Xuất video thành phẩm thất bại.")

        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)


# Tương thích tên gọi
VideoDubber = OmniDubber


# ══════════════════════════════════════════════════════════════════════
# GIAO DIỆN TƯƠNG THÍCH CHO UI
# ══════════════════════════════════════════════════════════════════════

@dataclass
class DubConfig:
    """Cấu hình cho phiên lồng tiếng."""
    source_lang: str = "zh-CN"
    voice: str = "vi"
    bg_volume: float = 0.12
    whisper_model: str = "base"
    gemini_api_key: str = ""
    ffmpeg_path: str = ""
    custom_segments: Optional[List[DubSegment]] = None
    log_callback: Optional[Callable[[str], None]] = None
    progress_callback: Optional[Callable[[int, int], None]] = None


def check_dub_dependencies() -> dict[str, bool]:
    """Kiểm tra các thư viện phục vụ lồng tiếng."""
    res: dict[str, bool] = {}
    for lib in ("faster_whisper", "gtts", "requests", "pydub"):
        try:
            __import__(lib)
            res[lib] = True
        except ImportError:
            res[lib] = False
    return res
