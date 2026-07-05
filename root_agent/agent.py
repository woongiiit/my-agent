"""PC 루트 에이전트 — 모바일 채팅 앱에서 명령을 받아 도구를 실행합니다."""

from google.adk.agents.llm_agent import Agent

from metabuild_attendance_agent.tools.attendance import (
    clock_in,
    clock_out,
    get_attendance_status,
)
from root_agent.llm_config import create_llm
from root_agent.tools.apps import launch_app, launch_maple

root_agent = Agent(
    model=create_llm(),
    name="root_agent",
    description="사용자의 PC를 원격으로 제어하는 루트 에이전트",
    instruction="""
당신은 사용자의 PC를 제어하는 루트 에이전트입니다.
모바일 채팅 앱에서 온 명령을 이해하고 적절한 도구를 호출하세요.

사용 가능한 작업:
- 출근/퇴근: clock_in, clock_out, get_attendance_status
- 게임 실행: launch_maple 또는 launch_app (메이플, maple 등)

규칙:
- 요청 의도를 파악해 가장 적합한 도구 하나를 선택하세요.
- 도구 실행 결과를 짧고 명확한 한국어로 전달하세요.
- PC에서만 실행 가능한 작업임을 필요 시 안내하세요.
""",
    tools=[
        clock_in,
        clock_out,
        get_attendance_status,
        launch_maple,
        launch_app,
    ],
)
