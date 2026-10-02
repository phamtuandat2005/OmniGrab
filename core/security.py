"""
core/security.py - Module bảo vệ mã nguồn và tính toàn vẹn (Anti-Reverse Engineering)
"""

import sys
import os
import hashlib
from typing import Optional

def get_base_path() -> str:
    """
    Lấy đường dẫn gốc của ứng dụng an toàn cho cả khi chạy script (.py),
    khi đóng gói bằng PyInstaller (_MEIPASS) và khi đóng gói Nuitka.
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller tạo ra _MEIPASS, Nuitka có thể không có nhưng getattr(sys, 'frozen') = True
        if hasattr(sys, '_MEIPASS'):
            return sys._MEIPASS
        # Nuitka standalone onefile thường bung ra temp dir giống PyInstaller hoặc chạy trực tiếp thư mục
        return os.path.dirname(sys.executable)
    # Chạy từ script Python bình thường
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
