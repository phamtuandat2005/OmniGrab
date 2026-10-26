import re
from pathlib import Path
from core.version import APP_VERSION

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_app_version_format():
    """Kiểm tra định dạng phiên bản tuân thủ chuẩn Semantic Versioning (x.y.z)."""
    pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$"
    assert re.match(pattern, APP_VERSION) is not None, f"APP_VERSION '{APP_VERSION}' không đúng định dạng semver."


def test_setup_iss_version_consistency():
    """Kiểm tra tính nhất quán của APP_VERSION với cấu hình Inno Setup."""
    iss_file = ROOT_DIR / "setup.iss"
    assert iss_file.is_file(), "Không tìm thấy file setup.iss"
    
    content = iss_file.read_text(encoding="utf-8")
    # Kiểm tra dòng #define MyAppVersion "<version>"
    match = re.search(r'#define\s+MyAppVersion\s+"([^"]+)"', content)
    assert match is not None, "Không tìm thấy khai báo MyAppVersion trong setup.iss"
    iss_version = match.group(1)
    assert iss_version == APP_VERSION, (
        f"Phiên bản không khớp: core.version.APP_VERSION={APP_VERSION} "
        f"nhưng setup.iss MyAppVersion={iss_version}"
    )
