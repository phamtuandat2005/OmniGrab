import os
from pathlib import Path
from core.security import (
    get_base_path,
    get_app_dir,
    get_resource_path,
    _verify_file_integrity,
    setup_ffmpeg_environment,
)


def test_paths_exist():
    base_path = get_base_path()
    assert os.path.isdir(base_path), f"get_base_path() trả về đường dẫn không tồn tại: {base_path}"

    app_dir = get_app_dir()
    assert os.path.isdir(app_dir), f"get_app_dir() trả về đường dẫn không tồn tại: {app_dir}"


def test_get_resource_path():
    icon_rel = "assets/icon.png"
    icon_abs = os.path.normpath(get_resource_path(icon_rel))
    assert os.path.isabs(icon_abs)
    expected_suffix = os.path.normpath(icon_rel)
    assert icon_abs.endswith(expected_suffix)


def test_verify_file_integrity(tmp_path):
    sample = tmp_path / "hello.txt"
    sample.write_text("Hello OmniGrab CI/CD", encoding="utf-8")

    import hashlib
    expected_hash = hashlib.sha256("Hello OmniGrab CI/CD".encode("utf-8")).hexdigest()

    assert _verify_file_integrity(str(sample), expected_hash) is True
    assert _verify_file_integrity(str(sample), "wrong_hash") is False
    assert _verify_file_integrity(str(tmp_path / "non_existing.bin"), expected_hash) is False


def test_setup_ffmpeg_environment():
    ffmpeg_bin, ffprobe_bin = setup_ffmpeg_environment()
    assert isinstance(ffmpeg_bin, str)
    assert isinstance(ffprobe_bin, str)
