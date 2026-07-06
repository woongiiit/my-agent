"""
출퇴근 도구 수동 실행 CLI.

사용법:
    python run_attendance.py clock_in
    python run_attendance.py clock_out
    python run_attendance.py status
"""

import asyncio
import sys

from metabuild_attendance_agent.tools.attendance import (
    clock_in,
    clock_out,
    get_attendance_status,
)

COMMANDS = {
    "clock_in": clock_in,
    "clock_out": clock_out,
    "status": get_attendance_status,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("사용법: python run_attendance.py [clock_in|clock_out|status]")
        sys.exit(1)

    cmd = sys.argv[1]
    result = asyncio.run(COMMANDS[cmd]())
    print(result)


if __name__ == "__main__":
    main()
