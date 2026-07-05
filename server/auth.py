"""에이전트 접근 인증 — Railway 환경변수 기반 ID/PW."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time

from fastapi import HTTPException

AGENT_USER_ID = os.getenv("AGENT_USER_ID", "")
AGENT_PASSWORD = os.getenv("AGENT_PASSWORD", "")
# 토큰 서명용 (미설정 시 AGENT_PASSWORD 사용)
AGENT_SECRET_KEY = os.getenv("AGENT_SECRET_KEY", "") or AGENT_PASSWORD
# 레거시: CHAT_API_TOKEN 직접 사용도 허용
CHAT_API_TOKEN = os.getenv("CHAT_API_TOKEN", "")

TOKEN_TTL_SECONDS = int(os.getenv("AGENT_TOKEN_TTL", str(60 * 60 * 24 * 7)))  # 7일


def _safe_compare(a: str, b: str) -> bool:
    return secrets.compare_digest(a.encode(), b.encode())


def verify_credentials(user_id: str, password: str) -> bool:
    if not AGENT_USER_ID or not AGENT_PASSWORD:
        return False
    return _safe_compare(user_id, AGENT_USER_ID) and _safe_compare(
        password, AGENT_PASSWORD
    )


def create_access_token(user_id: str) -> str:
    if not AGENT_SECRET_KEY:
        raise HTTPException(status_code=500, detail="AGENT_SECRET_KEY not configured")
    issued_at = int(time.time())
    payload = f"{user_id}:{issued_at}"
    signature = hmac.new(
        AGENT_SECRET_KEY.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}:{signature}"


def verify_access_token(token: str | None) -> bool:
    if not token:
        return False

    # 레거시 고정 토큰
    if CHAT_API_TOKEN and _safe_compare(token, CHAT_API_TOKEN):
        return True

    if not AGENT_SECRET_KEY:
        return not CHAT_API_TOKEN and not AGENT_USER_ID

    try:
        payload, signature = token.rsplit(":", 1)
        user_id, issued_at_str = payload.split(":", 1)
        issued_at = int(issued_at_str)
    except ValueError:
        return False

    expected = hmac.new(
        AGENT_SECRET_KEY.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not _safe_compare(signature, expected):
        return False

    if AGENT_USER_ID and not _safe_compare(user_id, AGENT_USER_ID):
        return False

    if time.time() - issued_at > TOKEN_TTL_SECONDS:
        return False

    return True


def require_token(token: str | None) -> None:
    if verify_access_token(token):
        return
    if not AGENT_USER_ID and not CHAT_API_TOKEN:
        return
    raise HTTPException(status_code=401, detail="Invalid credentials or token")
