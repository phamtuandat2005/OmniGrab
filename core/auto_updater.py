"""
core/auto_updater.py - Cơ chế Tự động tải & Cập nhật phiên bản mới cho OmniGrab.

Cung cấp:
1. UpdateDownloadWorker: Luồng (QThread) tải installer nền với tiến trình, tốc độ, thời gian còn lại.
2. launch_silent_update_and_restart: Tự động khởi chạy bộ cài Inno Setup ở chế độ im lặng (/SILENT),
   tắt app cũ để không bị khóa file, cài đặt đè bản mới và tự động mở lại OmniGrab.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

# pyrefly: ignore [missing-import]
from PyQt6.QtCore import QThread, pyqtSignal
# pyrefly: ignore [missing-import]
from PyQt6.QtWidgets import QApplication

from core.version import APP_VERSION


def get_updates_dir() -> Path:
    """Trả về thư mục lưu trữ bản cập nhật tải về (%LOCALAPPDATA%/OmniGrab/updates)."""
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        base = os.path.expanduser("~")
    updates_path = Path(base) / "OmniGrab" / "updates"
    updates_path.mkdir(parents=True, exist_ok=True)
    return updates_path


def get_cached_installer_path(version: str) -> Path:
    """Trả về đường dẫn file cài đặt của phiên bản tương ứng."""
    return get_updates_dir() / f"OmniGrab.Setup.{version}.exe"


def is_installer_downloaded(version: str, expected_size: int = 0) -> bool:
    """Kiểm tra xem file cài đặt đã được tải về hoàn chỉnh trước đó hay chưa."""
    target = get_cached_installer_path(version)
    if not target.is_file():
        return False
    try:
        size = target.stat().st_size
        # Bộ cài đặt OmniGrab thường > 50MB; nếu có expected_size thì so khớp
        if expected_size > 0:
            return size == expected_size
        return size > 10 * 1024 * 1024  # Tối thiểu 10 MB
    except OSError:
        return False


def format_size(size_bytes: float) -> str:
    """Định dạng dung lượng sang đơn vị thân thiện (B, KB, MB, GB)."""
    if size_bytes <= 0:
        return "0 MB"
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0 or unit == "GB":
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} GB"


def format_speed(bps: float) -> str:
    """Định dạng tốc độ truyền dữ liệu (KB/s, MB/s)."""
    if bps <= 0:
        return "-- KB/s"
    mbps = bps / (1024.0 * 1024.0)
    if mbps >= 1.0:
        return f"{mbps:.1f} MB/s"
    kbps = bps / 1024.0
    return f"{kbps:.0f} KB/s"


def format_eta(seconds: float) -> str:
    """Định dạng thời gian còn lại (giây, phút, giờ)."""
    if seconds <= 0 or seconds > 86400:
        return "--"
    secs = int(seconds)
    if secs < 60:
        return f"{secs} giây"
    mins = secs // 60
    rem_secs = secs % 60
    if mins < 60:
        return f"{mins}p {rem_secs}s"
    hours = mins // 60
    rem_mins = mins % 60
    return f"{hours}h {rem_mins}p"


class UpdateDownloadWorker(QThread):
    """
    Luồng chạy ngầm tải bộ cài đặt mới (.exe) từ GitHub Release.
    Phát tín hiệu tiến trình, tốc độ tải và ước lượng thời gian hoàn tất.
    """

    # downloaded_bytes, total_bytes, speed_bps, eta_text
    progress = pyqtSignal(int, int, float, str)
    finished = pyqtSignal(str)   # installer_path
    error = pyqtSignal(str)      # error_message
    cancelled = pyqtSignal()

    def __init__(
        self,
        download_url: str,
        version: str,
        expected_size: int = 0,
        parent: Optional[QThread] = None,
    ) -> None:
        super().__init__(parent)
        self.download_url = download_url
        self.version = version
        self.expected_size = expected_size
        self._is_cancelled = False

    def cancel(self) -> None:
        """Yêu cầu dừng việc tải xuống."""
        self._is_cancelled = True

    def run(self) -> None:
        final_path = get_cached_installer_path(self.version)
        part_path = final_path.with_suffix(".exe.part")

        try:
            req = Request(
                self.download_url,
                headers={"User-Agent": f"OmniGrab-Updater/{APP_VERSION}"},
            )
            # Timeout 20s cho handshake ban đầu
            with urlopen(req, timeout=20) as response:
                total_bytes = self.expected_size
                header_len = response.headers.get("Content-Length")
                if header_len and header_len.isdigit():
                    total_bytes = int(header_len)

                downloaded_bytes = 0
                chunk_size = 64 * 1024  # 64 KB
                start_time = time.time()
                last_emit_time = start_time
                last_emit_bytes = 0

                with open(part_path, "wb") as f_out:
                    while True:
                        if self._is_cancelled:
                            break

                        chunk = response.read(chunk_size)
                        if not chunk:
                            break

                        f_out.write(chunk)
                        downloaded_bytes += len(chunk)

                        now = time.time()
                        # Phát tín hiệu tiến độ cách nhau tối thiểu 100ms
                        if (now - last_emit_time) >= 0.12 or (total_bytes > 0 and downloaded_bytes >= total_bytes):
                            elapsed = now - last_emit_time
                            bytes_diff = downloaded_bytes - last_emit_bytes
                            speed_bps = (bytes_diff / elapsed) if elapsed > 0 else 0.0

                            eta_text = "--"
                            if speed_bps > 0 and total_bytes > downloaded_bytes:
                                eta_secs = (total_bytes - downloaded_bytes) / speed_bps
                                eta_text = format_eta(eta_secs)

                            self.progress.emit(
                                downloaded_bytes,
                                total_bytes,
                                speed_bps,
                                eta_text,
                            )
                            last_emit_time = now
                            last_emit_bytes = downloaded_bytes

            if self._is_cancelled:
                try:
                    if part_path.is_file():
                        part_path.unlink()
                except OSError:
                    pass
                self.cancelled.emit()
                return

            # Kiểm tra kích thước hoàn tất
            final_size = part_path.stat().st_size
            if total_bytes > 0 and final_size < total_bytes:
                raise ValueError(
                    f"File tải về chưa trọn vẹn ({format_size(final_size)} / {format_size(total_bytes)})."
                )

            # Đổi tên file tạm .part thành file .exe chính thức
            if final_path.is_file():
                try:
                    final_path.unlink()
                except OSError:
                    pass
            part_path.rename(final_path)

            self.finished.emit(str(final_path))

        except (URLError, TimeoutError, OSError, ValueError) as exc:
            try:
                if part_path.is_file():
                    part_path.unlink()
            except OSError:
                pass
            if not self._is_cancelled:
                self.error.emit(f"Lỗi tải bản cập nhật: {exc}")


def launch_silent_update_and_restart(
    installer_path: str | Path,
    app_exe_path: Optional[str | Path] = None,
) -> bool:
    """
    Thực thi tiến trình cập nhật tự động (Silent Update):
    1. Sinh script PowerShell chạy nền độc lập.
    2. Chờ tiến trình OmniGrab hiện tại tắt hẳn để giải phóng toàn bộ file locks.
    3. Chạy bộ cài Inno Setup với cờ /SILENT /SP- /NORESTART /CLOSEAPPLICATIONS.
    4. Tự động khởi động lại OmniGrab mới sau khi bộ cài đặt hoàn tất.
    5. Đóng ứng dụng hiện tại.
    """
    inst_p = Path(installer_path).resolve()
    if not inst_p.is_file():
        return False

    # Xác định đường dẫn file .exe của OmniGrab để khởi động lại
    if app_exe_path:
        target_exe = Path(app_exe_path).resolve()
    elif getattr(sys, "frozen", False):
        target_exe = Path(sys.executable).resolve()
    else:
        # Chế độ mã nguồn Python (dev): Trỏ vào thư mục cài đặt tiêu chuẩn hoặc exe đã build
        target_exe = (
            Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
            / "OmniGrab"
            / "OmniGrab.exe"
        ).resolve()

    updates_dir = get_updates_dir()
    script_path = updates_dir / "apply_update.ps1"

    # Script PowerShell tự trị chạy nền
    ps_content = """# OmniGrab Autonomous Auto-Updater
param(
    [int]$AppPid,
    [string]$InstallerPath,
    [string]$AppExePath
)

# 1. Chờ ứng dụng OmniGrab hiện tại tắt hoàn toàn để không khóa file
if ($AppPid -gt 0) {
    try {
        Wait-Process -Id $AppPid -Timeout 20 -ErrorAction SilentlyContinue
    } catch {}
}
Start-Sleep -Milliseconds 800

# 2. Chạy bộ cài đặt Inno Setup ở chế độ im lặng (/SILENT)
# /SILENT: Hiển thị thanh tiến trình cài đặt sạch, không bắt bấm Next/Next
# /SP-: Bỏ qua xác nhận bắt đầu cài đặt
# /NORESTART: Không khởi động lại máy tính
# /CLOSEAPPLICATIONS: Tự động đóng tiến trình nếu còn lưu luyến
$installedOk = $false
try {
    $proc = Start-Process -FilePath $InstallerPath -ArgumentList "/SILENT /SP- /NORESTART /CLOSEAPPLICATIONS" -Verb RunAs -PassThru
    if ($proc) {
        $proc.WaitForExit()
        if ($proc.ExitCode -eq 0) {
            $installedOk = $true
        }
    }
} catch {
    # Người dùng chọn 'No' ở bảng phân quyền UAC hoặc lỗi ngoài ý muốn
    $installedOk = $false
}

# 3. Khởi động lại ứng dụng OmniGrab
Start-Sleep -Milliseconds 600
if (Test-Path $AppExePath) {
    Start-Process -FilePath $AppExePath
}

# 4. Dọn dẹp file cài đặt tạm sau 5 giây
Start-Sleep -Seconds 5
try {
    Remove-Item -Path $InstallerPath -Force -ErrorAction SilentlyContinue
} catch {}
"""

    try:
        script_path.write_text(ps_content, encoding="utf-8")
    except OSError:
        return False

    # Chạy PowerShell ở chế độ tách biệt hoàn toàn (Detached Process) không cửa sổ
    current_pid = os.getpid()

    # Cờ Windows để tạo tiến trình độc lập không có console window
    DETACHED_PROCESS = 0x00000008
    CREATE_NO_WINDOW = 0x08000000
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    flags = DETACHED_PROCESS | CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP

    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-WindowStyle",
        "Hidden",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-AppPid",
        str(current_pid),
        "-InstallerPath",
        str(inst_p),
        "-AppExePath",
        str(target_exe),
    ]

    try:
        subprocess.Popen(
            cmd,
            creationflags=flags,
            close_fds=True,
        )
    except Exception:
        return False

    # Đóng ứng dụng ngay để tiến trình cài đặt tiến hành cập nhật
    app = QApplication.instance()
    if app is not None:
        app.quit()
    else:
        sys.exit(0)

    return True

