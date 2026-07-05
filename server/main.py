"""
모바일 채팅 앱 ↔ PC 루트 에이전트 서버.

로컬:  python -m server.main
Railway: Dockerfile / railway.toml (PORT 환경변수 사용)
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from server.agent_service import run_chat
from server.auth import (
    create_access_token,
    require_token,
    verify_credentials,
)
from server.tailscale import build_server_urls, get_tailscale_info
from server.worker_hub import worker_hub

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("PORT", os.getenv("SERVER_PORT", "8765")))
DEPLOYMENT_MODE = os.getenv("DEPLOYMENT_MODE", "local").lower()

MOBILE_DIR = Path(__file__).resolve().parent.parent / "mobile"

app = FastAPI(title="My Agent Chat Server", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    user_id: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user_id: str


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    user_id: str = "mobile_user"


class ChatResponse(BaseModel):
    reply: str
    session_id: str


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "agent": "root_agent",
        "deployment": DEPLOYMENT_MODE,
        "local_worker_connected": worker_hub.has_worker,
    }


@app.post("/api/login", response_model=LoginResponse)
async def login(body: LoginRequest) -> LoginResponse:
    """ID/PW 로그인 → 접근 토큰 발급."""
    if not verify_credentials(body.user_id, body.password):
        raise HTTPException(status_code=401, detail="Invalid user ID or password")
    token = create_access_token(body.user_id)
    return LoginResponse(token=token, user_id=body.user_id)


@app.get("/api/connection-info")
async def connection_info() -> dict:
    urls = build_server_urls(SERVER_PORT)
    ts = get_tailscale_info()
    return {
        "port": SERVER_PORT,
        "deployment": DEPLOYMENT_MODE,
        "local_worker_connected": worker_hub.has_worker,
        "tailscale": {
            "installed": ts.installed,
            "connected": ts.connected,
            "ipv4": ts.ipv4,
            "hostname": ts.hostname,
            "backend_state": ts.backend_state,
        },
        "urls": urls,
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat_http(
    body: ChatRequest,
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
) -> ChatResponse:
    require_token(x_api_token)

    session_id = body.session_id or str(uuid.uuid4())
    reply = await run_chat(
        user_id=body.user_id,
        session_id=session_id,
        message=body.message,
    )
    return ChatResponse(reply=reply, session_id=session_id)


@app.websocket("/ws/worker")
async def worker_websocket(websocket: WebSocket) -> None:
    """로컬 PC 워커 연결."""
    secret = websocket.query_params.get("secret")
    worker_id = websocket.query_params.get("worker_id", "default")

    if not worker_hub.verify_secret(secret):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    await worker_hub.register(worker_id, websocket)

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            if data.get("type") == "result":
                worker_hub.resolve(data.get("request_id", ""), data.get("result", {}))
    except WebSocketDisconnect:
        worker_hub.unregister(worker_id)


@app.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    try:
        require_token(token)
    except HTTPException:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    session_id = websocket.query_params.get("session_id") or str(uuid.uuid4())
    user_id = websocket.query_params.get("user_id") or "mobile_user"

    await websocket.send_json(
        {
            "type": "connected",
            "session_id": session_id,
            "message": "루트 에이전트에 연결되었습니다.",
        }
    )

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"message": raw}

            message = (payload.get("message") or "").strip()
            if not message:
                await websocket.send_json(
                    {"type": "error", "message": "빈 메시지는 처리할 수 없습니다."}
                )
                continue

            session_id = payload.get("session_id") or session_id
            user_id = payload.get("user_id") or user_id

            await websocket.send_json({"type": "typing", "status": True})

            try:
                reply = await run_chat(
                    user_id=user_id,
                    session_id=session_id,
                    message=message,
                )
                await websocket.send_json(
                    {
                        "type": "message",
                        "role": "assistant",
                        "message": reply,
                        "session_id": session_id,
                    }
                )
            except Exception as exc:
                logger.exception("Agent error")
                await websocket.send_json(
                    {"type": "error", "message": f"에이전트 오류: {exc}"}
                )
            finally:
                await websocket.send_json({"type": "typing", "status": False})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected (session=%s)", session_id)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(MOBILE_DIR / "index.html")


if MOBILE_DIR.exists():
    app.mount("/static", StaticFiles(directory=MOBILE_DIR), name="static")


def main() -> None:
    logger.info("Starting server on %s:%s (mode=%s)", SERVER_HOST, SERVER_PORT, DEPLOYMENT_MODE)

    if DEPLOYMENT_MODE == "local":
        urls = build_server_urls(SERVER_PORT)
        ts = get_tailscale_info()
        if ts.installed and ts.connected and urls.get("recommended"):
            logger.info("Tailscale URL: %s", urls["recommended"])

    uvicorn.run(
        "server.main:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
