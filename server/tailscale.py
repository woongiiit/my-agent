"""Tailscale IP 탐지 및 연결 정보 유틸리티."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class TailscaleInfo:
    installed: bool
    connected: bool
    ipv4: str | None
    hostname: str | None
    backend_state: str | None


def _run_tailscale(args: list[str], timeout: int = 5) -> subprocess.CompletedProcess[str] | None:
    exe = shutil.which("tailscale")
    if not exe:
        # Windows 기본 설치 경로
        default = r"C:\Program Files\Tailscale\tailscale.exe"
        if os.path.isfile(default):
            exe = default
        else:
            return None

    try:
        return subprocess.run(
            [exe, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError, UnicodeDecodeError):
        return None


def get_tailscale_info() -> TailscaleInfo:
    """Tailscale 설치·연결 상태와 IPv4를 반환합니다."""
    version = _run_tailscale(["version"])
    if version is None:
        return TailscaleInfo(
            installed=False,
            connected=False,
            ipv4=None,
            hostname=None,
            backend_state=None,
        )

    ip_result = _run_tailscale(["ip", "-4"])
    ipv4 = None
    if ip_result and ip_result.returncode == 0 and ip_result.stdout:
        candidate = ip_result.stdout.strip()
        if re.match(r"^100\.\d+\.\d+\.\d+$", candidate):
            ipv4 = candidate

    status_result = _run_tailscale(["status", "--json"])
    hostname = None
    backend_state = None
    connected = ipv4 is not None

    if status_result and status_result.returncode == 0 and status_result.stdout:
        try:
            import json

            data = json.loads(status_result.stdout)
            self_info = data.get("Self", {})
            hostname = self_info.get("DNSName") or self_info.get("HostName")
            backend_state = self_info.get("BackendState") or data.get("BackendState")
            connected = backend_state == "Running" and ipv4 is not None
            if backend_state in ("NeedsLogin", "Stopped"):
                connected = False
        except (json.JSONDecodeError, AttributeError):
            pass

    # JSON 실패 시 텍스트 status 폴백
    if not hostname:
        text_status = _run_tailscale(["status"])
        if text_status and text_status.returncode == 0 and text_status.stdout:
            for line in text_status.stdout.splitlines():
                if line.strip().startswith("#"):
                    # 예: # health: ...
                    continue
                if "\t" in line:
                    parts = line.split("\t")
                    if len(parts) >= 2 and parts[0].strip() == ipv4:
                        hostname = parts[1].strip().split()[0]
                        break

    return TailscaleInfo(
        installed=True,
        connected=connected,
        ipv4=ipv4,
        hostname=hostname.rstrip(".") if hostname else None,
        backend_state=backend_state,
    )


def build_server_urls(port: int) -> dict:
    """LAN / Tailscale 접속 URL 후보를 생성합니다."""
    info = get_tailscale_info()
    urls: dict = {
        "tailscale": None,
        "tailscale_hostname": None,
        "recommended": None,
        "tailscale_installed": info.installed,
        "tailscale_connected": info.connected,
    }

    if info.ipv4:
        base = f"http://{info.ipv4}:{port}"
        urls["tailscale"] = base
        urls["recommended"] = base

    if info.hostname:
        urls["tailscale_hostname"] = f"http://{info.hostname}:{port}"

    return urls
