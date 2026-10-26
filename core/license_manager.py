"""
core/license_manager.py — OmniGrab License System (Chuan VSS-License-Manager)

Co che:
  - Xac thuc chu ky so RSA-2048 / SHA256 / PKCS1v15 (offline 100%).
  - Khoa cung theo ma may tinh (Hardware Binding) dinh dang OG-XXXX-XXXX-XXXX.
  - Quan ly 10 luot dung thu mien phi.
  - Luu tru license key vao ~/.omnigrab_license.dat.
  - Luu tru so luot dung thu vao ~/.omnigrab_trial.dat.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Tuple

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.exceptions import InvalidSignature
    _CRYPTO_OK = True
except ImportError:
    _CRYPTO_OK = False


_LICENSE_FILE = Path.home() / ".omnigrab_license.dat"
_TRIAL_FILE   = Path.home() / ".omnigrab_trial.dat"
_TRIAL_TOTAL  = 10


class LicenseManager:
    """Quan ly ban quyen OmniGrab theo chuan VSS-License-Manager."""

    _instance: Optional["LicenseManager"] = None
    _cached_status: Optional[Tuple[bool, str, str, int]] = None

    def __new__(cls) -> "LicenseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ------------------------------------------------------------------
    # 1. MA MAY TINH (MACHINE ID)
    # ------------------------------------------------------------------

    def get_machine_id(self) -> str:
        """
        Tra ve ma may da luu de khong doi sau khi Windows cap nhat.

        Neu day la lan chay dau cua phien ban co luu ma, uu tien khoi phuc
        MID tu license cu da ky so; neu khong co thi tao MID theo cach cu,
        luu lai va tai su dung cho cac lan sau.
        """
        cached = getattr(self, "_machine_id_cache", None)
        if cached:
            return cached

        for path in self._machine_id_storage_paths():
            try:
                machine_id = path.read_text(encoding="ascii").strip().upper()
            except (OSError, UnicodeError):
                continue
            if self._is_valid_machine_id(machine_id):
                self._machine_id_cache = machine_id
                # Replicate a per-user copy into the machine-wide location
                # when possible, so other Windows accounts get the same ID.
                self._save_machine_id(machine_id)
                return machine_id

        machine_id = self._get_machine_id_from_saved_license()
        if not machine_id:
            raw = self._read_hardware_uuid()
            digest = hashlib.sha256(raw.encode()).hexdigest().upper()
            part = digest[:12]
            machine_id = f"OG-{part[0:4]}-{part[4:8]}-{part[8:12]}"

        self._machine_id_cache = machine_id
        self._save_machine_id(machine_id)
        return machine_id

    @staticmethod
    def _is_valid_machine_id(machine_id: str) -> bool:
        return re.fullmatch(r"OG-[0-9A-F]{4}(?:-[0-9A-F]{4}){2}", machine_id) is not None

    @staticmethod
    def _machine_id_storage_paths() -> list[Path]:
        """Machine-wide path first, then a writable per-user fallback."""
        paths: list[Path] = []
        program_data = os.environ.get("PROGRAMDATA")
        local_app_data = os.environ.get("LOCALAPPDATA")
        if program_data:
            paths.append(Path(program_data) / "OmniGrab" / "machine_id.dat")
        if local_app_data:
            paths.append(Path(local_app_data) / "OmniGrab" / "machine_id.dat")
        paths.append(Path.home() / ".omnigrab_machine_id")
        return paths

    @classmethod
    def _save_machine_id(cls, machine_id: str) -> None:
        """Persist the same ID wherever this account has write access."""
        for path in cls._machine_id_storage_paths():
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(machine_id + "\n", encoding="ascii")
            except OSError:
                continue

    def _get_machine_id_from_saved_license(self) -> str:
        """Migrate the MID from a previously issued, cryptographically valid key."""
        try:
            key_input = _LICENSE_FILE.read_text(encoding="utf-8").strip()
            raw = base64.b64decode(key_input, validate=True)
            bundle = json.loads(raw.decode("utf-8"))
            payload, payload_bytes, signature = self._unpack_bundle(bundle)
            self._load_public_key().verify(
                signature,
                payload_bytes,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            machine_id = str(payload.get("mid", "")).strip().upper()
            return machine_id if self._is_valid_machine_id(machine_id) else ""
        except Exception:
            return ""

    def _read_hardware_uuid(self) -> str:
        """Doc UUID phan cung tu he thong."""
        system = platform.system()

        if system == "Windows":
            commands = (
                ["wmic", "csproduct", "get", "uuid"],
                [
                    "powershell", "-NoProfile", "-NonInteractive", "-Command",
                    "(Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID",
                ],
            )
            for command in commands:
                try:
                    result = subprocess.run(
                        command, capture_output=True, text=True, timeout=8
                    )
                    for line in result.stdout.splitlines():
                        value = line.strip()
                        if self._is_valid_hardware_uuid(value):
                            return value
                except Exception:
                    continue

        elif system == "Linux":
            for path in ["/sys/class/dmi/id/product_uuid", "/etc/machine-id"]:
                try:
                    val = Path(path).read_text().strip()
                    if val:
                        return val
                except Exception:
                    pass

        elif system == "Darwin":
            try:
                result = subprocess.run(
                    ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                    capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.splitlines():
                    if "IOPlatformUUID" in line:
                        val = line.split("=")[-1].strip().strip('"')
                        if val:
                            return val
            except Exception:
                pass

        return str(uuid.getnode())

    @staticmethod
    def _is_valid_hardware_uuid(value: str) -> bool:
        normalized = value.strip().upper()
        return (
            bool(normalized)
            and normalized not in {"UUID", "N/A", "NONE", "UNKNOWN"}
            and normalized not in {
                "00000000-0000-0000-0000-000000000000",
                "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF",
            }
        )

    # ------------------------------------------------------------------
    # 2. KHOA CONG KHAI RSA
    # ------------------------------------------------------------------

    def _get_public_key_path(self) -> Optional[Path]:
        """Tim file public_key.pem theo thu tu uu tien."""
        candidates: list[Path] = []

        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir / "assets" / "public_key.pem")
        candidates.append(exe_dir / "public_key.pem")

        if sys.argv and sys.argv[0]:
            try:
                argv0_dir = Path(sys.argv[0]).resolve().parent
                candidates.append(argv0_dir / "assets" / "public_key.pem")
                candidates.append(argv0_dir / "public_key.pem")
            except Exception:
                pass

        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "assets" / "public_key.pem")
            candidates.append(Path(meipass) / "public_key.pem")

        try:
            this_dir = Path(__file__).resolve().parent.parent
            candidates.append(this_dir / "assets" / "public_key.pem")
        except Exception:
            pass

        candidates.append(Path.cwd() / "assets" / "public_key.pem")
        candidates.append(Path.cwd() / "public_key.pem")

        for p in candidates:
            if p.exists():
                return p
        return None

    def _load_public_key(self):
        """Nap va tra ve doi tuong RSAPublicKey."""
        if not _CRYPTO_OK:
            raise RuntimeError(
                "Thu vien 'cryptography' chua duoc cai dat.\n"
                "Chay: pip install cryptography>=41.0.0"
            )
        pem_path = self._get_public_key_path()
        if pem_path is None:
            raise RuntimeError(
                "Khong tim thay file 'assets/public_key.pem'.\n"
                "Hay dat file khoa cong khai vao thu muc assets/ cua ung dung."
            )
        pem_data = pem_path.read_bytes()
        try:
            return serialization.load_pem_public_key(pem_data)
        except Exception:
            # Ho tro tu dong giai ma neu file public_key.pem bi ma hoa Fernet tu VSS-Key-Generator
            try:
                from cryptography.fernet import Fernet
                _FERNET_KEY = b'G12qY-pL0Z8UjH3k4tJ7gR_5VbO9XFqA3D6lC_fM1wY='
                decrypted = Fernet(_FERNET_KEY).decrypt(pem_data)
                return serialization.load_pem_public_key(decrypted)
            except Exception:
                raise

    def _unpack_bundle(self, bundle: dict) -> Tuple[dict, bytes, bytes]:
        """
        Giai ma va dong nhat hoa bundle tu License Key (Chuan VSS).
        Ho tro ca dinh dang payload la dict (chuan VSS) hoac chuoi Base64/JSON.
        """
        if "payload" not in bundle or "sig" not in bundle:
            raise ValueError("Thiếu payload hoặc chữ ký (sig)")

        raw_payload = bundle["payload"]
        sig_b64 = str(bundle["sig"]).strip()
        sig_bytes = base64.b64decode(sig_b64)

        if isinstance(raw_payload, dict):
            payload = raw_payload
            payload_bytes = json.dumps(
                payload, separators=(',', ':'), sort_keys=True, ensure_ascii=False
            ).encode("utf-8")
        elif isinstance(raw_payload, str):
            try:
                dec = base64.b64decode(raw_payload)
                payload = json.loads(dec.decode("utf-8"))
                payload_bytes = dec
            except Exception:
                payload = json.loads(raw_payload)
                payload_bytes = json.dumps(
                    payload, separators=(',', ':'), sort_keys=True, ensure_ascii=False
                ).encode("utf-8")
        else:
            raise ValueError("Định dạng payload không hợp lệ")

        return payload, payload_bytes, sig_bytes

    # ------------------------------------------------------------------
    # 3. XAC THUC LICENSE KEY (Chuan VSS)
    # ------------------------------------------------------------------

    def verify_and_save_key(self, key_input: str) -> Tuple[bool, str]:
        """
        Xac thuc chuoi License Key (Base64) theo chuan VSS.

        Returns:
            (True, thong_bao_thanh_cong) hoac (False, thong_bao_loi).
        """
        key_input = key_input.strip().strip('"').strip("'")
        if not key_input:
            return False, "Vui lòng dán mã kích hoạt vào ô nhập."

        # Giai ma Base64
        try:
            raw = base64.b64decode(key_input, validate=True)
            bundle = json.loads(raw.decode("utf-8"))
        except Exception:
            return False, (
                "Mã kích hoạt không hợp lệ.\n"
                "Vui lòng kiểm tra lại — mã phải là chuỗi Base64 đúng định dạng."
            )

        # Lay payload va chu ky
        try:
            payload, payload_bytes, sig_bytes = self._unpack_bundle(bundle)
        except Exception as e:
            return False, (
                f"Cấu trúc mã kích hoạt bị lỗi: {e}\n"
                "Hãy sao chép toàn bộ mã và dán lại."
            )

        # Xac thuc chu ky RSA-SHA256
        try:
            public_key = self._load_public_key()
        except RuntimeError as e:
            return False, str(e)

        try:
            public_key.verify(
                sig_bytes,
                payload_bytes,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except InvalidSignature:
            return False, (
                "Chữ ký số không hợp lệ!\n"
                "Mã kích hoạt đã bị chỉnh sửa hoặc không được cấp bởi hệ thống này."
            )
        except Exception as e:
            return False, f"Lỗi xác thực chữ ký: {e}"

        # Kiem tra Machine ID
        key_mid: str = payload.get("mid", "")
        my_mid: str  = self.get_machine_id()
        if key_mid != my_mid:
            return False, (
                "M\u00e3 k\u00edch ho\u1ea1t kh\u00f4ng thu\u1ed9c v\u1ec1 m\u00e1y t\u00ednh n\u00e0y!\n\n"
                f"  M\u00e3 m\u00e1y trong key : {key_mid}\n"
                f"  M\u00e3 m\u00e1y c\u1ee7a b\u1ea1n   : {my_mid}\n\n"
                "Vui l\u00f2ng li\u00ean h\u1ec7 Admin \u0111\u1ec3 \u0111\u01b0\u1ee3c c\u1ea5p key \u0111\u00fang m\u00e3 m\u00e1y."
            )

        # Kiem tra ngay het han
        exp_str: str = payload.get("exp", "")
        if exp_str:
            try:
                exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
                if exp_date < date.today():
                    return False, (
                        f"B\u1ea3n quy\u1ec1n \u0111\u00e3 h\u1ebft h\u1ea1n v\u00e0o ng\u00e0y {exp_str}.\n"
                        "Vui l\u00f2ng gia h\u1ea1n \u0111\u1ec3 ti\u1ebfp t\u1ee5c s\u1eed d\u1ee5ng \u0111\u1ea7y \u0111\u1ee7 t\u00ednh n\u0103ng."
                    )
            except ValueError:
                return False, f"Ng\u00e0y h\u1ebft h\u1ea1n kh\u00f4ng \u0111\u00fang \u0111\u1ecbnh d\u1ea1ng: {exp_str}"

        # Luu key hop le
        try:
            _LICENSE_FILE.write_text(key_input, encoding="utf-8")
        except Exception as e:
            return False, f"Kh\u00f4ng th\u1ec3 l\u01b0u b\u1ea3n quy\u1ec1n: {e}"

        LicenseManager._cached_status = None

        customer = payload.get("customer", "Kh\u00e1ch h\u00e0ng")
        exp_display = exp_str if exp_str else "V\u0129nh vi\u1ec5n"
        return True, (
            f"\U0001f389 K\u00edch ho\u1ea1t b\u1ea3n quy\u1ec1n PRO th\u00e0nh c\u00f4ng!\n\n"
            f"  Ch\u1ee7 s\u1edf h\u1eefu : {customer}\n"
            f"  H\u1ea1n s\u1eed d\u1ee5ng : {exp_display}\n"
            f"  M\u00e3 thi\u1ebft b\u1ecb : {my_mid}"
        )

    # ------------------------------------------------------------------
    # 4. DOC TRANG THAI HIEN TAI
    # ------------------------------------------------------------------

    def get_status(self, use_cache: bool = True) -> Tuple[bool, str, str, int]:
        """
        Kiem tra va tra ve trang thai ban quyen hien tai.

        Returns:
            Tuple (is_licensed, status_text, expire_date, trial_remaining)
        """
        if use_cache and LicenseManager._cached_status is not None:
            return LicenseManager._cached_status

        result = self._compute_status()
        LicenseManager._cached_status = result
        return result

    def _compute_status(self) -> Tuple[bool, str, str, int]:
        if _LICENSE_FILE.exists():
            key_input = _LICENSE_FILE.read_text(encoding="utf-8").strip()
            ok, msg = self._verify_saved_key(key_input)
            if ok:
                exp = self._extract_exp(key_input)
                exp_display = exp if exp else "V\u0129nh vi\u1ec5n"
                return (
                    True,
                    f"Bản quyền PRO — Hạn dùng: {exp_display}",
                    exp,
                    _TRIAL_TOTAL,
                )
            else:
                try:
                    _LICENSE_FILE.unlink(missing_ok=True)
                except Exception:
                    pass

        remaining = self._get_trial_remaining()
        if remaining > 0:
            status_text = f"Dùng thử: còn {remaining}/{_TRIAL_TOTAL} lượt"
        else:
            status_text = f"Hết lượt dùng thử (0/{_TRIAL_TOTAL})"
        return (
            False,
            status_text,
            "",
            remaining,
        )

    def _verify_saved_key(self, key_input: str) -> Tuple[bool, str]:
        """Xac thuc key da luu (khong ghi file lai)."""
        try:
            raw = base64.b64decode(key_input.strip().strip('"').strip("'"), validate=True)
            bundle = json.loads(raw.decode("utf-8"))
            payload, payload_bytes, sig_bytes = self._unpack_bundle(bundle)

            public_key = self._load_public_key()
            public_key.verify(
                sig_bytes,
                payload_bytes,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )

            if payload.get("mid", "") != self.get_machine_id():
                return False, "Sai mã máy"

            exp_str = payload.get("exp", "")
            if exp_str:
                exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
                if exp_date < date.today():
                    return False, "Đã hết hạn"

            return True, "OK"
        except Exception as e:
            return False, str(e)

    def _extract_exp(self, key_input: str) -> str:
        """Trich xuat ngay het han tu key da luu."""
        try:
            raw = base64.b64decode(key_input.strip(), validate=True)
            bundle = json.loads(raw.decode("utf-8"))
            payload, _, _ = self._unpack_bundle(bundle)
            return payload.get("exp", "")
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # 5. QUAN LY LUOT DUNG THU
    # ------------------------------------------------------------------

    def _get_trial_remaining(self) -> int:
        """Doc so luot dung thu con lai tu file."""
        try:
            if _TRIAL_FILE.exists():
                data = json.loads(_TRIAL_FILE.read_text(encoding="utf-8"))
                used = int(data.get("used", 0))
                return max(0, _TRIAL_TOTAL - used)
        except Exception:
            pass
        return _TRIAL_TOTAL

    def consume_trial(self) -> int:
        """
        Tru 1 luot dung thu sau moi video tai thanh cong.

        Returns:
            So luot con lai sau khi tru.
        """
        try:
            used = 0
            if _TRIAL_FILE.exists():
                data = json.loads(_TRIAL_FILE.read_text(encoding="utf-8"))
                used = int(data.get("used", 0))
            used = min(used + 1, _TRIAL_TOTAL)
            _TRIAL_FILE.write_text(
                json.dumps({"used": used, "updated": datetime.now().isoformat()}),
                encoding="utf-8"
            )
            LicenseManager._cached_status = None
            return max(0, _TRIAL_TOTAL - used)
        except Exception:
            return self._get_trial_remaining()

    def is_trial_expired(self) -> bool:
        """Tra ve True neu da het luot dung thu va chua co ban quyen."""
        is_licensed, _, _, trial_remaining = self.get_status(use_cache=False)
        return not is_licensed and trial_remaining <= 0

    def invalidate_cache(self) -> None:
        """Xoa cache trang thai de buoc tinh lai lan sau."""
        LicenseManager._cached_status = None
