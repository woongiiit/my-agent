"""
로컬 PC 워커 — Railway 서버에 연결해 PC 전용 명령을 실행합니다.

Railway(클라우드)에서는 Windows exe 실행 등이 불가하므로,
PC에서 이 워커를 실행하면 '메이플 켜줘' 같은 명령을 처리합니다.

사용법:
    python -m worker.main
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket

import websockets
from dotenv import load_dotenv

from root_agent.tools.apps import launch_app, launch_maple

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVER_URL = os.getenv("SERVER_URL", "http://127.0.0.1:8765").rstrip("/")
WORKER_SECRET = os.getenv("WORKER_SECRET", "")
WORKER_ID = os.getenv("WORKER_ID", socket.gethostname())


def _to_ws_url(http_url: str) -> str:
    if http_url.startswith("https://"):
        return "wss://" + http_url[len("https://") :] + "/ws/worker"
    if http_url.startswith("http://"):
        return "ws://" + http_url[len("http://") :] + "/ws/worker"
    return "ws://" + http_url + "/ws/worker"


async def _handle_command(command: str, payload: dict) -> dict:
    if command == "launch_maple":
        return launch_maple()
    if command == "launch_app":
        return launch_app(payload.get("app_name", ""))
    return {"success": False, "message": f"Unknown command: {command}"}


async def run_worker() -> None:
    if not WORKER_SECRET:
        raise SystemExit("WORKER_SECRET 환경변수가 필요합니다.")

    ws_url = _to_ws_url(SERVER_URL)
    query = f"secret={WORKER_SECRET}&worker_id={WORKER_ID}"
    connect_url = f"{ws_url}?{query}"

    while True:
        try:
            logger.info("Connecting to %s", SERVER_URL)
            async with websockets.connect(connect_url, ping_interval=20) as ws:
                logger.info("Connected as worker %s", WORKER_ID)
                async for raw in ws:
                    data = json.loads(raw)
                    if data.get("type") != "command":
                        continue

                    request_id = data.get("request_id")
                    command = data.get("command", "")
                    payload = data.get("payload") or {}

                    try:
                        result = await asyncio.to_thread(
                            _handle_command, command, payload
                        )
                    except Exception as exc:
                        result = {"success": False, "message": str(exc)}

                    await ws.send(
                        json.dumps(
                            {
                                "type": "result",
                                "request_id": request_id,
                                "result": result,
                            }
                        )
                    )
        except Exception as exc:
            logger.warning("Worker connection error: %s — retry in 5s", exc)
            await asyncio.sleep(5)


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
