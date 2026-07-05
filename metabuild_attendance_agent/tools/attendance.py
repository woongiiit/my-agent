"""메타빌드 그룹웨어 출퇴근 자동화 도구."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum

from dotenv import load_dotenv
from playwright.sync_api import Page, sync_playwright

load_dotenv()

GW_BASE_URL = os.getenv("GW_BASE_URL", "https://gw.metabuild.co.kr")
GW_USER_ID = os.getenv("GW_USER_ID", "")
GW_PASSWORD = os.getenv("GW_PASSWORD", "")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"


class AttendanceAction(str, Enum):
    CLOCK_IN = "clock_in"
    CLOCK_OUT = "clock_out"


@dataclass
class AttendanceResult:
    success: bool
    action: str
    message: str
    clock_in_time: str | None = None
    already_done: bool = False


def _validate_credentials() -> None:
    if not GW_USER_ID or not GW_PASSWORD:
        raise ValueError(
            "GW_USER_ID, GW_PASSWORD 환경변수가 필요합니다. .env 파일을 확인하세요."
        )


def _login(page: Page) -> None:
    page.goto(GW_BASE_URL, wait_until="networkidle", timeout=60_000)

    # 로그인 페이지로 리다이렉트될 때까지 대기
    page.wait_for_url("**/login/**", timeout=30_000)

    # 다우오피스 계열 그룹웨어 공통 패턴
    id_input = page.locator(
        'input[name="userId"], input[name="id"], input[id="userId"], '
        'input[type="text"]:visible'
    ).first
    pw_input = page.locator(
        'input[name="password"], input[name="passwd"], input[type="password"]'
    ).first

    id_input.wait_for(state="visible", timeout=15_000)
    id_input.fill(GW_USER_ID)
    pw_input.fill(GW_PASSWORD)

    # Login 버튼 (접근성 이름 또는 텍스트)
    login_btn = page.get_by_role("button", name="Login").or_(
        page.get_by_text("Login", exact=False)
    )
    login_btn.first.click()

    # 메인 화면 로딩 대기
    page.wait_for_load_state("networkidle", timeout=60_000)
    page.wait_for_timeout(2_000)


def _get_attendance_widget(page: Page):
    """출퇴근 위젯 영역을 찾습니다."""
    # 스크린샷 기준: '출근', '퇴근', '출근완료' 텍스트가 있는 위젯
    widget = page.locator("text=출근").locator("xpath=ancestor::*[contains(@class,'')][1]")
    if widget.count() == 0:
        widget = page.locator("body")
    return page


def _read_status(page: Page) -> dict:
    """현재 출퇴근 상태를 읽습니다."""
    body_text = page.locator("body").inner_text()

    clocked_in = "출근완료" in body_text
    clock_in_time = None

    if clocked_in:
        # 출근 시간은 위젯 왼쪽 영역에 HH:MM 형태로 표시됨
        import re

        match = re.search(r"(\d{2}:\d{2})\s*\n?\s*출근완료", body_text)
        if match:
            clock_in_time = match.group(1)

    return {
        "clocked_in": clocked_in,
        "clock_in_time": clock_in_time,
        "body_preview": body_text[:500],
    }


def _click_attendance(page: Page, action: AttendanceAction) -> AttendanceResult:
    status = _read_status(page)

    if action == AttendanceAction.CLOCK_IN:
        if status["clocked_in"]:
            return AttendanceResult(
                success=True,
                action="clock_in",
                message="이미 출근 처리되어 있습니다.",
                clock_in_time=status["clock_in_time"],
                already_done=True,
            )
        # 출근 버튼 클릭 (출근완료가 아닌 '출근' 영역)
        clock_in_area = page.locator("text=출근").filter(has_not_text="출근완료").first
        if clock_in_area.count() == 0:
            clock_in_area = page.get_by_text("출근", exact=True).first
        clock_in_area.click()
        page.wait_for_timeout(2_000)

        new_status = _read_status(page)
        if new_status["clocked_in"]:
            return AttendanceResult(
                success=True,
                action="clock_in",
                message="출근 처리 완료",
                clock_in_time=new_status["clock_in_time"],
            )
        return AttendanceResult(
            success=False,
            action="clock_in",
            message="출근 버튼을 클릭했으나 출근완료 상태로 변경되지 않았습니다.",
        )

    # 퇴근
    clock_out_btn = page.get_by_text("퇴근", exact=True).first
    clock_out_btn.wait_for(state="visible", timeout=10_000)
    clock_out_btn.click()
    page.wait_for_timeout(2_000)

    return AttendanceResult(
        success=True,
        action="clock_out",
        message="퇴근 처리 완료",
        clock_in_time=status["clock_in_time"],
    )


def run_attendance(action: AttendanceAction) -> dict:
    """
    그룹웨어에 로그인 후 출근 또는 퇴근을 처리합니다.

    Args:
        action: 'clock_in' (출근) 또는 'clock_out' (퇴근)

    Returns:
        처리 결과 dict (success, message, clock_in_time 등)
    """
    _validate_credentials()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="ko-KR",
        )
        page = context.new_page()

        try:
            _login(page)
            _get_attendance_widget(page)
            result = _click_attendance(page, action)
            return {
                "success": result.success,
                "action": result.action,
                "message": result.message,
                "clock_in_time": result.clock_in_time,
                "already_done": result.already_done,
            }
        except Exception as exc:
            return {
                "success": False,
                "action": action.value,
                "message": f"오류 발생: {exc}",
            }
        finally:
            browser.close()


def clock_in() -> dict:
    """출근 처리를 수행합니다."""
    return run_attendance(AttendanceAction.CLOCK_IN)


def clock_out() -> dict:
    """퇴근 처리를 수행합니다."""
    return run_attendance(AttendanceAction.CLOCK_OUT)


def get_attendance_status() -> dict:
    """현재 출퇴근 상태만 조회합니다 (클릭 없음)."""
    _validate_credentials()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()
        try:
            _login(page)
            status = _read_status(page)
            return {"success": True, **status}
        except Exception as exc:
            return {"success": False, "message": str(exc)}
        finally:
            browser.close()
