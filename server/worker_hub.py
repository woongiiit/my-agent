"""Railway ↔ 로컬 PC 워커 연결 허브."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field

from fastapi import WebSocket

logger = logging.getLogger(__name__)

WORKER_SECRET = os.getenv("WORKER_SECRET", "")


@dataclass
class WorkerHub:
    """연결된 로컬 워커를 관리하고 명령을 위임합니다."""

    _workers: dict[str, WebSocket] = field(default_factory=dict)
    _pending: dict[str, asyncio.Future] = field(default_factory=dict)

    def verify_secret(self, secret: str | None) -> bool:
        if not WORKER_SECRET:
            return False
        return secret == WORKER_SECRET

    @property
    def has_worker(self) -> bool:
        return bool(self._workers)

    async def register(self, worker_id: str, websocket: WebSocket) -> None:
        old = self._workers.get(worker_id)
        if old is not None:
            try:
                await old.close()
            except Exception:
                pass
        self._workers[worker_id] = websocket
        logger.info("Local worker registered: %s", worker_id)

    def unregister(self, worker_id: str) -> None:
        self._workers.pop(worker_id, None)
        logger.info("Local worker disconnected: %s", worker_id)

    async def dispatch(self, command: str, payload: dict | None = None, timeout: float = 30) -> dict:
        if not self._workers:
            return {
                "success": False,
                "message": (
                    "로컬 PC 워커가 연결되어 있지 않습니다. "
                    "PC에서 `python -m worker.main`을 실행하세요."
                ),
            }

        worker_id, ws = next(iter(self._workers.items()))
        request_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[request_id] = future

        await ws.send_json(
            {
                "type": "command",
                "request_id": request_id,
                "command": command,
                "payload": payload or {},
            }
        )

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result if isinstance(result, dict) else {"success": True, "message": str(result)}
        except asyncio.TimeoutError:
            return {"success": False, "message": "로컬 워커 응답 시간 초과"}
        finally:
            self._pending.pop(request_id, None)

    def resolve(self, request_id: str, result: dict) -> None:
        future = self._pending.get(request_id)
        if future and not future.done():
            future.set_result(result)


worker_hub = WorkerHub()
