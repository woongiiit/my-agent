"""메타빌드 그룹웨어 출퇴근 ADK 에이전트."""

from google.adk.agents.llm_agent import Agent

from .tools.attendance import clock_in, clock_out, get_attendance_status

root_agent = Agent(
    model="gemini-flash-latest",
    name="metabuild_attendance_agent",
    description="메타빌드 그룹웨어(gw.metabuild.co.kr) 출퇴근을 처리하는 에이전트",
    instruction="""
당신은 메타빌드 그룹웨어 출퇴근 자동화 에이전트입니다.

사용자 요청에 따라 적절한 도구를 호출하세요:
- 출근이 필요하면 clock_in 도구 사용
- 퇴근이 필요하면 clock_out 도구 사용
- 현재 상태 확인이 필요하면 get_attendance_status 도구 사용

도구 실행 결과를 사용자에게 명확하게 전달하세요.
이미 출근 완료된 경우 중복 처리하지 않았음을 알려주세요.
""",
    tools=[clock_in, clock_out, get_attendance_status],
)
