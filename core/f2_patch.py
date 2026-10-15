"""
core/f2_patch.py - Tự động vá và bảo vệ thư viện f2 khi chạy dưới dạng file exe đóng gói (PyInstaller / Nuitka).

Vấn đề:
Khi đóng gói bằng Nuitka (--onefile) hoặc PyInstaller, các file phi mã nguồn (.yaml) trong f2/conf/
thường không được giải nén đúng cách vào thư mục tạm, dẫn đến lỗi:
    配置文件不存在 Filepath: ...\\f2\\conf\\conf.yaml
Lỗi này làm ứng dụng bị dừng đột ngột khi quét hoặc tải video từ Douyin.

Giải pháp:
Module này tự động can thiệp vào ConfigManager của f2 ngay trước khi f2 khởi tạo.
Nếu phát hiện file conf.yaml chưa có trên đĩa, nó sẽ tự động tạo file và nạp cấu hình mặc định,
đảm bảo ứng dụng chạy mượt mà 100% trong mọi môi trường (chạy source, PyInstaller, Nuitka).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_DEFAULT_F2_CONF_YAML = """f2:
  douyin:
    encryption: ab
    ttwid:
      url: https://ttwid.bytedance.com/ttwid/union/register/
      data: '{"region":"cn","aid":1768,"needFid":false,"service":"www.ixigua.com","migrate_info":{"ticket":"","source":"node"},"cbUrlProtocol":"https","union":true}'
    webid:
      url: https://mcs.zijieapi.com/webid?aid=6383&sdk_version=5.1.18_zip&device_platform=web
      body:
        app_id: 6383
        referer: https://www.douyin.com/
        url: https://www.douyin.com/
        user_agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0
        user_unique_id: ""
  tiktok:
    BaseRequestModel:
      browser:
        language: zh-CN
        name: Mozilla
        platform: Win32
        version: 5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36
      device:
        id: "7377772863376426514"
        platform: web_pc
      os: windows
      region: SG
      priority_region: ""
      webcast_language: zh-Hans
      tz_name: Asia/Hong_Kong
    headers:
      User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36
      Referer: https://www.tiktok.com/
    proxies:
      http:
      https:
    ttwid:
      url: https://www.tiktok.com/ttwid/check/
      data: '{"aid":1988,"service":"www.tiktok.com","union":false,"unionHost":"","needFid":false,"fid":"","migrate_priority":0}'
      cookie: ttwid=1%7C3uOVjidbOFBmdS6Aci5oeBb8Ta-HWpeyp2dvhl2Ib2E%7C1716637053%7C462867ee452aecd60a854225b854ff4498e9b99c13d4826a3e2a4e58a4c55134;
"""

_patched = False


def patch_f2_environment() -> bool:
    """
    Vá ConfigManager của f2 để tránh crash khi thiếu file conf.yaml.
    Hàm này an toàn và có thể gọi nhiều lần mà không gây tác dụng phụ.
    """
    global _patched
    if _patched:
        return True

    try:
        # pyrefly: ignore [missing-import]
        import f2
        # pyrefly: ignore [missing-import]
        import f2.utils.conf_manager as cm
        import yaml

        orig_load = cm.ConfigManager.load_config

        def safe_load_config(self) -> dict:
            if not self.filepath.exists():
                try:
                    self.filepath.parent.mkdir(parents=True, exist_ok=True)
                    self.filepath.write_text(_DEFAULT_F2_CONF_YAML, encoding="utf-8")
                except Exception:
                    pass

                try:
                    loaded = yaml.safe_load(_DEFAULT_F2_CONF_YAML) or {}
                    return self._replace_none(loaded)
                except Exception:
                    return {"f2": {"douyin": {"encryption": "ab"}}}

            return orig_load(self)

        cm.ConfigManager.load_config = safe_load_config
        _patched = True
        return True
    except Exception:
        return False


# Tự động vá ngay khi import module này
patch_f2_environment()
