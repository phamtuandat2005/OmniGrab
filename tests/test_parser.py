import pytest
from core.parser import extract_urls, count_urls, read_urls_from_file


def test_extract_single_url():
    raw = "Xem video này: https://www.youtube.com/watch?v=dQw4w9WgXcQ rất hay!"
    urls = extract_urls(raw)
    assert len(urls) == 1
    assert urls[0] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_extract_tiktok_and_douyin():
    raw = """
    7.12 复制打开抖音... https://v.douyin.com/i8ABCD/
    Check this TikTok: https://vt.tiktok.com/ZSxxxx/
    """
    urls = extract_urls(raw)
    assert len(urls) == 2
    assert "https://v.douyin.com/i8ABCD" in urls
    assert "https://vt.tiktok.com/ZSxxxx" in urls


def test_extract_deduplication():
    raw = "https://youtu.be/abc12345 và https://youtu.be/abc12345 lần 2"
    urls = extract_urls(raw)
    assert len(urls) == 1
    assert urls[0] == "https://youtu.be/abc12345"


def test_normalize_douyin_modal_id():
    raw = "https://www.douyin.com/jingxuan?modal_id=7659636795000799397"
    urls = extract_urls(raw)
    assert len(urls) == 1
    assert urls[0] == "https://www.douyin.com/video/7659636795000799397"


def test_count_urls():
    raw = "https://fb.watch/xyz và https://www.tiktok.com/@user/video/123"
    assert count_urls(raw) == 2
    assert count_urls("") == 0
    assert count_urls("Không có link nào") == 0


def test_read_urls_from_file(tmp_path):
    test_file = tmp_path / "links.txt"
    test_file.write_text(
        "Line 1: https://www.youtube.com/watch?v=111\n"
        "Line 2: https://v.douyin.com/222\n",
        encoding="utf-8"
    )
    urls = read_urls_from_file(str(test_file))
    assert len(urls) == 2
