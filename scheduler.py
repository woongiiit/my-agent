"""
정해진 시간에 출퇴근을 자동 실행하는 스케줄러.

ADK 에이전트 없이 도구를 직접 호출합니다.
(스케줄 작업은 LLM 판단이 필요 없으므로 도구만 실행하는 것이 안정적입니다.)

사용법:
    python scheduler.py
"""

from __future__ import annotations

import logging
import os
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from metabuild_attendance_agent.tools.attendance import clock_in, clock_out

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _parse_time(env_key: str, default: str) -> tuple[str, str]:
    raw = os.getenv(env_key, default)
    hour, minute = raw.split(":")
    return hour, minute


def job_clock_in() -> None:
    logger.info("출근 작업 시작")
    result = clock_in()
    logger.info("출근 결과: %s", result)


def job_clock_out() -> None:
    logger.info("퇴근 작업 시작")
    result = clock_out()
    logger.info("퇴근 결과: %s", result)


def main() -> None:
    in_hour, in_minute = _parse_time("CLOCK_IN_TIME", "08:50")
    out_hour, out_minute = _parse_time("CLOCK_OUT_TIME", "18:00")

    scheduler = BlockingScheduler(timezone="Asia/Seoul")

    scheduler.add_job(
        job_clock_in,
        CronTrigger(hour=in_hour, minute=in_minute, timezone="Asia/Seoul"),
        id="clock_in",
        name="출근",
    )
    scheduler.add_job(
        job_clock_out,
        CronTrigger(hour=out_hour, minute=out_minute, timezone="Asia/Seoul"),
        id="clock_out",
        name="퇴근",
    )

    logger.info("스케줄러 시작 (출근 %s:%s, 퇴근 %s:%s)", in_hour, in_minute, out_hour, out_minute)
    logger.info("종료: Ctrl+C")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러 종료")
        sys.exit(0)


if __name__ == "__main__":
    main()
