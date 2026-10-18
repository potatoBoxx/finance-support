import pytest
import pandas as pd
from services.portfolio_service import (
    calculate_portfolio_performance,
    get_live_price_map,
    format_quantity,
)

def test_calculate_portfolio_performance_profit_and_stop_loss():
    items = [
        {
            "id": "item-1",
            "market": "KRX",
            "ticker": "005930",
            "name": "삼성전자",
            "buy_price": 70000.0,
            "quantity": 10.0,
            "target_price": 80000.0,
            "stop_loss_price": 65000.0,
            "memo": "장기투자"
        },
        {
            "id": "item-2",
            "market": "US",
            "ticker": "AAPL",
            "name": "Apple Inc",
            "buy_price": 200.0,
            "quantity": 5.0,
            "target_price": 250.0,
            "stop_loss_price": 180.0,
            "memo": None
        }
    ]

    # 삼성전자는 손절가 65000 이하(64000)로 하락 -> 손절 경고(is_stop_loss=True)
    # 애플은 현재가 220으로 상승 -> 정상 수익(profit_rate=10.0%)
    price_map = {
        "005930": 64000.0,
        "AAPL": 220.0
    }

    # 환율 1300원 적용
    df, summary = calculate_portfolio_performance(items, price_map, usd_krw_rate=1300.0)

    assert len(df) == 2

    # 1. 삼성전자 검증 (국내 원화 기준)
    samsung = df[df["ticker"] == "005930"].iloc[0]
    assert bool(samsung["is_stop_loss"]) is True
    assert samsung["currency"] == "원"
    assert samsung["eval_amount"] == 640000.0
    assert samsung["eval_profit"] == -60000.0
    assert round(samsung["profit_rate"], 2) == -8.57
    assert round(samsung["target_rate"], 1) == 80.0
    assert samsung["quantity_display"] == "10주"

    # 2. 애플 검증 (미국 달러 기준)
    apple = df[df["ticker"] == "AAPL"].iloc[0]
    assert bool(apple["is_stop_loss"]) is False
    assert apple["currency"] == "$"
    assert apple["eval_amount"] == 1100.0
    assert apple["eval_profit"] == 100.0
    assert apple["profit_rate"] == 10.0
    assert round(apple["target_rate"], 1) == 88.0
    assert apple["quantity_display"] == "5주"

    # 3. 전체 요약 검증 (원화 환산 합산)
    # 투자원금: 700,000 + (1,000 * 1300) = 2,000,000
    # 평가금액: 640,000 + (1,100 * 1300) = 2,070,000
    # 손익: 70,000
    assert summary["item_count"] == 2
    assert summary["stop_loss_count"] == 1
    assert summary["total_invested"] == 2000000.0
    assert summary["total_eval"] == 2070000.0
    assert summary["total_profit"] == 70000.0


def test_calculate_portfolio_performance_empty():
    df, summary = calculate_portfolio_performance([], {})
    assert df.empty
    assert summary["item_count"] == 0
    assert summary["total_invested"] == 0.0


def test_get_live_price_map_fallback():
    items = [
        {"ticker": "005930", "buy_price": 70000.0},
        {"ticker": "UNKNOWN_TICKER", "buy_price": 5000.0}
    ]
    price_map = get_live_price_map(items)
    assert "005930" in price_map
    assert price_map["005930"] > 0
    assert "UNKNOWN_TICKER" in price_map
    assert price_map["UNKNOWN_TICKER"] == 5000.0


def test_get_live_price_map_alphanumeric_krx_stock():
    items = [
        {"ticker": "0155M0", "name": "ACE US SMR Nuclear TOP 10", "market": "KRX", "buy_price": 6837.0, "quantity": 21.0}
    ]
    price_map = get_live_price_map(items)
    assert "0155M0" in price_map
    assert price_map["0155M0"] > 0
    # Must get real market price (e.g. 5385), not fall back to buy price (6837.0)
    assert price_map["0155M0"] != 6837.0



def test_format_quantity():
    from services.portfolio_service import format_quantity
    assert format_quantity(15.0) == "15주"
    assert format_quantity(1.5) == "1.5주"
    assert format_quantity(0.1234) == "0.1234주"


def test_calculate_rebalanced_position():
    from services.portfolio_service import calculate_rebalanced_position
    # 1. 추가 매수 (10주 @ 70,000 + 10주 @ 60,000 -> 20주 @ 65,000)
    new_qty, new_price, msg = calculate_rebalanced_position("BUY", 10.0, 70000.0, 10.0, 60000.0)
    assert new_qty == 20.0
    assert new_price == 65000.0
    assert "추가 매수 완료" in msg

    # 2. 부분 매도 (10주 @ 70,000에서 4주 매도 -> 6주 @ 70,000 유지)
    new_qty_sell, new_price_sell, msg_sell = calculate_rebalanced_position("SELL", 10.0, 70000.0, 4.0, 80000.0)
    assert new_qty_sell == 6.0
    assert new_price_sell == 70000.0
    assert "부분 매도 완료" in msg_sell


def test_stock_label_formatting():
    from services.portfolio_service import calculate_portfolio_performance
    items = [
        {"id": "krx-1", "market": "KRX", "ticker": "005930", "name": "삼성전자", "buy_price": 72000.0, "quantity": 15.0},
        {"id": "us-1", "market": "US", "ticker": "AAPL", "name": "Apple", "buy_price": 196.5, "quantity": 10.0}
    ]
    price_map = {"005930": 75000.0, "AAPL": 210.0}
    perf_df, summary = calculate_portfolio_performance(items, price_map, usd_krw_rate=1350.0)

    stock_options = {}
    for _, r in perf_df.iterrows():
        m_sign = "+" if r["eval_profit"] > 0 else ""
        cur_p_str = f"{r['current_price']:,.0f}원" if r["market"] == "KRX" else f"${r['current_price']:,.2f}"
        buy_p_str = f"{r['buy_price']:,.0f}" if r["market"] == "KRX" else f"{r['buy_price']:,.2f}"
        stock_label = (
            f"[{r['market']}] {r['name']} ({r['ticker']}) · "
            f"보유 {r['quantity_display']} @ {buy_p_str}{r['currency']} "
            f"(현재 {cur_p_str}, {m_sign}{r['profit_rate']:.2f}%)"
        )
        stock_options[stock_label] = r["id"]

    assert len(stock_options) == 2
    krx_label = [k for k in stock_options.keys() if "삼성전자" in k][0]
    assert "72,000원" in krx_label
    assert "15주" in krx_label
    us_label = [k for k in stock_options.keys() if "Apple" in k][0]
    assert "196.50$" in us_label
    assert "10주" in us_label


def test_calculate_target_recommendations():
    from services.portfolio_service import calculate_target_recommendations

    # 1. KRX 종목 (목표가 미설정 시 단기 저항선 +8% 적용)
    krx_row = {
        "market": "KRX",
        "ticker": "005930",
        "name": "삼성전자",
        "current_price": 70000.0,
        "buy_price": 68000.0,
        "target_price": None,
    }
    rec_krx = calculate_target_recommendations(krx_row)
    assert rec_krx["recom_buy_price"] == 67200.0
    assert "67,200원" in rec_krx["recom_buy_display"]
    assert "단기 지지선" in rec_krx["buy_reason"]
    assert rec_krx["recom_sell_price"] == 75600.0
    assert "75,600원" in rec_krx["recom_sell_display"]
    assert "단기 저항선" in rec_krx["sell_reason"]

    # 2. US 종목 (사용자 목표가 설정 시 목표가 우선 반영)
    us_row = {
        "market": "US",
        "ticker": "AAPL",
        "name": "Apple",
        "current_price": 200.0,
        "buy_price": 190.0,
        "target_price": 230.0,
    }
    rec_us = calculate_target_recommendations(us_row)
    assert rec_us["recom_buy_price"] == 192.0
    assert "$192.00" == rec_us["recom_buy_display"]
    assert rec_us["recom_sell_price"] == 230.0
    assert "$230.00" == rec_us["recom_sell_display"]
    assert "설정 목표가" in rec_us["sell_reason"]


def test_generate_ai_comment():
    from services.portfolio_service import generate_ai_comment

    # 1. 뉴스 있는 홀딩 구간 (+3.5%)
    item_hold = {
        "ticker": "005930",
        "name": "삼성전자",
        "profit_rate": 3.5,
        "is_stop_loss": False,
        "current_price": 72000.0,
        "buy_price": 69500.0,
        "target_price": 85000.0
    }
    news_list = [
        {"ticker": "005930", "title": "삼성전자, 차세대 고대역폭메모리(HBM4) 양산 로드맵 발표"}
    ]
    res_hold = generate_ai_comment(item_hold, news_list)
    assert res_hold["badge_type"] == "hold"
    assert "홀딩" in res_hold["badge"]
    assert "안정" in res_hold["comment"] or "추세" in res_hold["comment"]
    assert "HBM" in res_hold["comment"] or "양산" in res_hold["comment"] or "메모리" in res_hold["comment"]

    # 2. 고수익 분할 익절 구간 (+12.0%)
    item_sell = {
        "ticker": "AAPL",
        "name": "Apple",
        "profit_rate": 12.0,
        "is_stop_loss": False,
        "current_price": 224.0,
        "buy_price": 200.0,
        "target_price": 230.0
    }
    res_sell = generate_ai_comment(item_sell, [])
    assert res_sell["badge_type"] == "sell"
    assert "익절" in res_sell["badge"] or "매도" in res_sell["badge"]
    assert "차익실현" in res_sell["comment"] or "분할 매도" in res_sell["comment"] or "저항선" in res_sell["comment"]

    # 3. 손절 경고/급락 리스크 관리 구간 (-8.0%, is_stop_loss=True)
    item_danger = {
        "ticker": "000660",
        "name": "SK하이닉스",
        "profit_rate": -8.0,
        "is_stop_loss": True,
        "current_price": 160000.0,
        "buy_price": 174000.0,
        "stop_loss_price": 165000.0
    }
    res_danger = generate_ai_comment(item_danger, [])
    assert res_danger["badge_type"] in ["danger", "sell"]
    assert "손절" in res_danger["comment"] or "리스크" in res_danger["comment"] or "비중 축소" in res_danger["comment"]

    # 4. 눌림목 매수 고려 구간 (-2.5%)
    item_buy = {
        "ticker": "NVDA",
        "name": "NVIDIA",
        "profit_rate": -2.5,
        "is_stop_loss": False,
        "current_price": 117.0,
        "buy_price": 120.0,
        "target_price": 140.0
    }
    res_buy = generate_ai_comment(item_buy, [])
    assert res_buy["badge_type"] == "buy"
    assert "매수" in res_buy["badge"]
    assert "지지선" in res_buy["comment"] or "눌림목" in res_buy["comment"] or "분할 매수" in res_buy["comment"]


def test_format_quantity():
    # 정수 수량: 소수점 .0000 숨김 검증
    assert format_quantity(15.0) == "15주"
    assert format_quantity(15.0000) == "15주"
    assert format_quantity(10) == "10주"
    assert format_quantity(1.0) == "1주"

    # 소수점 수량: 유효한 소수점만 표기 (불필요한 0 제거, 최대 4자리)
    assert format_quantity(1.25) == "1.25주"
    assert format_quantity(0.5000) == "0.5주"
    assert format_quantity(1.1234) == "1.1234주"
    assert format_quantity(1.12345) == "1.1235주"


def test_format_won_compact():
    from services.portfolio_service import format_won_compact

    # 1. 1억원 이상 단위
    assert format_won_compact(150_000_000) == "1.5억원"

    # 2. 1,000만원 이상 단위 (소수점 생략 간결 표기)
    assert format_won_compact(4_480_000, prefix_approx=True) == "약 448만원"

    # 3. 1만원 이상 ~ 1000만원 미만 (소수점 1자리 유지)
    assert format_won_compact(448_820, prefix_approx=True) == "약 44.9만원"
    assert format_won_compact(322_000) == "32.2만원"
    assert format_won_compact(241_000) == "24.1만원"
    assert format_won_compact(50_000) == "5만원"

    # 4. 1만원 미만 단위
    assert format_won_compact(9_500) == "9,500원"

    # 5. 부호 표기 옵션
    assert format_won_compact(1_863_700, is_signed=True, prefix_approx=True) == "약 +186만원"
    assert format_won_compact(-500_000, is_signed=True) == "-50만원"


def test_is_valid_price_and_recommendations_fallback():
    import numpy as np
    from services.portfolio_service import (
        is_valid_price,
        calculate_target_recommendations,
    )

    # 1. is_valid_price 유효성 검사
    assert is_valid_price(None) is False
    assert is_valid_price(np.nan) is False
    assert is_valid_price(float("nan")) is False
    assert is_valid_price("nan") is False
    assert is_valid_price("None") is False
    assert is_valid_price("") is False
    assert is_valid_price(0) is False
    assert is_valid_price(0.0) is False
    assert is_valid_price(-1000) is False
    assert is_valid_price(85000) is True
    assert is_valid_price(240.5) is True
    assert is_valid_price("150.0") is True

    # 2. 목표가 미설정(None/NaN) 시 단기 저항선 (+8%) 폴백 검증
    row_no_target = {
        "market": "KRX",
        "current_price": 70000.0,
        "buy_price": 70000.0,
        "target_price": np.nan,
        "stop_loss_price": None,
    }
    rec_fallback = calculate_target_recommendations(row_no_target)
    assert "단기 저항선" in rec_fallback["sell_reason"]
    assert "(+8%)" in rec_fallback["sell_reason"]
    assert "nan" not in rec_fallback["recom_sell_display"]

    # 3. 유효한 목표가 설정 시 설정 목표가 노출 검증
    row_with_target = {
        "market": "KRX",
        "current_price": 70000.0,
        "buy_price": 70000.0,
        "target_price": 84000.0,
        "stop_loss_price": 65000.0,
    }
    rec_target = calculate_target_recommendations(row_with_target)
    assert "설정 목표가" in rec_target["sell_reason"]
    assert rec_target["recom_sell_display"] == "84,000원"

def test_calculate_isa_default_maturity():
    from datetime import date
    from services.portfolio_service import calculate_isa_default_maturity
    opened = date(2024, 5, 10)
    expected_maturity = date(2027, 5, 10)
    assert calculate_isa_default_maturity(opened) == expected_maturity
    # String input support
    assert calculate_isa_default_maturity("2024-05-10") == expected_maturity
    # Leap year handling e.g. Feb 29
    assert calculate_isa_default_maturity(date(2024, 2, 29)) == date(2027, 2, 28)

def test_calculate_isa_dday():
    from datetime import date
    from services.portfolio_service import calculate_isa_dday
    today = date(2026, 10, 9)
    # 1. 만기 전
    res_future = calculate_isa_dday(date(2027, 4, 7), base_date=today)
    assert res_future["d_day"] == 180
    assert res_future["label"] == "D-180"
    assert res_future["status"] == "active"

    # 2. 오늘 만기
    res_today = calculate_isa_dday(today, base_date=today)
    assert res_today["d_day"] == 0
    assert res_today["label"] == "D-Day"
    assert res_today["status"] == "due"

    # 3. 만기 경과
    res_past = calculate_isa_dday(date(2026, 9, 9), base_date=today)
    assert res_past["d_day"] == -30
    assert res_past["label"] == "D+30"
    assert res_past["status"] == "expired"

    # 4. None or empty maturity
    assert calculate_isa_dday(None) is None
    assert calculate_isa_dday("") is None

def test_evaluate_isa_tax_advice():
    from services.portfolio_service import evaluate_isa_tax_advice
    account = {
        "account_type": "ISA",
        "broker_name": "미래에셋",
        "account_alias": "절세ISA",
        "maturity_at": "2026-10-15"
    }
    summary = {
        "total_eval": 40_000_000.0
    }
    advice = evaluate_isa_tax_advice(account, summary)
    assert advice is not None
    assert advice["max_deduction"] == 3_000_000.0  # 4000만의 10% = 400만 -> 한도 300만
    assert "연금계좌" in advice["title"]
    assert "300만" in advice["description"]

    # 일반 계좌는 advice None
    non_isa_acc = {"account_type": "일반", "broker_name": "토스증권"}
    assert evaluate_isa_tax_advice(non_isa_acc, summary) is None

    # 평가액이 작은 경우 (예: 1000만원 -> 10% = 100만원)
    summary_small = {"total_eval": 10_000_000.0}
    advice_small = evaluate_isa_tax_advice(account, summary_small)
    assert advice_small["max_deduction"] == 1_000_000.0


def test_generate_daily_portfolio_briefing_empty():
    from services.portfolio_service import generate_daily_portfolio_briefing
    briefing = generate_daily_portfolio_briefing(
        user_id="test-user",
        portfolio_items=[],
        accounts=[],
        market_indices={"USD/KRW": {"value": 1350.0}, "KOSPI": {"change_rate": 0.5}, "S&P 500": {"change_rate": 0.8}},
        briefing_date="2026-10-11"
    )
    assert briefing["briefing_date"] == "2026-10-11"
    assert briefing["summary_metrics"]["item_count"] == 0
    assert briefing["market_benchmark"]["status_tag"] == "분석 대기"
    assert briefing["risk_analysis"]["level"] == "안정"
    assert len(briefing["action_items"]) > 0


def test_generate_daily_portfolio_briefing_with_urgent_isa_and_stop_loss():
    from services.portfolio_service import generate_daily_portfolio_briefing
    items = [
        {
            "id": "item-1",
            "account_id": "acc-isa",
            "market": "KRX",
            "ticker": "005930",
            "name": "삼성전자",
            "buy_price": 70000.0,
            "quantity": 10.0,
            "stop_loss_price": 68000.0,
        },
        {
            "id": "item-2",
            "account_id": "acc-isa",
            "market": "KRX",
            "ticker": "000660",
            "name": "SK하이닉스",
            "buy_price": 180000.0,
            "quantity": 5.0,
            "stop_loss_price": 175000.0,
        }
    ]
    accounts = [
        {
            "id": "acc-isa",
            "broker_name": "한국투자증권",
            "account_alias": "절세ISA",
            "account_type": "ISA",
            "maturity_at": "2026-10-20"  # D-9 (임박)
        }
    ]
    # 현재가가 손절가 미만으로 하락했다고 가정
    price_map = {
        "005930": 65000.0,  # 손절가 68000 하회
        "000660": 170000.0  # 손절가 175000 하회
    }
    market_indices = {
        "USD/KRW": {"value": 1350.0},
        "KOSPI": {"change_rate": -1.2},
        "S&P 500": {"change_rate": -0.5}
    }
    briefing = generate_daily_portfolio_briefing(
        user_id="test-user",
        portfolio_items=items,
        accounts=accounts,
        market_indices=market_indices,
        price_map=price_map,
        briefing_date="2026-10-11"
    )
    # 1. 메트릭 확인
    assert briefing["summary_metrics"]["item_count"] == 2
    assert briefing["summary_metrics"]["stop_loss_count"] == 2
    # 2. 리스크 레벨은 경고 (손절 2건)
    assert briefing["risk_analysis"]["level"] == "경고"
    assert briefing["risk_analysis"]["badge_emoji"] == "🔴"
    # 3. 절세 만기 임박 감지
    assert briefing["tax_accounts"]["has_issue"] is True
    assert len(briefing["tax_accounts"]["urgent_isa"]) == 1
    assert "절세ISA" in briefing["tax_accounts"]["comment"]


