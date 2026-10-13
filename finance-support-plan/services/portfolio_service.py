"""개인 포트폴리오 계산 및 종목 뉴스/공시 서비스 모듈.

향후 실제 금융 데이터 API(pykrx, yfinance) 및 전자공시시스템(DART) 연동을 염두에 둔
데이터 정규화 및 비즈니스 로직을 제공합니다.
"""

from typing import Dict, List, Any
import pandas as pd


# 티커별 가상 실시간 시세 (실제 연동 시 pykrx.stock.get_market_snapshot 또는 yfinance 연동)
MOCK_CURRENT_PRICES = {
    "005930": {"name": "삼성전자", "price": 74500, "currency": "KRW", "market": "KRX"},
    "000660": {"name": "SK하이닉스", "price": 184500, "currency": "KRW", "market": "KRX"},
    "005380": {"name": "현대차", "price": 248500, "currency": "KRW", "market": "KRX"},
    "035420": {"name": "NAVER", "price": 172000, "currency": "KRW", "market": "KRX"},
    "267260": {"name": "HD현대일렉트릭", "price": 312000, "currency": "KRW", "market": "KRX"},
    "035720": {"name": "카카오", "price": 41200, "currency": "KRW", "market": "KRX"},
    "005490": {"name": "POSCO홀딩스", "price": 365000, "currency": "KRW", "market": "KRX"},
    "NVDA": {"name": "NVIDIA", "price": 128.5, "currency": "USD", "market": "US"},
    "AAPL": {"name": "Apple", "price": 226.3, "currency": "USD", "market": "US"},
    "TSLA": {"name": "Tesla", "price": 242.8, "currency": "USD", "market": "US"},
    "MSFT": {"name": "Microsoft", "price": 420.5, "currency": "USD", "market": "US"},
}


def get_current_stock_price(ticker: str) -> Dict[str, Any]:
    """특정 티커의 현재가 정보를 반환합니다.

    향후 연동 가이드:
    - KRX: pykrx.stock.get_market_ticker_name(ticker), pykrx.stock.get_market_price_change_by_ticker(...)
    - US: yfinance.Ticker(ticker).fast_info['lastPrice']
    """
    ticker_upper = ticker.strip().upper()
    if ticker_upper in MOCK_CURRENT_PRICES:
        return MOCK_CURRENT_PRICES[ticker_upper]

    # 기본 Mock fallback
    return {
        "name": ticker_upper,
        "price": 100000 if not ticker_upper.isalpha() else 100.0,
        "currency": "KRW" if not ticker_upper.isalpha() else "USD",
        "market": "KRX" if not ticker_upper.isalpha() else "US",
    }


def calculate_portfolio_details(holdings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """보유 종목 리스트를 받아 종목별 평가손익 및 포트폴리오 집계 통계를 계산합니다."""
    if not holdings:
        return {
            "summary": {
                "total_invested": 0,
                "total_eval": 0,
                "total_profit": 0,
                "total_return_pct": 0.0,
                "holding_count": 0,
                "warning_count": 0,
            },
            "rows": [],
            "df": pd.DataFrame(),
        }

    rows = []
    total_invested = 0.0
    total_eval = 0.0
    warning_count = 0

    # 환율 Mock (달러 자산의 원화 환산 비교용)
    usd_krw_rate = 1334.50

    for item in holdings:
        ticker = item.get("ticker", "").strip().upper()
        name = item.get("name") or ticker
        buy_price = float(item.get("buy_price", 0))
        qty = float(item.get("quantity", 0))
        target_price = float(item.get("target_price", 0)) if item.get("target_price") else None
        stop_loss_price = float(item.get("stop_loss_price", 0)) if item.get("stop_loss_price") else None
        currency = item.get("currency", "KRW")

        # 시세 조회
        live_info = get_current_stock_price(ticker)
        current_price = float(live_info.get("price", buy_price))
        if name == ticker and live_info.get("name") != ticker:
            name = live_info.get("name")

        invested_amount = buy_price * qty
        eval_amount = current_price * qty
        profit_loss = eval_amount - invested_amount
        return_pct = ((current_price - buy_price) / buy_price * 100) if buy_price > 0 else 0.0

        # 목표가 달성률 및 손절가 경고
        target_progress = (current_price / target_price * 100) if target_price and target_price > 0 else None
        is_stop_loss_triggered = (current_price <= stop_loss_price) if stop_loss_price and stop_loss_price > 0 else False
        if is_stop_loss_triggered:
            warning_count += 1

        # 원화 기준 합산 (USD인 경우 환율 적용)
        multiplier = usd_krw_rate if currency == "USD" else 1.0
        total_invested += invested_amount * multiplier
        total_eval += eval_amount * multiplier

        rows.append({
            "ticker": ticker,
            "name": name,
            "currency": currency,
            "buy_price": buy_price,
            "current_price": current_price,
            "quantity": qty,
            "invested_amount": invested_amount,
            "eval_amount": eval_amount,
            "profit_loss": profit_loss,
            "return_pct": return_pct,
            "target_price": target_price,
            "target_progress": target_progress,
            "stop_loss_price": stop_loss_price,
            "is_stop_loss_triggered": is_stop_loss_triggered,
            "memo": item.get("memo", ""),
        })

    total_profit = total_eval - total_invested
    total_return_pct = (total_profit / total_invested * 100) if total_invested > 0 else 0.0

    summary = {
        "total_invested": round(total_invested),
        "total_eval": round(total_eval),
        "total_profit": round(total_profit),
        "total_return_pct": round(total_return_pct, 2),
        "holding_count": len(holdings),
        "warning_count": warning_count,
        "usd_krw_rate": usd_krw_rate,
    }

    df = pd.DataFrame(rows)
    return {
        "summary": summary,
        "rows": rows,
        "df": df,
    }


def get_holdings_news_and_disclosures(tickers: List[str]) -> List[Dict[str, Any]]:
    """보유 종목들과 연관된 최신 뉴스 및 전자공시(DART) 헤드라인을 반환합니다.

    향후 연동 가이드:
    - DART 공시: OpenDartReader(api_key).list(corp_name=..., start=...)
    - 뉴스: 네이버 금융 뉴스 크롤링 또는 yfinance.Ticker.news
    """
    tickers_upper = [t.strip().upper() for t in tickers]

    # 더미 뉴스 및 공시 저장소
    all_mock_feeds = [
        {
            "ticker": "005930",
            "name": "삼성전자",
            "type": "공시 [DART]",
            "category": "수시공시",
            "title": "단일판매·공급계약체결 (북미 빅테크 대상 차세대 고대역폭 메모리 공급)",
            "date": "2026-10-04 11:20",
            "source": "금융감독원 전자공시시스템",
            "url": "https://dart.fss.or.kr",
            "tag": "호재"
        },
        {
            "ticker": "005930",
            "name": "삼성전자",
            "type": "뉴스 [언론사]",
            "category": "시장분석",
            "title": "외국인 투자자, 4거래일 연속 삼성전자 대량 순매수… 목표가 10만원 유지",
            "date": "2026-10-04 09:45",
            "source": "한국경제",
            "url": "https://finance.naver.com",
            "tag": "수급"
        },
        {
            "ticker": "000660",
            "name": "SK하이닉스",
            "type": "뉴스 [언론사]",
            "category": "산업동향",
            "title": "HBM3E 12단 양산 가속화… 글로벌 AI 가속기 공급 물량 선점 경쟁",
            "date": "2026-10-04 10:15",
            "source": "매일경제",
            "url": "https://finance.naver.com",
            "tag": "산업"
        },
        {
            "ticker": "005380",
            "name": "현대차",
            "type": "공시 [DART]",
            "category": "주주환원",
            "title": "자기주식 소각 결정 및 기업가치 제고(밸류업) 추진 현황 보고",
            "date": "2026-10-03 16:30",
            "source": "금융감독원 전자공시시스템",
            "url": "https://dart.fss.or.kr",
            "tag": "주주환원"
        },
        {
            "ticker": "NVDA",
            "name": "NVIDIA",
            "type": "글로벌 뉴스",
            "category": "실적전망",
            "title": "Blackwell 칩 고객사 납품 본격화… 글로벌 클라우드 CSP 주문 쇄도",
            "date": "2026-10-04 08:00",
            "source": "Bloomberg",
            "url": "https://bloomberg.com",
            "tag": "실적"
        },
        {
            "ticker": "035420",
            "name": "NAVER",
            "type": "뉴스 [언론사]",
            "category": "AI서비스",
            "title": "생성형 AI '하이퍼클로바X' B2B 엔터프라이즈 수익화 계약 건수 200% 증가",
            "date": "2026-10-03 14:10",
            "source": "디지털데일리",
            "url": "https://finance.naver.com",
            "tag": "성장성"
        }
    ]

    # 사용자가 보유한 종목에 해당하는 뉴스만 필터링 (없으면 전체 최신순 노출)
    matched_feeds = [item for item in all_mock_feeds if item["ticker"] in tickers_upper]
    return matched_feeds if matched_feeds else all_mock_feeds
