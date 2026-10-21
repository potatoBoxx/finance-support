"""
services/news_disclosure_service.py
보유 종목(국내 상장 ETF 및 주식)에 대한 최신 뉴스 및 공식 공시 수집 서비스 모듈.

독립 실행(CLI 배치 / GitHub Actions / 외부 스케줄러) 및 Streamlit UI 양쪽에서
유연하게 재사용할 수 있도록 설계되었습니다.
"""
import sys
import os
import time
import json
import html
import email.utils
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import logging
from datetime import datetime
from typing import Optional, Any

from db.portfolio_repo import PortfolioRepository

logger = logging.getLogger(__name__)

# 크롤링 안정성을 위한 기본 HTTP 헤더 (Streamlit Cloud 및 봇 차단 방어)
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

# 카테고리 판별용 키워드 정의
DIVIDEND_KEYWORDS = (
    "분배", "배당", "분배금", "월배당", "배당락", "배당금", "분배락", "수익분배", "주당배당"
)

DISCLOSURE_KEYWORDS = (
    "공시", "운용", "변경", "상장", "합병", "보수", "액면",
    "지정참가", "유동성공급", "순자본비율", "신탁", "약관",
    "투자설명서", "운용보고서", "임시총회", "주주총회", "감자", "증자",
    "koscom", "dart", "전자공시", "한국거래소", "상장지수투자신탁"
)


def classify_disclosure_category(title: str, body: str = "", source: str = "") -> str:
    """
    제목, 본문 요약, 출처 정보를 종합하여 우선순위에 따라 카테고리를 분류합니다.
    - 1순위: '배당/분배' (분배금, 배당 등 키워드 포함)
    - 2순위: '운용공시' (공시, 운용사 변경, LP/AP 계약, 상장 이슈 등)
    - 3순위: '시장이슈' (일반 시장 및 주가 동향)
    """
    target = f"{title} {body} {source}".lower()

    # 1순위: 분배금 / 배당
    for kw in DIVIDEND_KEYWORDS:
        if kw in target:
            return "배당/분배"

    # 2순위: 공시 및 운용 이슈
    for kw in DISCLOSURE_KEYWORDS:
        if kw in target:
            return "운용공시"

    # 3순위: 일반 시장 동향
    return "시장이슈"


def parse_published_at(raw_dt: Any) -> Optional[str]:
    """다양한 날짜 형식을 ISO 8601 문자열(YYYY-MM-DDTHH:MM:SS)로 변환합니다."""
    if not raw_dt:
        return None
    raw_str = str(raw_dt).strip()

    # Case 1: Naver Mobile News 'YYYYMMDDHHmm' (예: 202610192252)
    if len(raw_str) == 12 and raw_str.isdigit():
        try:
            return datetime.strptime(raw_str, "%Y%m%d%H%M").isoformat()
        except Exception:
            pass

    # Case 2: Naver Mobile News 'YYYYMMDDHHmmss'
    if len(raw_str) == 14 and raw_str.isdigit():
        try:
            return datetime.strptime(raw_str, "%Y%m%d%H%M%S").isoformat()
        except Exception:
            pass

    # Case 3: RFC 2822 형식 (Google News RSS: "Thu, 15 Oct 2026 09:17:10 GMT")
    if "GMT" in raw_str or "," in raw_str:
        try:
            dt = email.utils.parsedate_to_datetime(raw_str)
            return dt.isoformat()
        except Exception:
            pass

    # Case 4: 이미 ISO 형식(YYYY-MM-DDTHH:MM:SS)인 경우
    try:
        dt = datetime.fromisoformat(raw_str.replace("Z", "+00:00"))
        return dt.isoformat()
    except Exception:
        pass

    return None


def fetch_naver_stock_disclosures(ticker: str, item_name: str, limit: int = 5) -> list[dict]:
    """
    네이버 모바일 증권 KOSCOM 공시 API를 통해 ETF/종목의 공식 공시를 수집합니다.
    URL: https://m.stock.naver.com/api/stock/{ticker}/disclosure?pageSize={limit}&page=1
    """
    results = []
    clean_ticker = str(ticker or "").strip()
    if not clean_ticker or len(clean_ticker) != 6 or not clean_ticker.isalnum():
        return results

    url = f"https://m.stock.naver.com/api/stock/{clean_ticker}/disclosure?pageSize={limit}&page=1"
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list):
                for d in data:
                    title = html.unescape(str(d.get("title") or "").strip())
                    if not title:
                        continue
                    disc_id = d.get("disclosureId")
                    if disc_id:
                        origin_url = f"https://finance.naver.com/item/news_notice_read.naver?code={clean_ticker}&article_id={disc_id:010d}"
                    else:
                        origin_url = f"https://m.stock.naver.com/domestic/stock/{clean_ticker}/disclosure"

                    source = str(d.get("author") or "KOSCOM 공시").strip()
                    pub_dt = parse_published_at(d.get("datetime"))
                    cat = classify_disclosure_category(title, body="", source=source)

                    results.append({
                        "ticker": clean_ticker,
                        "item_name": item_name,
                        "title": title,
                        "source": source,
                        "origin_url": origin_url,
                        "published_at": pub_dt,
                        "category": cat,
                        "content_scraped": None,
                        "summary_ai": None,
                    })
    except Exception as e:
        logger.debug(f"fetch_naver_stock_disclosures failed for {clean_ticker}: {e}")

    return results


def fetch_naver_stock_news(ticker: str, item_name: str, limit: int = 8) -> list[dict]:
    """
    네이버 모바일 증권 종목 뉴스 API를 통해 해당 종목 관련 최신 언론 기사를 수집합니다.
    URL: https://m.stock.naver.com/api/news/stock/{ticker}?pageSize={limit}&page=1
    """
    results = []
    clean_ticker = str(ticker or "").strip()
    if not clean_ticker or len(clean_ticker) != 6 or not clean_ticker.isalnum():
        return results

    url = f"https://m.stock.naver.com/api/news/stock/{clean_ticker}?pageSize={limit}&page=1"
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list):
                for group in data:
                    for item in group.get("items", []):
                        title = html.unescape(str(item.get("title") or "").strip())
                        news_url = str(item.get("mobileNewsUrl") or "").strip()
                        if not title or not news_url:
                            continue
                        body = html.unescape(str(item.get("body") or "").strip())
                        source = str(item.get("officeName") or "네이버뉴스").strip()
                        pub_dt = parse_published_at(item.get("datetime"))
                        cat = classify_disclosure_category(title, body=body, source=source)

                        results.append({
                            "ticker": clean_ticker,
                            "item_name": item_name,
                            "title": title,
                            "source": source,
                            "origin_url": news_url,
                            "published_at": pub_dt,
                            "category": cat,
                            "content_scraped": body if body else None,
                            "summary_ai": None,
                        })
    except Exception as e:
        logger.debug(f"fetch_naver_stock_news failed for {clean_ticker}: {e}")

    return results


def fetch_keyword_feed_news(
    ticker: str,
    item_name: str,
    query_suffix: str = "분배금",
    limit: int = 3
) -> list[dict]:
    """
    ETF 종목명과 키워드(예: '분배금', '배당', '공시')를 결합한 Google News RSS 피드를 수집합니다.
    """
    results = []
    query = f"{item_name} {query_suffix}".strip() if query_suffix else item_name.strip()
    if not query:
        return results

    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            root = ET.fromstring(resp.read())
            items = root.findall(".//item")
            for it in items[:limit]:
                raw_title = it.find("title")
                title_text = html.unescape(raw_title.text.strip()) if raw_title is not None and raw_title.text else ""
                link_tag = it.find("link")
                link_text = link_tag.text.strip() if link_tag is not None and link_tag.text else ""
                pub_tag = it.find("pubDate")
                pub_text = pub_tag.text.strip() if pub_tag is not None and pub_tag.text else ""

                if not title_text or not link_text:
                    continue

                source = "언론사"
                if " - " in title_text:
                    parts = title_text.rsplit(" - ", 1)
                    title = parts[0].strip()
                    source = parts[1].strip()
                else:
                    title = title_text

                pub_dt = parse_published_at(pub_text)
                cat = classify_disclosure_category(title, body="", source=source)

                results.append({
                    "ticker": ticker,
                    "item_name": item_name,
                    "title": title,
                    "source": source,
                    "origin_url": link_text,
                    "published_at": pub_dt,
                    "category": cat,
                    "content_scraped": None,
                    "summary_ai": None,
                })
    except Exception as e:
        logger.debug(f"fetch_keyword_feed_news failed for query '{query}': {e}")

    return results


def fetch_disclosures_for_single_item(item: dict) -> list[dict]:
    """
    단일 보유 종목에 대해 공시 및 뉴스를 안전하게 수집하고 요청 간 미세 딜레이를 적용합니다.
    """
    ticker = str(item.get("ticker") or "").strip()
    item_name = str(item.get("name") or ticker).strip()
    is_krx = (str(item.get("market") or "").upper() == "KRX") or (len(ticker) == 6 and ticker.isalnum())

    collected = []

    try:
        if is_krx:
            # 1. KOSCOM 공식 공시 (운용공시 / 분배금 공시)
            disclosures = fetch_naver_stock_disclosures(ticker, item_name, limit=4)
            collected.extend(disclosures)
            time.sleep(0.25)

            # 2. 종목 관련 최신 언론 기사
            stock_news = fetch_naver_stock_news(ticker, item_name, limit=6)
            collected.extend(stock_news)
            time.sleep(0.25)

            # 3. ETF 맞춤형 분배금/배당 특화 피드 보강
            keyword_news = fetch_keyword_feed_news(ticker, item_name, query_suffix="분배금", limit=2)
            collected.extend(keyword_news)
            time.sleep(0.25)
        else:
            # 해외(US) 종목 또는 기타 자산
            keyword_div = fetch_keyword_feed_news(ticker, item_name, query_suffix="배당", limit=3)
            collected.extend(keyword_div)
            time.sleep(0.25)

            keyword_gen = fetch_keyword_feed_news(ticker, item_name, query_suffix="", limit=3)
            collected.extend(keyword_gen)
            time.sleep(0.25)
    except Exception as e:
        logger.warning(f"Error fetching disclosures for [{item_name}({ticker})]: {e}")

    return collected


def fetch_and_store_disclosures(
    user_id: str,
    portfolio_items: list[dict],
    repo: Optional[PortfolioRepository] = None
) -> dict[str, Any]:
    """
    유저가 보유한 포트폴리오 종목들을 순회하며 공시 및 뉴스를 수집하고 DB에 upsert 저장합니다.

    Args:
        user_id: 사용자 ID
        portfolio_items: 보유 종목 목록 [{'ticker': '449170', 'name': 'TIGER 미국배당다우존스', ...}, ...]
        repo: PortfolioRepository 인스턴스 (생략 시 기본 인스턴스 생성)

    Returns:
        수집 및 저장 결과 통계 딕셔너리
    """
    if repo is None or not hasattr(repo, "save_disclosures"):
        import importlib
        import db.portfolio_repo
        importlib.reload(db.portfolio_repo)
        repo = db.portfolio_repo.PortfolioRepository()

    if not user_id or not portfolio_items:
        return {
            "status": "empty",
            "saved_count": 0,
            "total_collected": 0,
            "message": "수집 대상 종목이 없습니다."
        }

    all_records: list[dict] = []
    seen_urls: set[str] = set()

    for item in portfolio_items:
        item_records = fetch_disclosures_for_single_item(item)
        for rec in item_records:
            url = rec.get("origin_url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_records.append(rec)

    if not all_records:
        return {
            "status": "empty",
            "saved_count": 0,
            "total_collected": 0,
            "message": "수집된 새로운 뉴스나 공시가 없습니다."
        }

    # DB에 안전하게 Upsert 적재
    saved_count, msg = repo.save_disclosures(user_id, all_records)

    return {
        "status": "success" if saved_count > 0 else "partial",
        "saved_count": saved_count,
        "total_collected": len(all_records),
        "message": msg
    }


def get_latest_disclosures(
    user_id: str,
    limit: int = 20,
    repo: Optional[PortfolioRepository] = None
) -> list[dict]:
    """
    Supabase DB (또는 로컬 세션)에서 해당 유저의 최신 공시/기사 목록을 최신순(published_at DESC)으로 조회하여 반환합니다.
    """
    if not user_id:
        return []
    if repo is None or not hasattr(repo, "get_disclosures"):
        import importlib
        import db.portfolio_repo
        importlib.reload(db.portfolio_repo)
        repo = db.portfolio_repo.PortfolioRepository()
    return repo.get_disclosures(user_id, limit=limit)


def render_collection_criteria_content():
    """
    사용자가 한눈에 이해할 수 있는 최신 소식 수집 기준표 및 가이드 렌더링
    (팝오버 / 말풍선 / 다이얼로그 공용)
    """
    import textwrap
    import streamlit as st

    html_content = textwrap.dedent("""
        <div class="criteria-popover-container" style="width: 100%; margin: 0; padding: 0;">
            <div style="margin-bottom: 3px;">
                <div style="color: #F8FAFC; font-size: 0.88rem; font-weight: 700; line-height: 1.2; display: flex; align-items: center; gap: 4px;">
                    📋 뉴스 및 주요 공시 수집 기준표
                </div>
                <div style="font-size: 0.68rem; color: #94A3B8; line-height: 1.2; margin-top: 2px; word-break: keep-all;">
                    보유종목 관련 핵심 투자 정보 실시간 선별 후 제공
                </div>
            </div>
            <div class="criteria-table-wrap" style="width: 100%; overflow-x: auto; margin: 3px 0;">
                <table class="criteria-table" style="width: 100%; border-collapse: collapse; font-size: 0.67rem; line-height: 1.22; color: #E2E8F0; text-align: left;">
                    <thead>
                        <tr style="background: rgba(30, 41, 59, 0.95); border-bottom: 1px solid rgba(148, 163, 184, 0.25);">
                            <th style="padding: 2.5px 4px; font-weight: 700; color: #F8FAFC; white-space: nowrap; width: 18%; font-size: 0.67rem;">시장</th>
                            <th style="padding: 2.5px 4px; font-weight: 700; color: #F8FAFC; white-space: nowrap; width: 25%; font-size: 0.67rem;">수집 출처</th>
                            <th style="padding: 2.5px 2px; font-weight: 700; color: #F8FAFC; white-space: nowrap; text-align: center; width: 17%; font-size: 0.67rem;">수집량</th>
                            <th style="padding: 2.5px 4px; font-weight: 700; color: #F8FAFC; width: 40%; font-size: 0.67rem;">주요 내용</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr style="border-bottom: 1px solid rgba(148, 163, 184, 0.1);">
                            <td rowspan="3" style="padding: 3px 4px; font-weight: 700; color: #38BDF8; vertical-align: middle; border-right: 1px solid rgba(148, 163, 184, 0.12); font-size: 0.67rem; line-height: 1.15;">국내<br><span style="font-size: 0.60rem; color: #94A3B8; font-weight: 400;">ETF·주식</span></td>
                            <td style="padding: 2.5px 4px; font-weight: 600; font-size: 0.67rem;">KOSCOM 공시</td>
                            <td style="padding: 2.5px 2px; text-align: center; white-space: nowrap; color: #CBD5E1; font-size: 0.65rem;">최대 4건</td>
                            <td style="padding: 2.5px 4px; word-break: keep-all; font-size: 0.65rem; color: #CBD5E1;">운용보고서, 분배금 공시, 상장/합병</td>
                        </tr>
                        <tr style="border-bottom: 1px solid rgba(148, 163, 184, 0.1);">
                            <td style="padding: 2.5px 4px; font-weight: 600; font-size: 0.67rem;">네이버 뉴스</td>
                            <td style="padding: 2.5px 2px; text-align: center; white-space: nowrap; color: #CBD5E1; font-size: 0.65rem;">최대 6건</td>
                            <td style="padding: 2.5px 4px; word-break: keep-all; font-size: 0.65rem; color: #CBD5E1;">주요 경제지 실시간 종목 보도</td>
                        </tr>
                        <tr style="border-bottom: 1px solid rgba(148, 163, 184, 0.18);">
                            <td style="padding: 2.5px 4px; font-weight: 600; font-size: 0.67rem;">Google 피드</td>
                            <td style="padding: 2.5px 2px; text-align: center; white-space: nowrap; color: #CBD5E1; font-size: 0.65rem;">최대 2건</td>
                            <td style="padding: 2.5px 4px; word-break: keep-all; font-size: 0.65rem; color: #CBD5E1;">{종목명} 분배금 특화 키워드</td>
                        </tr>
                        <tr>
                            <td style="padding: 3px 4px; font-weight: 700; color: #F59E0B; vertical-align: middle; border-right: 1px solid rgba(148, 163, 184, 0.12); font-size: 0.67rem; line-height: 1.15;">미국<br><span style="font-size: 0.60rem; color: #94A3B8; font-weight: 400;">주식·ETF</span></td>
                            <td style="padding: 2.5px 4px; font-weight: 600; font-size: 0.67rem;">글로벌 피드</td>
                            <td style="padding: 2.5px 2px; text-align: center; white-space: nowrap; color: #CBD5E1; font-size: 0.65rem;">최대 6건</td>
                            <td style="padding: 2.5px 4px; word-break: keep-all; font-size: 0.65rem; color: #CBD5E1;">배당 발표 및 글로벌 외신 실시간 동향</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 5px; padding: 3px 5px; margin-top: 3px; font-size: 0.64rem; line-height: 1.3; color: #94A3B8; word-break: keep-all;">
                <div style="margin-bottom: 2px;">
                    <b style="color: #CBD5E1;">🏷️ 분류:</b>
                    <span style="color: #34D399; font-weight: 600;">[배당/분배]</span> 분배금·월배당 &nbsp;·&nbsp;
                    <span style="color: #60A5FA; font-weight: 600;">[운용공시]</span> 보고서·DART &nbsp;·&nbsp;
                    <span style="color: #E2E8F0; font-weight: 600;">[시장이슈]</span> 실적·뉴스
                </div>
                <div>
                    <b style="color: #CBD5E1;">⚙️ 관리:</b>
                    중복 자동 차단 &nbsp;·&nbsp; 최신순 30건 정돈 &nbsp;·&nbsp; <b style="color: #F8FAFC;">[⭐ 스크랩]</b> 시 영구 보관
                </div>
            </div>
        </div>
    """).strip()

    try:
        st.html(html_content)
    except Exception:
        st.markdown(html_content, unsafe_allow_html=True)



# ------------------------------------------------------------------------------
# 독립 CLI 배치 실행 엔트리포인트 (GitHub Actions / 외부 크론 스케줄러 연동용)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FinScope 보유 종목 최신 뉴스 및 공시 수집 배치")
    parser.add_argument("--user-id", default=None, help="수집할 사용자 UUID (생략 시 데모 계정)")
    parser.add_argument("--limit", type=int, default=20, help="수집 후 조회할 출력 개수")
    cli_args = parser.parse_args()

    active_repo = PortfolioRepository()
    target_user_id = cli_args.user_id

    if not target_user_id:
        # 기본 데모 유저 ID 사용
        target_user_id = "00000000-0000-0000-0000-000000000001"
        print(f"[*] 사용자 ID 미지정. 기본 데모 계정({target_user_id})으로 실행합니다.")

    # 사용자의 보유 종목 조회
    items = active_repo.get_items(target_user_id)
    if not items:
        # 종목이 없을 경우 예시 ETF로 구성하여 수집 시연
        print("[!] 등록된 보유 종목이 없어 대표 ETF(TIGER 미국배당다우존스, ACE 미국SMR)로 수집을 진행합니다.")
        items = [
            {"ticker": "449170", "name": "TIGER 미국배당다우존스"},
            {"ticker": "487240", "name": "ACE 미국SMR"}
        ]

    print(f"[*] 총 {len(items)}개 종목에 대한 뉴스 및 공시 수집을 시작합니다...")
    result = fetch_and_store_disclosures(target_user_id, items, repo=active_repo)
    print(f"[+] 수집 결과: {result['message']} (총 {result['total_collected']}건 수집, {result['saved_count']}건 저장)")

    latest = get_latest_disclosures(target_user_id, limit=cli_args.limit, repo=active_repo)
    print(f"[*] DB 적재 최신 소식 상위 {len(latest)}건:")
    for idx, disc in enumerate(latest, 1):
        print(f"  {idx}. [{disc.get('category')}] [{disc.get('item_name')}] {disc.get('title')} ({disc.get('source')}, {disc.get('published_at')})")
