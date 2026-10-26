import re
from core.license_manager import LicenseManager


def test_machine_id_format():
    mgr = LicenseManager()
    machine_id = mgr.get_machine_id()
    assert isinstance(machine_id, str)
    # Định dạng mã máy tính: OG-XXXX-XXXX-XXXX
    pattern = r"^OG-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}$"
    assert re.match(pattern, machine_id) is not None, f"Machine ID '{machine_id}' sai định dạng OG-XXXX-XXXX-XXXX"


def test_verify_invalid_key():
    mgr = LicenseManager()
    # Key rác hoặc sai cấu trúc phải trả về False
    valid, msg = mgr.verify_and_save_key("INVALID-KEY-1234")
    assert valid is False
    assert "không hợp lệ" in msg.lower() or "base64" in msg.lower()


def test_trial_decrement(tmp_path, monkeypatch):
    mgr = LicenseManager()
    fake_trial_file = tmp_path / ".omnigrab_trial.dat"
    fake_license_file = tmp_path / ".omnigrab_license.dat"
    monkeypatch.setattr("core.license_manager._TRIAL_FILE", fake_trial_file)
    monkeypatch.setattr("core.license_manager._LICENSE_FILE", fake_license_file)
    mgr.invalidate_cache()

    # Lần đầu chưa có file -> số lượt dùng thử = 10
    remaining = mgr._get_trial_remaining()
    assert remaining == 10

    # Tiêu thụ 1 lượt
    new_remaining = mgr.consume_trial()
    assert new_remaining == 9
    assert fake_trial_file.is_file()
