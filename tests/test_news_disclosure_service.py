"""
tests/test_news_disclosure_service.py
보유 종목 뉴스 및 공시 수집 서비스(news_disclosure_service) 단위 테스트
"""
import pytest
from unittest.mock import patch, MagicMock

from services.news_disclosure_service import (
    classify_disclosure_category,
    parse_published_at,
    fetch_disclosures_for_single_item,
    fetch_and_store_disclosures,
    get_latest_disclosures,
)
from db.portfolio_repo import PortfolioRepository


def test_classify_disclosure_category():
    # 1순위: 배당 / 분배
    assert classify_disclosure_category("TIGER 미국배당다우존스 10월 분배금 지급 안내") == "배당/분배"
    assert classify_disclosure_category("ACE 미국SMR 3분기 배당락 기준가 공시") == "배당/분배"
    assert classify_disclosure_category("월배당 ETF 열풍 지속", body="분배금이 전월 대비 증가") == "배당/분배"
    assert classify_disclosure_category("일반 기사", body="", source="수익분배팀") == "배당/분배"

    # 2순위: 운용공시 (분배 키워드가 없을 때)
    assert classify_disclosure_category("ETF지정참가회사(AP) 추가 및 계약 변경 안내") == "운용공시"
    assert classify_disclosure_category("합성ETF 거래상대방 순자본비율 공시") == "운용공시"
    assert classify_disclosure_category("신규 상장 및 집합투자규약 변경 보고") == "운용공시"
    assert classify_disclosure_category("신탁 계약 체결 보고", body="", source="KOSCOM") == "운용공시"

    # 3순위: 시장이슈
    assert classify_disclosure_category("코스피 외인 순매수 전환… 반도체주 강세") == "시장이슈"
    assert classify_disclosure_category("뉴욕증시 혼조세 마감… 빅테크 실적 대기") == "시장이슈"


def test_parse_published_at():
    # Naver Mobile News 'YYYYMMDDHHmm'
    iso1 = parse_published_at("202610192252")
    assert iso1 == "2026-10-19T22:52:00"

    # Naver Mobile News 'YYYYMMDDHHmmss'
    iso2 = parse_published_at("20261019225230")
    assert iso2 == "2026-10-19T22:52:30"

    # RFC 2822 GMT
    iso3 = parse_published_at("Thu, 15 Oct 2026 09:17:10 GMT")
    assert "2026-10-15T09:17:10" in iso3

    # Already ISO
    iso4 = parse_published_at("2026-07-22T06:51:37")
    assert iso4 == "2026-07-22T06:51:37"

    # None / Empty
    assert parse_published_at(None) is None
    assert parse_published_at("") is None


def test_portfolio_repo_disclosure_crud():
    # Supabase 미연결 상태(Mock 저장소)에서 save_disclosures 및 get_disclosures 검증
    repo = PortfolioRepository(client=None)
    test_user = "test-user-uuid-1234"

    items = [
        {
            "ticker": "449170",
            "item_name": "TIGER 미국배당다우존스",
            "title": "TIGER 미국배당 10월 분배금 발표",
            "source": "한국경제",
            "origin_url": "https://n.news.naver.com/mnews/article/001/0001",
            "published_at": "2026-10-19T10:00:00",
            "category": "배당/분배",
        },
        {
            "ticker": "449170",
            "item_name": "TIGER 미국배당다우존스",
            "title": "TIGER 미국배당 순자본비율 공시",
            "source": "KOSCOM",
            "origin_url": "https://finance.naver.com/item/notice_002",
            "published_at": "2026-10-19T12:00:00",
            "category": "운용공시",
        },
    ]

    saved_count, msg = repo.save_disclosures(test_user, items)
    assert saved_count == 2

    # 조회 시 published_at DESC 순서로 정렬 검증
    fetched = repo.get_disclosures(test_user, limit=10)
    assert len(fetched) == 2
    assert fetched[0]["origin_url"] == "https://finance.naver.com/item/notice_002"
    assert fetched[1]["origin_url"] == "https://n.news.naver.com/mnews/article/001/0001"

    # 동일 origin_url upsert(중복 URL 무시 또는 갱신) 검증
    updated_items = [
        {
            "ticker": "449170",
            "item_name": "TIGER 미국배당다우존스",
            "title": "TIGER 미국배당 10월 분배금 확정 (수정)",
            "source": "한국경제",
            "origin_url": "https://n.news.naver.com/mnews/article/001/0001",
            "published_at": "2026-10-19T14:00:00",
            "category": "배당/분배",
        }
    ]
    saved_count2, _ = repo.save_disclosures(test_user, updated_items)
    assert saved_count2 == 1

    fetched_after = repo.get_disclosures(test_user, limit=10)
    assert len(fetched_after) == 2  # 중복 추가되지 않고 2개 유지
    # 최신화된 published_at 기준으로 정렬
    assert fetched_after[0]["title"] == "TIGER 미국배당 10월 분배금 확정 (수정)"


def test_fetch_and_store_disclosures_empty():
    repo = PortfolioRepository(client=None)
    res = fetch_and_store_disclosures("user-1", [], repo=repo)
    assert res["status"] == "empty"
    assert res["saved_count"] == 0


def test_fetch_and_store_disclosures_mocked():
    repo = PortfolioRepository(client=None)
    test_user = "user-mock-5678"

    mock_records = [
        {
            "ticker": "449170",
            "item_name": "TIGER 미국배당다우존스",
            "title": "TIGER 분배금 공시",
            "source": "KOSCOM",
            "origin_url": "https://example.com/item1",
            "published_at": "2026-10-19T15:00:00",
            "category": "배당/분배",
        }
    ]

    with patch("services.news_disclosure_service.fetch_disclosures_for_single_item", return_value=mock_records):
        res = fetch_and_store_disclosures(test_user, [{"ticker": "449170", "name": "TIGER 미국배당다우존스"}], repo=repo)
        assert res["status"] == "success"
        assert res["saved_count"] == 1
        assert res["total_collected"] == 1

        latest = get_latest_disclosures(test_user, limit=5, repo=repo)
        assert len(latest) == 1
        assert latest[0]["title"] == "TIGER 분배금 공시"
