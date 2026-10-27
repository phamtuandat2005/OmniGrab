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
from typing import Optional, Tuple

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

    def _locate(bin_name: str) -> Optional[Path]:
        candidates = [
            ROOT_DIR / bin_name,
            ROOT_DIR / "tools" / "ffmpeg" / "bin" / bin_name,
            ROOT_DIR / "tools" / bin_name,
            Path("C:/ProgramData/chocolatey/lib/ffmpeg-full/tools/ffmpeg/bin") / bin_name,
            Path("C:/ProgramData/chocolatey/lib/ffmpeg/tools/ffmpeg/bin") / bin_name,
            Path("C:/ProgramData/chocolatey/bin") / bin_name,
            Path("C:/tools/ffmpeg/bin") / bin_name,
            Path("C:/Program Files/FFmpeg/bin") / bin_name,
        ]
        for c in candidates:
            if c.is_file() and c.stat().st_size > 100_000:
                return c
        found = shutil.which(bin_name)
        if found:
            p = Path(found)
            if p.is_file():
                return p
        return None

    ffmpeg_src = _locate("ffmpeg.exe")
    if not ffmpeg_src:
        log("Không tìm thấy ffmpeg.exe trong thư mục gốc, tools/ffmpeg/bin, hoặc PATH hệ thống!", "ERROR")
        sys.exit(1)

    ffprobe_src = _locate("ffprobe.exe")
    if not ffprobe_src:
        log("Không tìm thấy ffprobe.exe trong thư mục gốc, tools/ffmpeg/bin, hoặc PATH hệ thống!", "ERROR")
        sys.exit(1)

    # Đảm bảo ffmpeg.exe và ffprobe.exe luôn có mặt ngay tại thư mục gốc dự án cho PyInstaller spec
    root_ffmpeg = ROOT_DIR / "ffmpeg.exe"
    if not root_ffmpeg.is_file() or root_ffmpeg.stat().st_size != ffmpeg_src.stat().st_size:
        try:
            shutil.copy2(ffmpeg_src, root_ffmpeg)
            ffmpeg_src = root_ffmpeg
        except Exception:
            pass

    root_ffprobe = ROOT_DIR / "ffprobe.exe"
    if not root_ffprobe.is_file() or root_ffprobe.stat().st_size != ffprobe_src.stat().st_size:
        try:
            shutil.copy2(ffprobe_src, root_ffprobe)
            ffprobe_src = root_ffprobe
        except Exception:
            pass

    log(f"Đã xác nhận FFmpeg: {ffmpeg_src}", "SUCCESS")
    log(f"Đã xác nhận FFprobe: {ffprobe_src}", "SUCCESS")
    return ffmpeg_src, ffprobe_src


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


def run_nuitka() -> None:
    log("Bắt đầu biên dịch toàn diện sang mã máy C++ bằng Nuitka (Bảo vệ bản quyền & Chống dịch ngược)...")
    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--assume-yes-for-downloads",
        "--jobs=2",
        "--low-memory",
        "--enable-plugin=pyqt6",
        "--enable-plugin=playwright",
        "--include-module=PyQt6.QtMultimedia",
        "--include-module=PyQt6.QtMultimediaWidgets",
        "--include-module=PyQt6.QtSvg",
        "--include-module=PyQt6.sip",
        "--include-package=ui",
        "--include-package=core",
        "--nofollow-import-to=yt_dlp.extractor.lazy_extractors",
        "--include-package-data=yt_dlp",
        "--include-package-data=f2",
        "--include-package-data=curl_cffi",
        "--include-package-data=faster_whisper",
        "--include-package-data=ctranslate2",
        f"--windows-icon-from-ico={ROOT_DIR / 'assets' / 'icon.ico'}",
        f"--include-data-dir={ROOT_DIR / 'assets'}=assets",
        "--windows-company-name=OmniGrab",
        "--windows-product-name=OmniGrab",
        f"--windows-file-version={VERSION}.0",
        f"--windows-product-version={VERSION}.0",
        "--windows-file-description=OmniGrab Video Downloader & AI Dubbing",
        f"--output-dir={ROOT_DIR / 'dist'}",
        "--output-filename=OmniGrab.exe",
        "--windows-disable-console",
        "--remove-output",
        "--lto=no",
        "main.py",
    ]
    log(f"Thực thi lệnh: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT_DIR))
    if result.returncode != 0:
        log("Biên dịch Nuitka C++ thất bại! Vui lòng kiểm tra log lỗi bên trên.", "ERROR")
        sys.exit(result.returncode)

    # Nuitka --standalone thường sinh thư mục dist/main.dist hoặc dist/OmniGrab.dist
    candidates = [ROOT_DIR / "dist" / "main.dist", ROOT_DIR / "dist" / "OmniGrab.dist"]
    if (ROOT_DIR / "dist").is_dir():
        for p in (ROOT_DIR / "dist").glob("*.dist"):
            if p not in candidates:
                candidates.append(p)
    for candidate in candidates:
        if candidate.is_dir() and candidate.resolve() != DIST_DIR.resolve():
            if DIST_DIR.exists():
                shutil.rmtree(DIST_DIR, ignore_errors=True)
            candidate.rename(DIST_DIR)
            log(f"Đã chuẩn hóa thư mục build Nuitka -> {DIST_DIR}", "SUCCESS")
            break

    # Đảm bảo file thực thi có tên OmniGrab.exe trong DIST_DIR
    if DIST_DIR.is_dir():
        main_exe = DIST_DIR / "main.exe"
        omnigrab_exe = DIST_DIR / "OmniGrab.exe"
        if main_exe.is_file() and not omnigrab_exe.is_file():
            main_exe.rename(omnigrab_exe)

    log("Biên dịch Nuitka C++ hoàn tất thành công!", "SUCCESS")


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

    # 4. Sao chép runtime Playwright Chromium & Whisper model vào DIST_DIR nếu chưa có
    if PLAYWRIGHT_RUNTIME.is_dir():
        target_pw = DIST_DIR / "playwright-browsers"
        if not target_pw.exists():
            log(f"Sao chép runtime Playwright vào {target_pw}...", "INFO")
            shutil.copytree(PLAYWRIGHT_RUNTIME, target_pw, dirs_exist_ok=True)

    if WHISPER_RUNTIME.is_dir():
        target_wh = DIST_DIR / "models" / "faster-whisper-base"
        if not target_wh.exists():
            log(f"Sao chép runtime Whisper model vào {target_wh}...", "INFO")
            shutil.copytree(WHISPER_RUNTIME, target_wh, dirs_exist_ok=True)

    # 5. Làm mới bộ nhớ đệm icon của Windows
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


def auto_bump_version(bump_kind: str) -> str:
    """Tự động tăng version, ghi vào file và trả về version mới.
    
    Args:
        bump_kind: 'patch' | 'minor' | 'major' | 'none'
    Returns:
        Version mới (string), hoặc version hiện tại nếu bump_kind='none'
    """
    bump_script = ROOT_DIR / "tools" / "bump_version.py"
    if not bump_script.is_file():
        log("Không tìm thấy tools/bump_version.py, bỏ qua bước tăng version.", "WARN")
        return VERSION

    result = subprocess.run(
        [sys.executable, str(bump_script), bump_kind, "--ci", "--commit"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log(f"Lỗi khi tăng version: {result.stderr}", "ERROR")
        sys.exit(result.returncode)

    # Parse version mới từ output
    import re
    for line in result.stdout.splitlines():
        m = re.search(r"new_version=([\d]+\.[\d]+\.[\d]+)", line)
        if m:
            return m.group(1)

    # Fallback: đọc lại từ file
    from importlib import reload
    import core.version as _ver_mod
    reload(_ver_mod)
    return _ver_mod.APP_VERSION


def main() -> None:
    ensure_venv()

    # ------------------------------------------------------------------ #
    # 1. Phân tích đối số dòng lệnh                                        #
    # ------------------------------------------------------------------ #
    args = sys.argv[1:]

    # Engine đóng gói
    engine = "nuitka"
    if "--pyinstaller" in args or os.environ.get("BUILD_ENGINE", "").lower() == "pyinstaller":
        engine = "pyinstaller"
    elif "--nuitka" in args or os.environ.get("BUILD_ENGINE", "").lower() == "nuitka":
        engine = "nuitka"

    # Bump version (--bump / --bump-minor / --bump-major)
    bump_kind = "none"
    if "--bump" in args or "--bump-patch" in args:
        bump_kind = "patch"
    elif "--bump-minor" in args:
        bump_kind = "minor"
    elif "--bump-major" in args:
        bump_kind = "major"
    # Cho phép --bump=minor, --bump=major, --bump=patch
    for arg in args:
        if arg.startswith("--bump="):
            bump_kind = arg.split("=", 1)[1].strip().lower()
            break

    # ------------------------------------------------------------------ #
    # 2. Tự động tăng version nếu được yêu cầu                            #
    # ------------------------------------------------------------------ #
    global VERSION
    if bump_kind != "none":
        log(f"Tự động tăng version: {VERSION} -> ({bump_kind.upper()})...", "INFO")
        new_ver = auto_bump_version(bump_kind)
        VERSION = new_ver
        log(f"Version mới: {VERSION}", "SUCCESS")
    else:
        log(f"Giữ nguyên version hiện tại: {VERSION}", "INFO")

    print("=" * 64)
    print(f"      OmniGrab v{VERSION} - HE THONG DONG GOI [{engine.upper()}]")
    print("=" * 64)

    # ------------------------------------------------------------------ #
    # 3. Quy trình đóng gói chính                                          #
    # ------------------------------------------------------------------ #
    ffmpeg_src, ffprobe_src = check_prerequisites()
    prepare_runtime()
    clean_previous_builds()

    if engine == "pyinstaller":
        run_pyinstaller()
    else:
        run_nuitka()

    verify_and_copy_binaries(ffmpeg_src, ffprobe_src)
    build_portable_zip()
    build_installer()

    print("\n" + "=" * 64)
    print("                    HOAN TAT DONG GOI!")
    print("=" * 64)
    print(f"1. Thu muc chay truc tiep (Standalone App):")
    print(f"   -> {DIST_DIR / 'OmniGrab.exe'}")
    print(f"2. File cai dat cho nguoi dung cuoi (Installer Setup):")
    print(f"   -> {OUT_INSTALLER_DIR / f'OmniGrab.Setup.{VERSION}.exe'}")
    print(f"3. Ban nen khong can cai dat (Portable ZIP):")
    print(f"   -> {OUT_INSTALLER_DIR / f'OmniGrab_v{VERSION}_Portable.zip'}")
    print("=" * 64)
    print("Nguoi dung tai file ve cai dat hoac giai nen la chay duoc ngay!")
    print("Da tich hop FFmpeg, FFprobe, Qt6, AI dubbing va tat ca thu vien!\n")


if __name__ == "__main__":
    main()

