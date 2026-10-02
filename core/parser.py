"""
core/parser.py - Trích xuất và làm sạch URL từ chuỗi văn bản.

Hỗ trợ:
- Trích xuất URL HTTP/HTTPS từ chuỗi chia sẻ (Douyin, TikTok, Facebook...).
- Đọc danh sách liên kết từ file .txt hoặc .csv.
- Loại bỏ trùng lặp và dòng trống.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

# Biểu thức chính quy trích xuất URL HTTP/HTTPS hợp lệ
_URL_PATTERN: re.Pattern[str] = re.compile(
    r'https?://[^\s<>"\')\]，。！？》）\u200b\u200c\u200d\ufeff]+'
)

# Các domain được hỗ trợ để tải video
_SUPPORTED_DOMAINS: tuple[str, ...] = (
    "tiktok.com",
    "douyin.com",
    "facebook.com",
    "fb.watch",
    "fb.com",
    "vm.tiktok.com",
    "vt.tiktok.com",
    "v.douyin.com",
    "www.douyin.com",
    "www.tiktok.com",
    "m.tiktok.com",
    "www.facebook.com",
    "m.facebook.com",
    "web.facebook.com",
    "youtube.com",
    "youtu.be",
    "www.youtube.com",
    "m.youtube.com",
)


def extract_urls(raw_text: str) -> List[str]:
    """
    Trích xuất tất cả URL hợp lệ từ chuỗi văn bản thô.

    Xử lý tốt các dạng chia sẻ từ điện thoại, ví dụ:
      '7.12 复制打开抖音... https://v.douyin.com/xxxxx/'
      'Xem video TikTok tuyệt vời này https://vm.tiktok.com/ZMxxxx/'

    Args:
        raw_text: Chuỗi văn bản có thể chứa nhiều URL lẫn với nội dung khác.

    Returns:
        Danh sách URL đã làm sạch, loại bỏ trùng lặp, giữ nguyên thứ tự.
    """
    if not raw_text or not raw_text.strip():
        return []

    found_urls: list[str] = _URL_PATTERN.findall(raw_text)

    # Làm sạch: loại bỏ ký tự thừa ở cuối URL
    cleaned: list[str] = []
    for url in found_urls:
        url = url.rstrip("/.,;:!?)")
        if _is_supported_url(url):
            url = _normalize_url(url)
            cleaned.append(url)

    # Loại bỏ trùng lặp, giữ nguyên thứ tự xuất hiện
    seen: set[str] = set()
    unique: list[str] = []
    for url in cleaned:
        if url not in seen:
            seen.add(url)
            unique.append(url)

    return unique


def read_urls_from_file(file_path: str) -> List[str]:
    """
    Đọc và trích xuất URL từ file văn bản (.txt hoặc .csv).

    Mỗi dòng trong file có thể chứa một URL hoặc một đoạn văn bản
    có kèm URL (sẽ được trích xuất tự động).

    Args:
        file_path: Đường dẫn tuyệt đối hoặc tương đối đến file.

    Returns:
        Danh sách URL đã trích xuất và làm sạch.

    Raises:
        FileNotFoundError: Nếu file không tồn tại.
        PermissionError: Nếu không có quyền đọc file.
        UnicodeDecodeError: Nếu file không phải UTF-8.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {file_path}")

    if not path.is_file():
        raise ValueError(f"Đường dẫn không phải là file: {file_path}")

    # Thử đọc với UTF-8, fallback sang Latin-1
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="latin-1")

    return extract_urls(content)


def _normalize_url(url: str) -> str:
    """
    Chuẩn hóa URL trước khi tải (ví dụ: bóc tách modal_id của Douyin).
    
    Args:
        url: URL gốc.
        
    Returns:
        URL đã được chuẩn hóa.
    """
    # Xử lý link Douyin dạng modal_id: https://www.douyin.com/jingxuan?modal_id=7659636795000799397
    if "douyin.com" in url and "modal_id=" in url:
        match = re.search(r'modal_id=(\d+)', url)
        if match:
            video_id = match.group(1)
            return f"https://www.douyin.com/video/{video_id}"
            
    return url


def _is_supported_url(url: str) -> bool:
    """
    Kiểm tra URL có thuộc các nền tảng được hỗ trợ hay không.

    Args:
        url: URL cần kiểm tra.

    Returns:
        True nếu URL thuộc domain hỗ trợ.
    """
    url_lower = url.lower()
    return any(domain in url_lower for domain in _SUPPORTED_DOMAINS)


def count_urls(raw_text: str) -> int:
    """
    Đếm nhanh số lượng URL hợp lệ trong chuỗi văn bản.

    Args:
        raw_text: Chuỗi văn bản cần đếm.

    Returns:
        Số lượng URL hợp lệ.
    """
    return len(extract_urls(raw_text))
