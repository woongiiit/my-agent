"""한화오션 주가 조회 및 수익률 계산 도구."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

HANWHA_OCEAN_TICKER = os.getenv("HANWHA_OCEAN_TICKER", "042660.KS")
HANWHA_OCEAN_AVG_PRICE = float(os.getenv("HANWHA_OCEAN_AVG_PRICE", "125571"))
YAHOO_CHART_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
)


def _fetch_current_price(ticker: str) -> tuple[float, str | None]:
    """Yahoo Finance chart API에서 현재가를 조회합니다."""
    url = YAHOO_CHART_URL.format(ticker=ticker)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; my-agent/1.0)"},
    )

    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())

    result = data.get("chart", {}).get("result")
    if not result:
        raise ValueError("주가 데이터를 찾을 수 없습니다.")

    meta = result[0].get("meta", {})
    price = meta.get("regularMarketPrice")
    if price is None:
        # 장 마감 후 등 fallback
        closes = result[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
        closes = [c for c in closes if c is not None]
        if closes:
            price = closes[-1]

    if price is None:
        raise ValueError("현재가를 확인할 수 없습니다.")

    currency = meta.get("currency", "KRW")
    market_time = meta.get("regularMarketTime")
    as_of = None
    if market_time:
        as_of = datetime.fromtimestamp(market_time, tz=timezone.utc).astimezone().strftime(
            "%Y-%m-%d %H:%M"
        )

    return float(price), as_of


def get_hanwha_ocean_profit(
    average_price: float | None = None,
) -> dict:
    """
    한화오션(042660) 현재 주가를 조회하고, 평균단가 대비 수익률을 계산합니다.

    Args:
        average_price: 평균 매수단가(원). 미입력 시 환경변수 HANWHA_OCEAN_AVG_PRICE 사용.

    Returns:
        현재가, 평균단가, 손익금, 수익률 등
    """
    avg = average_price if average_price is not None else HANWHA_OCEAN_AVG_PRICE

    try:
        current_price, as_of = _fetch_current_price(HANWHA_OCEAN_TICKER)
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, TimeoutError) as exc:
        return {
            "success": False,
            "message": f"한화오션 주가 조회 실패: {exc}",
            "ticker": HANWHA_OCEAN_TICKER,
        }

    profit_per_share = current_price - avg
    profit_rate = (profit_per_share / avg) * 100 if avg else 0.0
    status = "수익" if profit_per_share >= 0 else "손실"

    return {
        "success": True,
        "name": "한화오션",
        "ticker": HANWHA_OCEAN_TICKER,
        "current_price": round(current_price, 2),
        "average_price": round(avg, 2),
        "profit_per_share": round(profit_per_share, 2),
        "profit_rate_percent": round(profit_rate, 2),
        "status": status,
        "as_of": as_of,
        "message": (
            f"한화오션 현재가 {current_price:,.0f}원 (기준: {as_of or '최근 시세'}), "
            f"평균단가 {avg:,.0f}원 대비 "
            f"{'+' if profit_per_share >= 0 else ''}{profit_rate:.2f}% "
            f"({status} {abs(profit_per_share):,.0f}원/주)"
        ),
    }
