"""ADK Runner를 감싸 채팅 메시지를 처리합니다."""

from __future__ import annotations

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.utils.content_utils import extract_text_from_content
from google.genai import types

from root_agent.agent import root_agent

_session_service = InMemorySessionService()
_runner = Runner(
    agent=root_agent,
    app_name="root_agent",
    session_service=_session_service,
    auto_create_session=True,
)


async def run_chat(
    *,
    user_id: str,
    session_id: str,
    message: str,
) -> str:
    """사용자 메시지를 루트 에이전트에 전달하고 최종 응답 텍스트를 반환합니다."""
    content = types.Content(
        role="user",
        parts=[types.Part(text=message)],
    )

    final_text = ""
    async for event in _runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        if event.is_final_response() and event.content:
            text = extract_text_from_content(event.content)
            if text:
                final_text = text

    if final_text:
        return final_text

    return "요청을 처리했지만 텍스트 응답을 생성하지 못했습니다."
