from pathlib import Path
import sys
import pytest
from PyQt6.QtWidgets import QApplication
from core.auto_updater import (
    format_size,
    format_speed,
    format_eta,
    get_updates_dir,
    get_cached_installer_path,
    is_installer_downloaded,
)
from core.update_checker import (
    find_release_update,
    ReleaseUpdate,
    _version_key,
)
from ui.update_dialog import UpdateDialog


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_version_key():
    assert _version_key("4.0.2") == (4, 0, 2)
    assert _version_key("4.10.15") == (4, 10, 15)
    with pytest.raises(ValueError):
        _version_key("invalid.version")


def test_format_helpers():
    assert format_size(0) == "0 MB"
    assert format_size(1024 * 1024) == "1.0 MB"
    assert format_size(1024 * 1024 * 50) == "50.0 MB"
    assert format_size(1024 * 1024 * 1024 * 2) == "2.0 GB"

    assert format_speed(0) == "-- KB/s"
    assert format_speed(500 * 1024) == "500 KB/s"
    assert format_speed(2.5 * 1024 * 1024) == "2.5 MB/s"

    assert format_eta(0) == "--"
    assert format_eta(45) == "45 giây"
    assert format_eta(125) == "2p 5s"
    assert format_eta(3665) == "1h 1p"


def test_find_release_update_with_size():
    mock_payload = {
        "html_url": "https://github.com/phamtuandat2005/OmniGrab/releases/tag/v4.1.0",
        "body": "Fixes and new features",
        "assets": [
            {
                "name": "OmniGrab.Setup.4.1.0.exe",
                "browser_download_url": "https://github.com/phamtuandat2005/OmniGrab/releases/download/v4.1.0/OmniGrab.Setup.4.1.0.exe",
                "size": 52428800,
            },
            {
                "name": "OmniGrab_v4.1.0_Portable.zip",
                "browser_download_url": "https://github.com/phamtuandat2005/OmniGrab/releases/download/v4.1.0/OmniGrab_v4.1.0_Portable.zip",
                "size": 62428800,
            },
        ],
    }

    # Current is 4.0.2, new is 4.1.0 -> Should return ReleaseUpdate with size
    res = find_release_update(mock_payload, "4.0.2")
    assert res is not None
    assert res.version == "4.1.0"
    assert res.size == 52428800
    assert "https://github.com" in res.download_url
    assert res.notes == "Fixes and new features"

    # Current is 4.1.0, payload is 4.1.0 -> Should return None (up to date)
    assert find_release_update(mock_payload, "4.1.0") is None

    # Current is 5.0.0, payload is 4.1.0 -> Should return None (newer than release)
    assert find_release_update(mock_payload, "5.0.0") is None


def test_installer_cache_helpers(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    up_dir = get_updates_dir()
    assert up_dir.is_dir()
    assert up_dir == tmp_path / "OmniGrab" / "updates"

    target_file = get_cached_installer_path("9.9.9")
    assert target_file == up_dir / "OmniGrab.Setup.9.9.9.exe"
    assert not is_installer_downloaded("9.9.9")

    # Create dummy file with 15MB
    target_file.write_bytes(b"0" * (15 * 1024 * 1024))
    assert is_installer_downloaded("9.9.9")
    assert is_installer_downloaded("9.9.9", expected_size=15 * 1024 * 1024)
    assert not is_installer_downloaded("9.9.9", expected_size=20 * 1024 * 1024)


def test_update_dialog_ui(qapp):
    up = ReleaseUpdate(
        version="4.5.0",
        download_url="https://github.com/phamtuandat2005/OmniGrab/releases/download/v4.5.0/OmniGrab.Setup.4.5.0.exe",
        release_url="https://github.com/phamtuandat2005/OmniGrab/releases/tag/v4.5.0",
        notes="Giao diện và tính năng cập nhật mới.",
        size=50 * 1024 * 1024,
    )
    dlg = UpdateDialog(up)
    assert "4.5.0" in dlg.windowTitle()
    assert dlg.notes_box.toPlainText() == "Giao diện và tính năng cập nhật mới."
    assert "Cập nhật tự động" in dlg.btn_primary.text()
    assert not dlg.progress_card.isVisible()
    assert not dlg.ready_banner.isVisible()
