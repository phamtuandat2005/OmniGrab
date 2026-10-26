from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_packaging_files_exist():
    """Đảm bảo các file cần thiết cho quy trình CI/CD và đóng gói luôn tồn tại."""
    assert (ROOT_DIR / "OmniGrab.spec").is_file(), "Thiếu file OmniGrab.spec"
    assert (ROOT_DIR / "build_release.py").is_file(), "Thiếu script build_release.py"
    assert (ROOT_DIR / "setup.iss").is_file(), "Thiếu script setup.iss"
    assert (ROOT_DIR / "assets" / "icon.ico").is_file(), "Thiếu assets/icon.ico"
    assert (ROOT_DIR / "assets" / "icon.png").is_file(), "Thiếu assets/icon.png"


def test_build_release_script_syntax():
    """Kiểm tra cú pháp của build_release.py để tránh lỗi khi chạy CD."""
    script_path = ROOT_DIR / "build_release.py"
    code = script_path.read_text(encoding="utf-8")
    compile(code, str(script_path), "exec")
