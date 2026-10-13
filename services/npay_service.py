"""
Npay 증권 API 연동 및 퀀트 Top 3 유망 종목 발굴 서비스
"""
import re
import logging
import requests
import pandas as pd
import numpy as np
from typing import Any, Optional

logger = logging.getLogger(__name__)

URL_DOMESTIC = "https://stock.naver.com/api/stockSecurity/etfs/v2/domestic?listingType=tradingValueDesc&size=100&index=0"
URL_GLOBAL = "https://stock.naver.com/api/foreign/market/stock/global?nation=USA&tradeType=ALL&orderType=priceTop&startIdx=0&pageSize=100"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://stock.naver.com/",
    "Accept": "application/json, text/plain, */*"
}

STANDARD_COLUMNS = ["ticker", "name", "current_price", "change_rate", "trading_value", "market"]


def _clean_float(val: Any, default: float = 0.0) -> float:
    """문자열, 쉼표, 특수기호가 포함된 숫자 값을 안전하게 float으로 변환합니다."""
    if val is None or pd.isna(val):
        return default
    if isinstance(val, (int, float)):
        return float(val)
    try:
        s = str(val).replace(",", "").replace("%", "").replace("+", "").strip()
        return float(s) if s else default
    except (ValueError, TypeError):
        return default


def normalize_market_data(raw_data: Any, market: str = "KRX") -> pd.DataFrame:
    """
    국내/해외 Npay API의 서로 다른 응답 JSON 구조를 동일한 규격의 pandas DataFrame으로 변환합니다.
    
    통일된 DataFrame 컬럼:
    - ticker (str): 종목/ETF 코드
    - name (str): 종목/ETF 명칭
    - current_price (float): 현재가
    - change_rate (float): 등락률 (%)
    - trading_value (float): 거래대금 (원 또는 달러)
    - market (str): 'KRX' 또는 'US'
    """
    market = market.upper()
    if not raw_data:
        return pd.DataFrame(columns=STANDARD_COLUMNS)

    items_list: list[dict] = []

    # 1. 원시 응답 타입 정규화 (dict vs list)
    if isinstance(raw_data, list):
        items_list = raw_data
    elif isinstance(raw_data, dict):
        if "items" in raw_data and isinstance(raw_data["items"], list):
            items_list = raw_data["items"]
        elif "result" in raw_data and isinstance(raw_data["result"], dict):
            res = raw_data["result"]
            items_list = res.get("etfItemList") or res.get("stockList") or res.get("items") or []
        elif "stockList" in raw_data:
            items_list = raw_data["stockList"]
        elif "etfItemList" in raw_data:
            items_list = raw_data["etfItemList"]
        else:
            # 기타 리스트형 키 탐색
            for v in raw_data.values():
                if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                    items_list = v
                    break

    normalized_rows = []
    for item in items_list:
        if not isinstance(item, dict):
            continue

        # 티커 추출 (국내: itemCode, 해외: symbolCode or reutersCode)
        ticker = item.get("itemCode") or item.get("itemcode") or item.get("symbolCode") or item.get("reutersCode") or ""
        ticker = str(ticker).strip()
        # 해외 티커 뒤 거래소 접미사(.O, .N 등) 정리
        if market == "US" and "." in ticker and not item.get("symbolCode"):
            ticker = ticker.split(".")[0]
        elif market == "US" and item.get("symbolCode"):
            ticker = str(item.get("symbolCode")).strip()

        # 종목명 추출 (한글명 우선, 없을 시 영문명)
        name = (
            item.get("itemName") or 
            item.get("itemname") or 
            item.get("koreanCodeName") or 
            item.get("englishCodeName") or 
            item.get("stockName") or 
            ticker
        )
        name = str(name).strip()

        # 현재가 추출
        raw_price = (
            item.get("currentPrice") or 
            item.get("nowVal") or 
            item.get("closePrice") or 
            0.0
        )
        current_price = _clean_float(raw_price)

        # 등락률 추출
        raw_change = (
            item.get("changeRate") or 
            item.get("fluctuationsRatio") or 
            0.0
        )
        change_rate = _clean_float(raw_change)

        # 거래대금 추출
        raw_val = (
            item.get("tradingValue") or 
            item.get("amount") or 
            item.get("accumulatedTradingValue") or 
            item.get("marketValue") or 
            0.0
        )
        trading_value = _clean_float(raw_val)

        if ticker:
            normalized_rows.append({
                "ticker": ticker,
                "name": name,
                "current_price": current_price,
                "change_rate": change_rate,
                "trading_value": trading_value,
                "market": market
            })

    if not normalized_rows:
        return pd.DataFrame(columns=STANDARD_COLUMNS)

    df = pd.DataFrame(normalized_rows)
    return df[STANDARD_COLUMNS]


def get_mock_market_data(market: str = "KRX") -> pd.DataFrame:
    """API 장애 또는 테스트 시 사용할 현실적인 모의 시세 데이터"""
    if market.upper() == "KRX":
        mock_data = [
            {"ticker": "069500", "name": "KODEX 200", "current_price": 36500.0, "change_rate": 0.85, "trading_value": 254000000000.0, "market": "KRX"},
            {"ticker": "379800", "name": "KODEX 미국S&P500TR", "current_price": 18450.0, "change_rate": 1.20, "trading_value": 182000000000.0, "market": "KRX"},
            {"ticker": "133690", "name": "TIGER 미국나스닥100", "current_price": 115200.0, "change_rate": 1.45, "trading_value": 165000000000.0, "market": "KRX"},
            {"ticker": "122630", "name": "KODEX 레버리지", "current_price": 17800.0, "change_rate": 1.80, "trading_value": 310000000000.0, "market": "KRX"},
            {"ticker": "252670", "name": "KODEX 200선물인버스2X", "current_price": 2150.0, "change_rate": -1.75, "trading_value": 220000000000.0, "market": "KRX"},
            {"ticker": "453850", "name": "ACE 미국30년국채액티브(H)", "current_price": 9850.0, "change_rate": -0.30, "trading_value": 95000000000.0, "market": "KRX"},
            {"ticker": "449170", "name": "TIGER 미국배당다우존스", "current_price": 12350.0, "change_rate": 0.40, "trading_value": 85000000000.0, "market": "KRX"},
        ]
    else:
        mock_data = [
            {"ticker": "NVDA", "name": "NVIDIA Corporation", "current_price": 128.50, "change_rate": 2.45, "trading_value": 32000000000.0, "market": "US"},
            {"ticker": "AAPL", "name": "Apple Inc", "current_price": 224.20, "change_rate": 0.75, "trading_value": 18500000000.0, "market": "US"},
            {"ticker": "MSFT", "name": "Microsoft Corporation", "current_price": 435.00, "change_rate": 1.10, "trading_value": 14200000000.0, "market": "US"},
            {"ticker": "TSLA", "name": "Tesla Inc", "current_price": 255.80, "change_rate": 3.80, "trading_value": 24500000000.0, "market": "US"},
            {"ticker": "AMZN", "name": "Amazon.com Inc", "current_price": 186.40, "change_rate": -0.65, "trading_value": 11500000000.0, "market": "US"},
            {"ticker": "QQQ", "name": "Invesco QQQ Trust", "current_price": 490.30, "change_rate": 1.35, "trading_value": 19500000000.0, "market": "US"},
            {"ticker": "SPY", "name": "SPDR S&P 500 ETF Trust", "current_price": 575.10, "change_rate": 0.80, "trading_value": 28000000000.0, "market": "US"},
        ]
    return pd.DataFrame(mock_data)[STANDARD_COLUMNS]


def _fetch_from_api(market: str = "KRX") -> pd.DataFrame:
    """Npay API 직접 호출 내부 함수"""
    url = URL_DOMESTIC if market.upper() == "KRX" else URL_GLOBAL
    try:
        resp = requests.get(url, headers=HEADERS, timeout=6)
        if resp.status_code == 200:
            df = normalize_market_data(resp.json(), market=market)
            if not df.empty:
                return df
        logger.warning(f"Npay API response status {resp.status_code} for {market}. Using fallback.")
    except Exception as e:
        logger.warning(f"Npay API request failed for {market}: {e}. Using fallback.")

    return get_mock_market_data(market)


# Streamlit 캐시 래퍼 (Streamlit 런타임 환경에서 30분 TTL 적용)
try:
    import streamlit as st
    @st.cache_data(ttl=1800, show_spinner=False)
    def _cached_fetch_npay_items(market: str) -> pd.DataFrame:
        return _fetch_from_api(market)
    
    def fetch_npay_items(market: str = "KRX") -> pd.DataFrame:
        """Streamlit 30분 캐시가 적용된 시세 수집 함수"""
        try:
            return _cached_fetch_npay_items(market)
        except Exception:
            return _fetch_from_api(market)
except Exception:
    def fetch_npay_items(market: str = "KRX") -> pd.DataFrame:
        """비-Streamlit 환경 (pytest 등) 직접 수집 함수"""
        return _fetch_from_api(market)


def calculate_top3_quant(df: pd.DataFrame) -> pd.DataFrame:
    """
    가치(50%) + 수급(50%) 혼합 기준 퀀트 점수를 산출하고 Top 3 종목을 반환합니다.
    
    - 가치 점수 (50%): 가격 과열도가 낮고 적정 가격대에 위치한 종목 우대 (안정성 및 가격 메리트)
    - 수급 점수 (50%): 시장 거래대금 및 유동성 강도 (Min-Max Scaling)
    """
    if df.empty or len(df) < 3:
        return df

    work_df = df.copy()

    # 1. 수급 점수 (0 ~ 100): 거래대금 기준 Min-Max 스케일링
    tv_min = work_df["trading_value"].min()
    tv_max = work_df["trading_value"].max()
    if tv_max > tv_min:
        supply_raw = (work_df["trading_value"] - tv_min) / (tv_max - tv_min) * 100.0
    else:
        supply_raw = pd.Series(50.0, index=work_df.index)

    # 2. 가치 점수 (0 ~ 100):
    # 과도한 급등(+5% 이상 과열) 종목보다는 건강한 상승/눌림목 및 매력적인 밸류에이션 구간 종목에 가산점
    # 등락률이 -2% ~ +3% 사이의 건전한 변동성 구간일 때 높은 점수 부여
    cr = work_df["change_rate"]
    # 적정 변동성 중심 거리 기반 가치 점수 모델
    distance_from_ideal = (cr - 0.5).abs()
    max_dist = distance_from_ideal.max() if distance_from_ideal.max() > 0 else 1.0
    value_raw = 100.0 - (distance_from_ideal / max_dist * 80.0)

    work_df["supply_score"] = supply_raw.round(1)
    work_df["value_score"] = value_raw.round(1)

    # 3. 종합 점수 (50:50 가중 평균)
    work_df["total_score"] = (work_df["value_score"] * 0.5 + work_df["supply_score"] * 0.5).round(1)

    # 4. 선정 사유 텍스트 자동 생성
    reasons = []
    for _, row in work_df.iterrows():
        s_score = row["supply_score"]
        v_score = row["value_score"]
        chg = row["change_rate"]

        if s_score >= 80:
            supply_text = "압도적 거래대금 집중"
        elif s_score >= 50:
            supply_text = "양호한 시장 유동성"
        else:
            supply_text = "안정적 거래 규모"

        if chg > 2.0:
            trend_text = "강한 상승 모멘텀 지속"
        elif chg >= 0.0:
            trend_text = "우상향 지지 구간"
        else:
            trend_text = "눌림목 매수 기회 구간"

        reasons.append(f"{supply_text} & {trend_text} (종합 점수 {row['total_score']}점)")

    work_df["reason"] = reasons

    # 5. 종합 점수 내림차순 정렬 후 Top 3 추출
    top3 = work_df.sort_values(by="total_score", ascending=False).head(3).reset_index(drop=True)
    return top3
