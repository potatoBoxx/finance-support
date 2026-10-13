import pytest
from services.market_service import (
    fetch_market_indices,
    generate_3line_briefing,
    get_mock_indices,
    INDEX_SYMBOLS,
)
from services.news_service import fetch_stock_news

def test_fetch_market_indices():
    indices = fetch_market_indices()
    assert isinstance(indices, dict)
    for key in INDEX_SYMBOLS.keys():
        assert key in indices
        item = indices[key]
        assert "value" in item
        assert "change" in item
        assert "change_rate" in item
        assert "unit" in item
        assert item["value"] > 0

def test_generate_3line_briefing():
    mock_idx = get_mock_indices()
    briefing = generate_3line_briefing(mock_idx)
    assert isinstance(briefing, list)
    assert len(briefing) == 3
    categories = [b["category"] for b in briefing]
    assert "거시경제" in categories
    assert "시장심리" in categories
    assert "투자전략" in categories
    for b in briefing:
        assert len(b["summary"]) > 10
        assert "badge" in b

def test_fetch_stock_news():
    news = fetch_stock_news(["005930", "AAPL"])
    assert isinstance(news, list)
    assert len(news) > 0
    first = news[0]
    assert "ticker" in first
    assert "title" in first
    assert "publisher" in first
    assert "time" in first


def test_get_market_operation_status():
    from services.market_service import get_market_operation_status
    from zoneinfo import ZoneInfo
    from datetime import datetime

    status = get_market_operation_status()
    assert "current_time_kst" in status
    assert "current_time_us" in status
    assert "now_kst" in status
    assert "now_ny" in status
    assert "krx" in status
    assert "us" in status
    assert any(tz in status["current_time_us"] for tz in ["EDT", "EST"])

    # KRX 검증
    krx = status["krx"]
    assert "is_open" in krx
    assert "status_text" in krx
    assert "remaining_time" in krx
    assert "target_label" in krx
    assert "summary_text" in krx

    # US 검증
    us = status["us"]
    assert "is_open" in us
    assert "status_text" in us
    assert "remaining_time" in us
    assert "target_label" in us
    assert "summary_text" in us

    # 시나리오 테스트: 월요일 오전 10시 KST (국내 장중, 미국 장마감)
    kst_tz = ZoneInfo("Asia/Seoul")
    mon_open_krx = datetime(2026, 10, 5, 10, 0, 0, tzinfo=kst_tz)
    res_mon = get_market_operation_status(mon_open_krx)
    assert res_mon["krx"]["is_open"] is True
    assert "장중" in res_mon["krx"]["status_text"]
    assert res_mon["krx"]["target_label"] == "장종료까지"

    # 시나리오 테스트: 화요일 오후 4시 KST (국내 장마감)
    tue_close_krx = datetime(2026, 10, 6, 16, 0, 0, tzinfo=kst_tz)
    res_close = get_market_operation_status(tue_close_krx)
    assert res_close["krx"]["is_open"] is False
    assert res_close["krx"]["status_text"] == "장 마감"
    assert "개시까지" in res_close["krx"]["target_label"]

