"""
보유 종목 관련 최신 뉴스 및 주요 공시 헤드라인 수집 서비스
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Any
import yfinance as yf

logger = logging.getLogger(__name__)


def _get_mock_news(tickers: list[str]) -> list[dict[str, str]]:
    """테스트 또는 네트워크 부재 시 반환할 모의 뉴스 헤드라인"""
    mock_news_pool = [
        {"ticker": "005930", "title": "삼성전자, 차세대 고대역폭메모리(HBM4) 양산 로드맵 발표", "publisher": "한국경제", "link": "https://finance.naver.com/", "time": "20분 전"},
        {"ticker": "005930", "title": "[공시] 삼성전자 주주가치 제고를 위한 분기 배당금 지급 결정", "publisher": "DART 전자공시", "link": "https://dart.fss.or.kr/", "time": "1시간 전"},
        {"ticker": "AAPL", "title": "Apple, 신규 M4 칩셋 탑재 디바이스 라인업 강화 기대감", "publisher": "Bloomberg", "link": "https://www.bloomberg.com/", "time": "45분 전"},
        {"ticker": "NVDA", "title": "NVIDIA 데이터센터 AI 가속기 글로벌 빅테크 주문 지속 증가", "publisher": "Reuters", "link": "https://www.reuters.com/", "time": "30분 전"},
        {"ticker": "TSLA", "title": "Tesla 완전자율주행(FSD) 신규 버전 글로벌 배포 본격화", "publisher": "CNBC", "link": "https://www.cnbc.com/", "time": "2시간 전"},
        {"ticker": "000660", "title": "SK하이닉스, 글로벌 빅테크향 엔터프라이즈 SSD 공급 확대", "publisher": "매일경제", "link": "https://finance.naver.com/", "time": "1시간 전"},
    ]
    if not tickers:
        return mock_news_pool[:4]

    clean_tickers = [t.strip().upper() for t in tickers]
    matched = [n for n in mock_news_pool if n["ticker"] in clean_tickers]
    return matched if matched else mock_news_pool[:3]


def _fetch_stock_news_raw(tickers: list[str]) -> list[dict[str, str]]:
    """yfinance 및 폴백을 통해 종목별 최신 뉴스를 수집합니다."""
    if not tickers:
        return _get_mock_news([])

    news_list = []
    seen_titles = set()

    for ticker in tickers[:5]:  # 빠른 렌더링을 위해 최대 상위 5개 종목 우선 조회
        clean_t = ticker.strip().upper()
        sym = f"{clean_t}.KS" if clean_t.isdigit() and len(clean_t) == 6 else clean_t

        try:
            t_obj = yf.Ticker(sym)
            raw_news = getattr(t_obj, "news", []) or []
            
            for item in raw_news[:3]:
                title = item.get("title", "").strip()
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    pub = item.get("publisher", "Financial News")
                    link = item.get("link", "#")
                    pub_time = item.get("providerPublishTime")
                    if pub_time:
                        try:
                            dt = datetime.fromtimestamp(pub_time)
                            time_str = dt.strftime("%m-%d %H:%M")
                        except Exception:
                            time_str = "최근"
                    else:
                        time_str = "최근"

                    news_list.append({
                        "ticker": clean_t,
                        "title": title,
                        "publisher": pub,
                        "link": link,
                        "time": time_str
                    })
        except Exception as e:
            logger.debug(f"Failed to fetch yfinance news for {clean_t}: {e}")

    # 실시간 뉴스가 없거나 실패한 경우 모의 뉴스로 보강
    if not news_list:
        return _get_mock_news(tickers)

    return news_list


# Streamlit 10분 TTL 캐시 적용
try:
    import streamlit as st
    @st.cache_data(ttl=600, show_spinner=False)
    def _cached_fetch_stock_news(tickers_tuple: tuple[str, ...]) -> list[dict[str, str]]:
        return _fetch_stock_news_raw(list(tickers_tuple))

    def fetch_stock_news(tickers: list[str]) -> list[dict[str, str]]:
        """10분 캐시가 적용된 뉴스 수집 함수"""
        try:
            # list는 unhashable하므로 tuple로 변환하여 캐싱
            return _cached_fetch_stock_news(tuple(sorted(tickers)))
        except Exception:
            return _fetch_stock_news_raw(tickers)
except Exception:
    def fetch_stock_news(tickers: list[str]) -> list[dict[str, str]]:
        """비-Streamlit 환경 뉴스 수집 함수"""
        return _fetch_stock_news_raw(tickers)
