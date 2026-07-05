"""PC 앱/게임 실행 도구."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

MAPLE_STORY_PATH = os.getenv(
    "MAPLE_STORY_PATH",
    r"C:\Nexon\MapleStory\MapleStory.exe",
)
# railway | local — Railway에서는 로컬 워커로 위임
DEPLOYMENT_MODE = os.getenv("DEPLOYMENT_MODE", "local").lower()


def _launch_maple_local() -> dict:
    path = Path(MAPLE_STORY_PATH)
    if not path.exists():
        return {
            "success": False,
            "message": (
                f"게임 경로를 찾을 수 없습니다: {path}. "
                ".env의 MAPLE_STORY_PATH를 확인하세요."
            ),
        }

    subprocess.Popen([str(path)], shell=True)
    return {"success": True, "message": "메이플스토리를 실행했습니다."}


def _dispatch_to_worker(command: str, payload: dict | None = None) -> dict:
    from server.worker_hub import worker_hub

    if not worker_hub.has_worker:
        return {
            "success": False,
            "message": (
                "로컬 PC 워커가 연결되어 있지 않습니다. "
                "PC에서 `python -m worker.main`을 실행하세요."
            ),
        }

    import asyncio
    import concurrent.futures

    coro = worker_hub.dispatch(command, payload)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    if loop.is_running():
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=35)

    return asyncio.run(coro)


def launch_maple() -> dict:
    """메이플스토리를 실행합니다."""
    if DEPLOYMENT_MODE == "railway":
        return _dispatch_to_worker("launch_maple")
    return _launch_maple_local()


def launch_app(app_name: str) -> dict:
    """
    등록된 앱을 실행합니다.

    Args:
        app_name: 실행할 앱 이름 (예: maple, 메이플)
    """
    normalized = app_name.strip().lower()
    aliases = {"maple", "메이플", "메이플스토리", "maplestory"}

    if normalized in aliases:
        return launch_maple()

    if DEPLOYMENT_MODE == "railway":
        return _dispatch_to_worker("launch_app", {"app_name": app_name})

    return {
        "success": False,
        "message": f"'{app_name}' 앱을 찾을 수 없습니다. 지원: maple(메이플스토리)",
    }
