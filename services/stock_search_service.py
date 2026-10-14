"""
종목코드 또는 종목명으로 종목 정보(티커, 종목명, 시장, 현재가/종가)를 자동 검색 및 불러오는 서비스
"""
import logging
import re
from typing import Any, Optional
import requests
import yfinance as yf

from services.npay_service import fetch_npay_items

logger = logging.getLogger(__name__)

# 빠른 조회를 위한 국내 및 미국 대표 주식/ETF 사전 (기준가 및 실시간 시세 연동 지원)
POPULAR_STOCKS: dict[str, dict[str, Any]] = {
    # 국내 대표 주식 (KRX)
    "005930": {"ticker": "005930", "name": "삼성전자", "market": "KRX", "price": 234500.0, "current_price": 234500.0},
    "삼성전자": {"ticker": "005930", "name": "삼성전자", "market": "KRX", "price": 234500.0, "current_price": 234500.0},
    "000660": {"ticker": "000660", "name": "SK하이닉스", "market": "KRX", "price": 180000.0, "current_price": 180000.0},
    "SK하이닉스": {"ticker": "000660", "name": "SK하이닉스", "market": "KRX", "price": 180000.0, "current_price": 180000.0},
    "373220": {"ticker": "373220", "name": "LG에너지솔루션", "market": "KRX", "price": 400000.0, "current_price": 400000.0},
    "LG에너지솔루션": {"ticker": "373220", "name": "LG에너지솔루션", "market": "KRX", "price": 400000.0, "current_price": 400000.0},
    "005380": {"ticker": "005380", "name": "현대차", "market": "KRX", "price": 240000.0, "current_price": 240000.0},
    "현대차": {"ticker": "005380", "name": "현대차", "market": "KRX", "price": 240000.0, "current_price": 240000.0},
    "000270": {"ticker": "000270", "name": "기아", "market": "KRX", "price": 105000.0, "current_price": 105000.0},
    "기아": {"ticker": "000270", "name": "기아", "market": "KRX", "price": 105000.0, "current_price": 105000.0},
    "207940": {"ticker": "207940", "name": "삼성바이오로직스", "market": "KRX", "price": 980000.0, "current_price": 980000.0},
    "삼성바이오로직스": {"ticker": "207940", "name": "삼성바이오로직스", "market": "KRX", "price": 980000.0, "current_price": 980000.0},
    "068270": {"ticker": "068270", "name": "셀트리온", "market": "KRX", "price": 195000.0, "current_price": 195000.0},
    "셀트리온": {"ticker": "068270", "name": "셀트리온", "market": "KRX", "price": 195000.0, "current_price": 195000.0},
    "035420": {"ticker": "035420", "name": "NAVER", "market": "KRX", "price": 170000.0, "current_price": 170000.0},
    "NAVER": {"ticker": "035420", "name": "NAVER", "market": "KRX", "price": 170000.0, "current_price": 170000.0},
    "네이버": {"ticker": "035420", "name": "NAVER", "market": "KRX", "price": 170000.0, "current_price": 170000.0},
    "035720": {"ticker": "035720", "name": "카카오", "market": "KRX", "price": 38000.0, "current_price": 38000.0},
    "카카오": {"ticker": "035720", "name": "카카오", "market": "KRX", "price": 38000.0, "current_price": 38000.0},
    "005490": {"ticker": "005490", "name": "POSCO홀딩스", "market": "KRX", "price": 380000.0, "current_price": 38000.0},
    "POSCO홀딩스": {"ticker": "005490", "name": "POSCO홀딩스", "market": "KRX", "price": 380000.0, "current_price": 38000.0},
    "105560": {"ticker": "105560", "name": "KB금융", "market": "KRX", "price": 85000.0, "current_price": 85000.0},
    "KB금융": {"ticker": "105560", "name": "KB금융", "market": "KRX", "price": 85000.0, "current_price": 85000.0},

    # 국내 대표 ETF (KRX)
    "069500": {"ticker": "069500", "name": "KODEX 200", "market": "KRX", "price": 35000.0, "current_price": 35000.0},
    "KODEX 200": {"ticker": "069500", "name": "KODEX 200", "market": "KRX", "price": 35000.0, "current_price": 35000.0},
    "360750": {"ticker": "360750", "name": "TIGER 미국S&P500", "market": "KRX", "price": 25900.0, "current_price": 25900.0},
    "TIGER 미국S&P500": {"ticker": "360750", "name": "TIGER 미국S&P500", "market": "KRX", "price": 25900.0, "current_price": 25900.0},
    "133690": {"ticker": "133690", "name": "TIGER 미국나스닥100", "market": "KRX", "price": 115000.0, "current_price": 115000.0},
    "TIGER 미국나스닥100": {"ticker": "133690", "name": "TIGER 미국나스닥100", "market": "KRX", "price": 115000.0, "current_price": 115000.0},
    "472170": {"ticker": "472170", "name": "TIGER 미국테크TOP10채권혼합", "market": "KRX", "price": 14170.0, "current_price": 14170.0},
    "472107": {"ticker": "472107", "name": "TIGER 미국테크TOP10채권혼합", "market": "KRX", "price": 14170.0, "current_price": 14170.0},
    "TIGER 미국테크TOP10채권혼합": {"ticker": "472170", "name": "TIGER 미국테크TOP10채권혼합", "market": "KRX", "price": 14170.0, "current_price": 14170.0},

    # 미국 대표 주식/ETF (US)
    "AAPL": {"ticker": "AAPL", "name": "Apple Inc.", "market": "US", "price": 345.0, "current_price": 345.0},
    "애플": {"ticker": "AAPL", "name": "Apple Inc.", "market": "US", "price": 345.0, "current_price": 345.0},
    "NVDA": {"ticker": "NVDA", "name": "NVIDIA Corporation", "market": "US", "price": 223.0, "current_price": 223.0},
    "엔비디아": {"ticker": "NVDA", "name": "NVIDIA Corporation", "market": "US", "price": 223.0, "current_price": 223.0},
    "TSLA": {"ticker": "TSLA", "name": "Tesla, Inc.", "market": "US", "price": 367.0, "current_price": 367.0},
    "테슬라": {"ticker": "TSLA", "name": "Tesla, Inc.", "market": "US", "price": 367.0, "current_price": 367.0},
    "MSFT": {"ticker": "MSFT", "name": "Microsoft Corporation", "market": "US", "price": 538.0, "current_price": 538.0},
    "마이크로소프트": {"ticker": "MSFT", "name": "Microsoft Corporation", "market": "US", "price": 538.0, "current_price": 538.0},
    "AMZN": {"ticker": "AMZN", "name": "Amazon.com, Inc.", "market": "US", "price": 210.0, "current_price": 210.0},
    "아마존": {"ticker": "AMZN", "name": "Amazon.com, Inc.", "market": "US", "price": 210.0, "current_price": 210.0},
    "GOOGL": {"ticker": "GOOGL", "name": "Alphabet Inc.", "market": "US", "price": 180.0, "current_price": 180.0},
    "구글": {"ticker": "GOOGL", "name": "Alphabet Inc.", "market": "US", "price": 180.0, "current_price": 180.0},
    "META": {"ticker": "META", "name": "Meta Platforms, Inc.", "market": "US", "price": 580.0, "current_price": 580.0},
    "메타": {"ticker": "META", "name": "Meta Platforms, Inc.", "market": "US", "price": 580.0, "current_price": 580.0},
    "NFLX": {"ticker": "NFLX", "name": "Netflix, Inc.", "market": "US", "price": 700.0, "current_price": 700.0},
    "넷플릭스": {"ticker": "NFLX", "name": "Netflix, Inc.", "market": "US", "price": 700.0, "current_price": 700.0},
    "SPY": {"ticker": "SPY", "name": "SPDR S&P 500 ETF Trust", "market": "US", "price": 570.0, "current_price": 570.0},
    "QQQ": {"ticker": "QQQ", "name": "Invesco QQQ Trust", "market": "US", "price": 485.0, "current_price": 485.0},
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
    """네이버 증권 API를 통해 국내 종목 기본 정보 및 현재가(또는 장종료 시 종가) 조회"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://m.stock.naver.com/"
    }

    # 1. 네이버 모바일 베이직 API
    url = f"https://m.stock.naver.com/api/stock/{ticker}/basic"
    try:
        resp = requests.get(url, headers=headers, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            stock_name = data.get("stockName")
            close_price_raw = data.get("closePrice", "0")
            parsed_price = _clean_price(close_price_raw)
            if stock_name and parsed_price > 0:
                return {
                    "ticker": ticker,
                    "name": stock_name,
                    "market": "KRX",
                    "current_price": parsed_price,
                    "price": parsed_price,
                }
    except Exception as e:
        logger.debug(f"Naver basic API lookup failed for {ticker}: {e}")

    # 2. 실시간 폴링 API 보조 조회
    try:
        poll_url = f"https://polling.finance.naver.com/api/realtime/domestic/stock/{ticker}"
        resp = requests.get(poll_url, headers=headers, timeout=3)
        if resp.status_code == 200:
            datas = resp.json().get("datas", [])
            if datas:
                d = datas[0]
                stock_name = d.get("stockName")
                price = _clean_price(d.get("closePriceRaw") or d.get("closePrice") or 0)
                if stock_name and price > 0:
                    return {
                        "ticker": ticker,
                        "name": stock_name,
                        "market": "KRX",
                        "current_price": price,
                        "price": price,
                    }
    except Exception as e:
        logger.debug(f"Naver polling API lookup failed for {ticker}: {e}")

    return None


def _search_us_stock(ticker: str) -> Optional[dict[str, Any]]:
    """미국 종목명 및 현재가(또는 장종료 시 종가) 조회 (네이버 해외증권 API 우선 -> yfinance fallback)"""
    clean_ticker = ticker.upper().strip()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://m.stock.naver.com/"
    }

    # 1. 네이버 해외증권 빠른 조회 (나스닥 .O, 뉴욕 .N 등)
    for ext in [".O", ".N", ""]:
        sym = f"{clean_ticker}{ext}" if ext else clean_ticker
        try:
            url = f"https://api.stock.naver.com/stock/{sym}/basic"
            resp = requests.get(url, headers=headers, timeout=2.5)
            if resp.status_code == 200:
                data = resp.json()
                stock_name = data.get("stockNameEng") or data.get("stockName") or clean_ticker
                close_price = _clean_price(data.get("closePrice"))
                if close_price > 0:
                    return {
                        "ticker": clean_ticker,
                        "name": stock_name,
                        "market": "US",
                        "current_price": round(close_price, 2),
                        "price": round(close_price, 2),
                    }
        except Exception:
            continue

    # 2. yfinance 보조 조회
    return _search_us_yfinance(clean_ticker)


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
            p = round(float(curr_price), 2)
            return {
                "ticker": ticker.upper(),
                "name": name,
                "market": "US",
                "current_price": p,
                "price": p,
            }
    except Exception as e:
        logger.debug(f"yfinance lookup failed for {ticker}: {e}")
    return None


def search_stock_by_ticker_or_name(query: str, market: str = "KRX") -> Optional[dict[str, Any]]:
    """
    종목코드(티커) 또는 종목명을 입력받아 종목명과 현재가(장종료 시 종가)를 자동으로 조회합니다.
    1. 인기 대표 종목 사전 매칭 + 실시간/종가 시세 갱신
    2. Npay API 캐시 데이터프레임 매칭
    3. 실시간 온라인 API (네이버 증권 또는 yfinance) 조회
    """
    if not query:
        return None

    clean_q = query.strip()
    upper_q = clean_q.upper()

    # 1. 사전 등록 종목 매칭 및 실시간 현재가(장종료 시 종가) 자동 반영
    matched_entry = None
    if clean_q in POPULAR_STOCKS:
        matched_entry = POPULAR_STOCKS[clean_q]
    elif upper_q in POPULAR_STOCKS:
        matched_entry = POPULAR_STOCKS[upper_q]

    if matched_entry:
        hit = dict(matched_entry)
        target_ticker = hit.get("ticker", upper_q)
        target_market = hit.get("market", market)

        # 실시간 현재가/종가 조회 시도
        try:
            if target_market == "KRX":
                live = _search_krx_naver_api(target_ticker)
                if live and live.get("current_price", 0) > 0:
                    hit["current_price"] = live["current_price"]
                    hit["price"] = live["current_price"]
                    if live.get("name"):
                        hit["name"] = live["name"]
            elif target_market == "US":
                live = _search_us_stock(target_ticker)
                if live and live.get("current_price", 0) > 0:
                    hit["current_price"] = live["current_price"]
                    hit["price"] = live["current_price"]
                    if live.get("name"):
                        hit["name"] = live["name"]
        except Exception as e:
            logger.debug(f"Live price fetch failed for popular stock {target_ticker}: {e}")

        # 최소한 기본값 보장
        cp = hit.get("current_price") or hit.get("price") or 0.0
        hit["current_price"] = float(cp)
        hit["price"] = float(cp)
        return hit

    # 2. Npay 캐시 상위 100개 데이터프레임에서 검색
    try:
        cached_df = fetch_npay_items(market)
        if not cached_df.empty:
            # 티커 정확 일치
            match_ticker = cached_df[cached_df["ticker"].astype(str).str.upper() == upper_q]
            if not match_ticker.empty:
                row = match_ticker.iloc[0]
                cp = float(row["current_price"])
                return {
                    "ticker": str(row["ticker"]),
                    "name": str(row["name"]),
                    "market": market,
                    "current_price": cp,
                    "price": cp,
                }
            # 종목명 부분 일치
            match_name = cached_df[cached_df["name"].astype(str).str.contains(clean_q, case=False, na=False)]
            if not match_name.empty:
                row = match_name.iloc[0]
                cp = float(row["current_price"])
                return {
                    "ticker": str(row["ticker"]),
                    "name": str(row["name"]),
                    "market": market,
                    "current_price": cp,
                    "price": cp,
                }
    except Exception as e:
        logger.debug(f"Npay cache search skipped: {e}")

    # 3. 실시간 API 직접 조회
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
                    p = float(curr_price)
                    return {
                        "ticker": clean_q,
                        "name": name,
                        "market": "KRX",
                        "current_price": p,
                        "price": p,
                    }
            except Exception:
                continue

    elif market == "US":
        # 미국 주식은 티커 알파벳 기준으로 조회
        res = _search_us_stock(upper_q)
        if res:
            return res

    return None

