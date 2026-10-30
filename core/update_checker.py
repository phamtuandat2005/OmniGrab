"""Helpers for checking OmniGrab releases published on GitHub."""

from __future__ import annotations

import re
from typing import Any, NamedTuple
from urllib.parse import urlparse

GITHUB_RELEASE_API_URL = "https://api.github.com/repos/phamtuandat2005/OmniGrab/releases/latest"
_INSTALLER_RE = re.compile(r"^OmniGrab\.Setup\.(\d+\.\d+\.\d+)\.exe$", re.IGNORECASE)
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


class ReleaseUpdate(NamedTuple):
    version: str
    download_url: str
    release_url: str
    notes: str
    size: int = 0


def _version_key(version: str) -> tuple[int, int, int]:
    if not _VERSION_RE.fullmatch(version):
        raise ValueError(f"Phiên bản không đúng định dạng x.y.z: {version}")
    parts = version.split(".")
    return int(parts[0]), int(parts[1]), int(parts[2])


def _is_github_https_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and parsed.hostname in {"github.com", "api.github.com"}


def find_release_update(release: Any, current_version: str) -> ReleaseUpdate | None:
    """Return the newest attached OmniGrab installer if it is newer than this app."""
    if not isinstance(release, dict):
        raise ValueError("GitHub trả về dữ liệu release không hợp lệ.")

    current_key = _version_key(current_version)
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise ValueError("Release mới nhất không có danh sách file tải xuống.")

    installers: list[tuple[tuple[int, int, int], str, str, int]] = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = asset.get("name")
        match = _INSTALLER_RE.fullmatch(name) if isinstance(name, str) else None
        if not match:
            continue
        version = match.group(1)
        download_url = asset.get("browser_download_url")
        if not _is_github_https_url(download_url):
            continue
        raw_size = asset.get("size")
        size_int = int(raw_size) if isinstance(raw_size, (int, float)) and raw_size > 0 else 0
        installers.append((_version_key(version), version, download_url, size_int))

    if not installers:
        raise ValueError(
            "Release mới nhất chưa đính kèm file OmniGrab.Setup.x.y.z.exe."
        )

    version_key, version, download_url, size_int = max(installers, key=lambda item: item[0])
    if version_key <= current_key:
        return None

    release_url = release.get("html_url")
    if not _is_github_https_url(release_url):
        raise ValueError("Release không có đường dẫn GitHub hợp lệ.")

    notes = release.get("body")
    return ReleaseUpdate(
        version=version,
        download_url=download_url,
        release_url=release_url,
        notes=notes.strip()[:1500] if isinstance(notes, str) and notes.strip() else "",
        size=size_int,
    )
