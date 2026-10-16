"""
core/security.py - Module bảo vệ mã nguồn và tính toàn vẹn (Anti-Reverse Engineering)
"""

import sys
import os
import shutil
import hashlib
from typing import Optional, Tuple

def get_base_path() -> str:
    """
    Lấy đường dẫn gốc của ứng dụng an toàn cho cả khi chạy script (.py),
    khi đóng gói bằng PyInstaller (_MEIPASS) và khi đóng gói Nuitka.
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller tạo ra _MEIPASS
        if hasattr(sys, '_MEIPASS'):
            return sys._MEIPASS
        # Nuitka onefile bung các file tài nguyên ra thư mục tạm NUITKA_ONEFILE_DIRECTORY
        if 'NUITKA_ONEFILE_DIRECTORY' in os.environ and os.path.isdir(os.environ['NUITKA_ONEFILE_DIRECTORY']):
            return os.environ['NUITKA_ONEFILE_DIRECTORY']
        # Nuitka standalone hoặc chạy trực tiếp thư mục
        return os.path.dirname(sys.executable)
    # Chạy từ script Python bình thường
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_app_dir() -> str:
    """
    Lấy thư mục cài đặt thực tế của ứng dụng (nơi chứa file .exe hoặc thư mục gốc dự án).
    Khác với get_base_path() (có thể trỏ vào _internal của PyInstaller khi chạy onedir),
    hàm này luôn đảm bảo trỏ tới thư mục ứng dụng ngoài cùng.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def setup_ffmpeg_environment() -> Tuple[str, str]:
    """
    Tự động quét và phát hiện ffmpeg.exe & ffprobe.exe trong tất cả các thư mục tiềm năng:
    1. Thư mục chứa file exe (dist/OmniGrab hoặc Program Files/OmniGrab)
    2. Thư mục _internal của PyInstaller (sys._MEIPASS hoặc exe/_internal)
    3. Thư mục gốc dự án khi chạy mã nguồn
    4. Thư mục tools/ffmpeg/bin, tools/ffmpeg, tools/
    5. Biến môi trường PATH hiện tại
    
    Tự động đưa thư mục chứa binary vào đầu biến PATH để yt-dlp, pydub,
    faster-whisper, ffmpeg subprocess... luôn chạy được ngay lập tức mà không cần cài thêm gì.
    
    Returns:
        (ffmpeg_path, ffprobe_path)
    """
    candidate_dirs: list[str] = []

    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        if exe_dir and exe_dir not in candidate_dirs:
            candidate_dirs.append(exe_dir)
        exe_internal = os.path.join(exe_dir, "_internal")
        if os.path.isdir(exe_internal) and exe_internal not in candidate_dirs:
            candidate_dirs.append(exe_internal)

    base_p = get_base_path()
    if base_p and base_p not in candidate_dirs:
        candidate_dirs.append(base_p)
    base_internal = os.path.join(base_p, "_internal")
    if os.path.isdir(base_internal) and base_internal not in candidate_dirs:
        candidate_dirs.append(base_internal)

    proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if proj_dir and proj_dir not in candidate_dirs:
        candidate_dirs.append(proj_dir)

    for sub in [
        os.path.join(proj_dir, "tools", "ffmpeg", "bin"),
        os.path.join(proj_dir, "tools", "ffmpeg"),
        os.path.join(proj_dir, "tools"),
    ]:
        if os.path.isdir(sub) and sub not in candidate_dirs:
            candidate_dirs.append(sub)

    ffmpeg_bin = ""
    ffprobe_bin = ""

    # Quét tìm ffmpeg
    for c_dir in candidate_dirs:
        if not c_dir or not os.path.isdir(c_dir):
            continue
        p = os.path.join(c_dir, "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
        if os.path.isfile(p):
            ffmpeg_bin = os.path.abspath(p)
            break
    if not ffmpeg_bin:
        found_ff = shutil.which("ffmpeg")
        if found_ff:
            ffmpeg_bin = os.path.abspath(found_ff)

    # Quét tìm ffprobe
    for c_dir in candidate_dirs:
        if not c_dir or not os.path.isdir(c_dir):
            continue
        p = os.path.join(c_dir, "ffprobe.exe" if sys.platform == "win32" else "ffprobe")
        if os.path.isfile(p):
            ffprobe_bin = os.path.abspath(p)
            break
    if not ffprobe_bin:
        found_probe = shutil.which("ffprobe")
        if found_probe:
            ffprobe_bin = os.path.abspath(found_probe)

    # Đưa các thư mục chứa ffmpeg/ffprobe lên đầu PATH
    dirs_to_add: list[str] = []
    if ffmpeg_bin:
        d1 = os.path.dirname(ffmpeg_bin)
        if d1 not in dirs_to_add:
            dirs_to_add.append(d1)
    if ffprobe_bin:
        d2 = os.path.dirname(ffprobe_bin)
        if d2 not in dirs_to_add:
            dirs_to_add.append(d2)

    for d in reversed(dirs_to_add):
        curr_path = os.environ.get("PATH", "")
        if d not in curr_path.split(os.pathsep):
            os.environ["PATH"] = d + os.pathsep + curr_path

    if ffmpeg_bin:
        os.environ["FFMPEG_BINARY"] = ffmpeg_bin
        os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_bin
    if ffprobe_bin:
        os.environ["FFPROBE_BINARY"] = ffprobe_bin

    return ffmpeg_bin, ffprobe_bin


def get_resource_path(relative_path: str) -> str:
    """Trả về đường dẫn tuyệt đối an toàn tới một tài nguyên tĩnh."""
    return os.path.join(get_base_path(), relative_path)


def _check_debugger() -> bool:
    """
    Phát hiện các debugger cơ bản đang móc vào Python runtime.
    """
    # Nếu sys.gettrace() trả về khác None, có thể đang bị theo dõi
    gettrace = getattr(sys, 'gettrace', None)
    if gettrace is not None and gettrace():
        return True
    
    # Kiểm tra một số biến môi trường phổ biến khi debug
    if 'PYDEVD_USE_FRAME_EVAL' in os.environ or 'PYDEVD_LOAD_VALUES_ASYNC' in os.environ:
        return True
        
    return False


def _verify_file_integrity(filepath: str, expected_sha256: Optional[str] = None) -> bool:
    """
    Kiểm tra tính toàn vẹn của một file bằng mã băm SHA256.
    (Ví dụ kiểm tra ffmpeg.exe không bị thay thế bằng trojan).
    """
    if not os.path.exists(filepath):
        return False
        
    if not expected_sha256:
        # Nếu chưa có mã băm kì vọng, chỉ kiểm tra file tồn tại
        return True
        
    sha256_hash = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest() == expected_sha256
    except Exception:
        return False


def run_security_checks() -> None:
    """
    Chạy các bước kiểm tra an ninh cơ bản trước khi khởi động ứng dụng.
    Nếu phát hiện vi phạm, thoát chương trình ngay lập tức.
    """
    # 1. Anti-Debugging
    if _check_debugger():
        print("[BAO MAT] Phat hien cong cu xam nhap (Debugger). Dong ung dung.")
        sys.exit(1)
        
    # 2. Kiểm tra toàn vẹn tài nguyên cơ bản (ví dụ icon ứng dụng)
    # (Trong dự án thực tế, bạn sẽ lấy mã SHA256 chuẩn và so sánh)
    icon_path = get_resource_path("assets/icon.png")
    if os.path.exists(icon_path):
        # Có thể thêm logic verify_file_integrity ở đây
        pass
        
    # 3. Chống hook ctypes cơ bản (tùy chọn)
    pass
