"""
종목코드 또는 종목명으로 종목 정보(티커, 종목명, 시장, 현재가)를 자동 검색 및 불러오는 서비스
"""
import logging
from typing import Any, Optional
import requests
import yfinance as yf

from services.npay_service import fetch_npay_items

logger = logging.getLogger(__name__)

# 빠른 조회를 위한 국내 및 미국 대표 주식/ETF 사전
POPULAR_STOCKS: dict[str, dict[str, Any]] = {
    # 국내 (KRX)
    "005930": {"ticker": "005930", "name": "삼성전자", "market": "KRX", "price": 60000.0},
    "삼성전자": {"ticker": "005930", "name": "삼성전자", "market": "KRX", "price": 60000.0},
    "000660": {"ticker": "000660", "name": "SK하이닉스", "market": "KRX", "price": 180000.0},
    "SK하이닉스": {"ticker": "000660", "name": "SK하이닉스", "market": "KRX", "price": 180000.0},
    "373220": {"ticker": "373220", "name": "LG에너지솔루션", "market": "KRX", "price": 400000.0},
    "LG에너지솔루션": {"ticker": "373220", "name": "LG에너지솔루션", "market": "KRX", "price": 400000.0},
    "005380": {"ticker": "005380", "name": "현대차", "market": "KRX", "price": 240000.0},
    "현대차": {"ticker": "005380", "name": "현대차", "market": "KRX", "price": 240000.0},
    "035420": {"ticker": "035420", "name": "NAVER", "market": "KRX", "price": 170000.0},
    "NAVER": {"ticker": "035420", "name": "NAVER", "market": "KRX", "price": 170000.0},
    "035720": {"ticker": "035720", "name": "카카오", "market": "KRX", "price": 38000.0},
    "카카오": {"ticker": "035720", "name": "카카오", "market": "KRX", "price": 38000.0},
    "069500": {"ticker": "069500", "name": "KODEX 200", "market": "KRX", "price": 35000.0},
    "360750": {"ticker": "360750", "name": "TIGER 미국S&P500", "market": "KRX", "price": 18000.0},
    "133690": {"ticker": "133690", "name": "TIGER 미국나스닥100", "market": "KRX", "price": 115000.0},
    "472170": {"ticker": "472170", "name": "TIGER 미국테크TOP10채권혼합", "market": "KRX", "price": 14170.0},
    "472107": {"ticker": "472107", "name": "TIGER 미국테크TOP10채권혼합", "market": "KRX", "price": 14170.0},
    "TIGER 미국테크TOP10채권혼합": {"ticker": "472170", "name": "TIGER 미국테크TOP10채권혼합", "market": "KRX", "price": 14170.0},

    # 미국 (US)
    "AAPL": {"ticker": "AAPL", "name": "Apple Inc.", "market": "US", "price": 225.0},
    "애플": {"ticker": "AAPL", "name": "Apple Inc.", "market": "US", "price": 225.0},
    "NVDA": {"ticker": "NVDA", "name": "NVIDIA Corporation", "market": "US", "price": 120.0},
    "엔비디아": {"ticker": "NVDA", "name": "NVIDIA Corporation", "market": "US", "price": 120.0},
    "TSLA": {"ticker": "TSLA", "name": "Tesla, Inc.", "market": "US", "price": 240.0},
    "테슬라": {"ticker": "TSLA", "name": "Tesla, Inc.", "market": "US", "price": 240.0},
    "MSFT": {"ticker": "MSFT", "name": "Microsoft Corporation", "market": "US", "price": 420.0},
    "마이크로소프트": {"ticker": "MSFT", "name": "Microsoft Corporation", "market": "US", "price": 420.0},
    "AMZN": {"ticker": "AMZN", "name": "Amazon.com, Inc.", "market": "US", "price": 185.0},
    "아마존": {"ticker": "AMZN", "name": "Amazon.com, Inc.", "market": "US", "price": 185.0},
    "GOOGL": {"ticker": "GOOGL", "name": "Alphabet Inc.", "market": "US", "price": 165.0},
    "구글": {"ticker": "GOOGL", "name": "Alphabet Inc.", "market": "US", "price": 165.0},
    "SPY": {"ticker": "SPY", "name": "SPDR S&P 500 ETF Trust", "market": "US", "price": 570.0},
    "QQQ": {"ticker": "QQQ", "name": "Invesco QQQ Trust", "market": "US", "price": 485.0},
}


def _clean_price(val: Any) -> float:
    """문자열 또는 숫자 가격을 float로 변환"""
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = val.replace(",", "").replace("$", "").replace("원", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    return 0.0


def _search_krx_naver_api(ticker: str) -> Optional[dict[str, Any]]:
    """네이버 증권 API를 통해 국내 종목 기본 정보 조회"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://m.stock.naver.com/"
    }
    url = f"https://m.stock.naver.com/api/stock/{ticker}/basic"
    try:
        resp = requests.get(url, headers=headers, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            stock_name = data.get("stockName")
            close_price_raw = data.get("closePrice", "0")
            if stock_name:
                return {
                    "ticker": ticker,
                    "name": stock_name,
                    "market": "KRX",
                    "current_price": _clean_price(close_price_raw),
                }
    except Exception as e:
        logger.debug(f"Naver basic API lookup failed for {ticker}: {e}")
    return None


def _search_us_yfinance(ticker: str) -> Optional[dict[str, Any]]:
    """yfinance를 통해 미국 종목명 및 현재가 조회"""
    try:
        t = yf.Ticker(ticker)
        name = t.info.get("shortName") or t.info.get("longName")
        curr_price = t.info.get("regularMarketPrice") or t.info.get("currentPrice") or 0.0
        if not curr_price:
            hist = t.history(period="2d")
            if not hist.empty:
                curr_price = float(hist["Close"].iloc[-1])
        if name:
            return {
                "ticker": ticker.upper(),
                "name": name,
                "market": "US",
                "current_price": round(float(curr_price), 2),
            }
    except Exception as e:
        logger.debug(f"yfinance lookup failed for {ticker}: {e}")
    return None


def search_stock_by_ticker_or_name(query: str, market: str = "KRX") -> Optional[dict[str, Any]]:
    """
    종목코드(티커) 또는 종목명을 입력받아 종목명과 현재가를 자동으로 조회합니다.
    1. 인기 대표 종목 사전 매칭 (0ms)
    2. Npay API 캐시 데이터프레임 매칭
    3. 실시간 온라인 API (네이버 증권 또는 yfinance) 조회
    """
    if not query:
        return None

    clean_q = query.strip()
    upper_q = clean_q.upper()

    # 1. 사전 등록 종목 즉시 매칭
    if clean_q in POPULAR_STOCKS:
        hit = dict(POPULAR_STOCKS[clean_q])
        return hit
    if upper_q in POPULAR_STOCKS:
        hit = dict(POPULAR_STOCKS[upper_q])
        return hit

    # 2. Npay 캐시 상위 100개 데이터프레임에서 검색
    try:
        cached_df = fetch_npay_items(market)
        if not cached_df.empty:
            # 티커 정확 일치
            match_ticker = cached_df[cached_df["ticker"].astype(str).str.upper() == upper_q]
            if not match_ticker.empty:
                row = match_ticker.iloc[0]
                return {
                    "ticker": str(row["ticker"]),
                    "name": str(row["name"]),
                    "market": market,
                    "current_price": float(row["current_price"]),
                }
            # 종목명 부분 일치
            match_name = cached_df[cached_df["name"].astype(str).str.contains(clean_q, case=False, na=False)]
            if not match_name.empty:
                row = match_name.iloc[0]
                return {
                    "ticker": str(row["ticker"]),
                    "name": str(row["name"]),
                    "market": market,
                    "current_price": float(row["current_price"]),
                }
    except Exception as e:
        logger.debug(f"Npay cache search skipped: {e}")

    # 3. 실시간 API 조회
    if market == "KRX":
        # 6자리 숫자 코드인 경우 네이버 API 시도
        if len(clean_q) == 6 and clean_q.isdigit():
            res = _search_krx_naver_api(clean_q)
            if res:
                return res
        # yfinance 한국 거래소 심볼 조회 (.KS / .KQ)
        for suffix in [".KS", ".KQ"]:
            try:
                t = yf.Ticker(f"{clean_q}{suffix}")
                name = t.info.get("shortName")
                if name:
                    curr_price = t.info.get("regularMarketPrice") or 0.0
                    return {
                        "ticker": clean_q,
                        "name": name,
                        "market": "KRX",
                        "current_price": float(curr_price),
                    }
            except Exception:
                continue

    elif market == "US":
        # 미국 주식은 티커 알파벳 기준으로 yfinance 조회
        res = _search_us_yfinance(upper_q)
        if res:
            return res

    return None
