"""
build_release.py - Script tự động hóa toàn diện quy trình đóng gói OmniGrab.

Quy trình tự động thực hiện:
1. Kiểm tra môi trường (Python 64-bit, venv, ffmpeg.exe, ffprobe.exe).
2. Chuẩn bị tài nguyên runtime (Playwright Chromium, mô hình Whisper base).
3. Dọn dẹp thư mục build/dist cũ.
4. Đóng gói ứng dụng thành file thực thi độc lập (PyInstaller với OmniGrab.spec).
5. Tích hợp đầy đủ FFmpeg và FFprobe vào cả thư mục gốc và _internal.
6. Đóng gói bản Portable (ZIP) sẵn sàng chia sẻ.
7. Biên dịch bộ cài đặt Windows chuyên nghiệp (.exe) bằng Inno Setup (nếu có).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from core.version import APP_VERSION

if sys.platform == "win32":
    try:
        if sys.stdout is not None:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr is not None:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


ROOT_DIR = Path(__file__).resolve().parent
DIST_DIR = ROOT_DIR / "dist" / "OmniGrab"
BUILD_DIR = ROOT_DIR / "build"
OUT_INSTALLER_DIR = ROOT_DIR / "dist_installer"
SPEC_FILE = ROOT_DIR / "OmniGrab.spec"
RUNTIME_DIR = ROOT_DIR / "build_runtime"
PLAYWRIGHT_RUNTIME = RUNTIME_DIR / "playwright-browsers"
WHISPER_RUNTIME = RUNTIME_DIR / "models" / "faster-whisper-base"

VERSION = APP_VERSION


def ensure_venv() -> None:
    """Tự động chuyển tiếp sang môi trường ảo (venv) nếu người dùng chạy bằng Python hệ thống."""
    venv_python = ROOT_DIR / "venv" / "Scripts" / "python.exe"
    if venv_python.is_file():
        try:
            current_py = Path(sys.executable).resolve()
            if current_py != venv_python.resolve():
                print(f"[INFO] Phát hiện đang chạy Python ngoài venv: {current_py}", flush=True)
                print(f"[INFO] Tự động chuyển tiếp thực thi sang: {venv_python}...", flush=True)
                res = subprocess.run([str(venv_python)] + sys.argv, cwd=str(ROOT_DIR))
                sys.exit(res.returncode)
        except Exception as e:
            print(f"[WARN] Không thể tự chuyển venv: {e}", flush=True)


def kill_conflicting_processes() -> None:
    """Tắt các tiến trình OmniGrab hoặc ffmpeg đang chạy ngầm làm khóa file trong thư mục dist."""
    if sys.platform == "win32":
        for proc in ["OmniGrab.exe", "ffmpeg.exe", "ffprobe.exe"]:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", proc],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception:
                pass


def log(msg: str, level: str = "INFO") -> None:
    prefixes = {
        "INFO": "[INFO] ",
        "SUCCESS": "[OK]   ",
        "WARN": "[WARN] ",
        "ERROR": "[LOI]  ",
    }
    print(f"{prefixes.get(level, '[INFO] ')}{msg}", flush=True)


def check_prerequisites() -> tuple[Path, Path]:
    log("Kiểm tra các thành phần bắt buộc...")

    if sys.version_info < (3, 10):
        log("Cần Python 3.10 trở lên để đóng gói!", "ERROR")
        sys.exit(1)

    import struct
    if struct.calcsize("P") != 8:
        log("Cần Python 64-bit để tạo bản phát hành Windows x64!", "ERROR")
        sys.exit(1)

    ffmpeg_path = ROOT_DIR / "ffmpeg.exe"
    ffprobe_path = ROOT_DIR / "ffprobe.exe"

    if not ffmpeg_path.is_file():
        alt = ROOT_DIR / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
        if alt.is_file():
            ffmpeg_path = alt
        else:
            log("Không tìm thấy ffmpeg.exe trong thư mục gốc hoặc tools/ffmpeg/bin!", "ERROR")
            sys.exit(1)

    if not ffprobe_path.is_file():
        alt = ROOT_DIR / "tools" / "ffmpeg" / "bin" / "ffprobe.exe"
        if alt.is_file():
            ffprobe_path = alt
        else:
            log("Không tìm thấy ffprobe.exe trong thư mục gốc hoặc tools/ffmpeg/bin!", "ERROR")
            sys.exit(1)

    log(f"Đã xác nhận FFmpeg: {ffmpeg_path}", "SUCCESS")
    log(f"Đã xác nhận FFprobe: {ffprobe_path}", "SUCCESS")
    return ffmpeg_path, ffprobe_path


def prepare_runtime() -> None:
    log("Chuẩn bị tài nguyên runtime (Chromium và Whisper)...")
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    PLAYWRIGHT_RUNTIME.mkdir(parents=True, exist_ok=True)
    WHISPER_RUNTIME.mkdir(parents=True, exist_ok=True)

    # 1. Chromium
    has_chrome = any(PLAYWRIGHT_RUNTIME.rglob("chrome.exe"))
    if not has_chrome:
        ms_playwright = Path(os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright"))
        copied = False
        if ms_playwright.is_dir():
            for d in sorted(ms_playwright.glob("chromium-*")):
                # Chỉ lấy thư mục chromium thật, bỏ qua headless shell
                if "headless" in d.name:
                    continue
                if (d / "chrome-win64" / "chrome.exe").is_file():
                    target = PLAYWRIGHT_RUNTIME / d.name
                    log(f"Sao chép Chromium ({d.name}) vào {target}...", "INFO")
                    shutil.copytree(d, target, dirs_exist_ok=True)
                    copied = True
                    break
        if not copied:
            log("Tải Chromium qua Playwright...", "INFO")
            env = os.environ.copy()
            env["PLAYWRIGHT_BROWSERS_PATH"] = str(PLAYWRIGHT_RUNTIME)
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], env=env, check=True)

    if not any(PLAYWRIGHT_RUNTIME.rglob("chrome.exe")):
        log("Không tìm thấy chrome.exe trong playwright-browsers!", "ERROR")
        sys.exit(1)
    log("Chromium đã sẵn sàng.", "SUCCESS")

    # 2. Whisper Model base
    if not (WHISPER_RUNTIME / "model.bin").is_file():
        log("Chuẩn bị mô hình Whisper base...", "INFO")
        from faster_whisper.utils import download_model
        download_model("base", output_dir=str(WHISPER_RUNTIME))

    if not (WHISPER_RUNTIME / "model.bin").is_file():
        log("Không tìm thấy model.bin của mô hình Whisper!", "ERROR")
        sys.exit(1)
    log("Mô hình Whisper base đã sẵn sàng.", "SUCCESS")


def clean_previous_builds() -> None:
    log("Dọn dẹp thư mục build cũ và tắt các tiến trình liên quan...")
    kill_conflicting_processes()
    for p in [BUILD_DIR, ROOT_DIR / "dist", ROOT_DIR / "dist_release", ROOT_DIR / "build_release_pyinstaller"]:
        if p.exists():
            try:
                shutil.rmtree(p, ignore_errors=True)
            except Exception as e:
                log(f"Không thể xóa hoàn toàn {p}: {e}", "WARN")
    OUT_INSTALLER_DIR.mkdir(parents=True, exist_ok=True)
    # Dọn dẹp các artifact cũ của phiên bản hiện tại để tránh file lock hoặc ghi đè lỗi
    for old_target in [
        OUT_INSTALLER_DIR / f"OmniGrab.Setup.{VERSION}.exe",
        OUT_INSTALLER_DIR / f"OmniGrab_v{VERSION}_Portable.zip",
    ]:
        if old_target.is_file():
            try:
                old_target.unlink()
            except Exception:
                pass
    log("Đã dọn dẹp xong.", "SUCCESS")


def run_pyinstaller() -> None:
    log("Bắt đầu đóng gói bằng PyInstaller (sử dụng OmniGrab.spec)...")
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        str(SPEC_FILE),
    ]
    log(f"Thực thi lệnh: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT_DIR))
    if result.returncode != 0:
        log("Đóng gói PyInstaller thất bại! Vui lòng kiểm tra lỗi bên trên.", "ERROR")
        sys.exit(result.returncode)
    log("Đóng gói PyInstaller thành công!", "SUCCESS")


def verify_and_copy_binaries(ffmpeg_src: Path, ffprobe_src: Path) -> None:
    log("Đồng bộ và xác nhận các thành phần trong gói phát hành...")

    if not DIST_DIR.exists():
        log(f"Không tìm thấy thư mục phân phối {DIST_DIR}!", "ERROR")
        sys.exit(1)

    exe_target = DIST_DIR / "OmniGrab.exe"
    if not exe_target.is_file():
        log(f"Không tìm thấy file thực thi {exe_target}!", "ERROR")
        sys.exit(1)

    # 1. Đảm bảo ffmpeg.exe và ffprobe.exe có mặt ở thư mục gốc (cạnh OmniGrab.exe)
    for src, name in [(ffmpeg_src, "ffmpeg.exe"), (ffprobe_src, "ffprobe.exe")]:
        dest_root = DIST_DIR / name
        if not dest_root.is_file():
            shutil.copy2(src, dest_root)
            log(f"Đã sao chép {name} -> {dest_root}", "SUCCESS")
        else:
            log(f"Đã có {name} tại thư mục gốc dist.", "SUCCESS")

    # 2. Đảm bảo ffmpeg.exe và ffprobe.exe cũng có mặt trong thư mục _internal (nếu có)
    internal_dir = DIST_DIR / "_internal"
    if internal_dir.is_dir():
        for src, name in [(ffmpeg_src, "ffmpeg.exe"), (ffprobe_src, "ffprobe.exe")]:
            dest_internal = internal_dir / name
            if not dest_internal.is_file():
                shutil.copy2(src, dest_internal)
                log(f"Đã sao chép {name} -> {dest_internal}", "SUCCESS")

    # 3. Đảm bảo assets có đủ icon
    assets_target = DIST_DIR / "assets"
    assets_target.mkdir(parents=True, exist_ok=True)
    for icon_name in ["icon.ico", "icon.png"]:
        src_ico = ROOT_DIR / "assets" / icon_name
        dest_ico = assets_target / icon_name
        if src_ico.is_file() and not dest_ico.is_file():
            shutil.copy2(src_ico, dest_ico)

    # 4. Làm mới bộ nhớ đệm icon của Windows
    try:
        subprocess.run(["ie4uinit.exe", "-show"], check=False)
    except Exception:
        pass


def find_iscc() -> Path | None:
    """Tìm trình biên dịch Inno Setup (ISCC.exe)."""
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 7" / "ISCC.exe",
        Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
        Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
        Path("C:/Program Files/Inno Setup 7/ISCC.exe"),
    ]
    for c in candidates:
        if c.is_file():
            return c

    found = shutil.which("ISCC")
    if found:
        return Path(found)
    return None


def build_installer() -> None:
    log("Kiểm tra trình biên dịch Inno Setup...")
    OUT_INSTALLER_DIR.mkdir(parents=True, exist_ok=True)
    iscc_path = find_iscc()
    if not iscc_path:
        log("Không tìm thấy Inno Setup (ISCC.exe). Bỏ qua bước tạo file cài đặt .exe.", "WARN")
        log("Người dùng có thể cài Inno Setup 6 để tự động tạo file setup.exe.", "WARN")
        return

    log(f"Tìm thấy Inno Setup: {iscc_path}", "SUCCESS")
    iss_file = ROOT_DIR / "setup.iss"
    if not iss_file.is_file():
        log(f"Không tìm thấy file kịch bản {iss_file}!", "ERROR")
        return

    log("Đang biên dịch Bộ cài đặt chuyên nghiệp (Inno Setup)...")
    cmd = [
        str(iscc_path),
        f"/DAppDistDir={DIST_DIR.parent}",
        f"/DMyAppVersion={VERSION}",
        str(iss_file),
    ]
    res = subprocess.run(cmd, cwd=str(ROOT_DIR))
    if res.returncode == 0:
        inst_target = OUT_INSTALLER_DIR / f"OmniGrab.Setup.{VERSION}.exe"
        if inst_target.is_file():
            mb_size = inst_target.stat().st_size / (1024 * 1024)
            log(f"Tạo bộ cài đặt thành công: {inst_target.name} ({mb_size:.1f} MB)", "SUCCESS")
        else:
            log(f"Đã biên dịch xong nhưng không tìm thấy {inst_target.name}!", "WARN")
    else:
        log("Biên dịch bộ cài đặt Inno Setup gặp lỗi!", "WARN")


def build_portable_zip() -> None:
    log("Đang đóng gói bản Portable (ZIP)...")
    OUT_INSTALLER_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = OUT_INSTALLER_DIR / f"OmniGrab_v{VERSION}_Portable.zip"
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(DIST_DIR):
                for f in files:
                    full_p = Path(root) / f
                    rel_p = Path("OmniGrab") / full_p.relative_to(DIST_DIR)
                    zf.write(full_p, rel_p)
        mb_size = zip_path.stat().st_size / (1024 * 1024)
        log(f"Tạo bản Portable ZIP thành công: {zip_path} ({mb_size:.1f} MB)", "SUCCESS")
    except Exception as e:
        log(f"Không thể nén file ZIP: {e}", "WARN")


def main() -> None:
    ensure_venv()

    print("=" * 64)
    print(f"      OmniGrab v{VERSION} - HỆ THỐNG ĐÓNG GÓI TỰ ĐỘNG CHUYÊN NGHIỆP")
    print("=" * 64)

    ffmpeg_src, ffprobe_src = check_prerequisites()
    prepare_runtime()
    clean_previous_builds()
    run_pyinstaller()
    verify_and_copy_binaries(ffmpeg_src, ffprobe_src)
    build_portable_zip()
    build_installer()

    print("\n" + "=" * 64)
    print("                    HOÀN TẤT ĐÓNG GÓI!")
    print("=" * 64)
    print(f"1. Thư mục chạy trực tiếp (Standalone App):")
    print(f"   -> {DIST_DIR / 'OmniGrab.exe'}")
    print(f"2. File cài đặt cho người dùng cuối (Installer Setup):")
    print(f"   -> {OUT_INSTALLER_DIR / f'OmniGrab.Setup.{VERSION}.exe'}")
    print(f"3. Bản nén không cần cài đặt (Portable ZIP):")
    print(f"   -> {OUT_INSTALLER_DIR / f'OmniGrab_v{VERSION}_Portable.zip'}")
    print("=" * 64)
    print("Người dùng tải file về cài đặt hoặc giải nén là chạy được ngay,")
    print("đã tích hợp đầy đủ FFmpeg, FFprobe, Qt6, AI dubbing và tất cả thư viện!\n")


if __name__ == "__main__":
    main()
