"""
tests/test_scrap_service.py
개인 기사/공시 스크랩북 서비스 단위 테스트
"""
import pytest
from db.portfolio_repo import PortfolioRepository
from services.scrap_service import (
    save_scrap,
    get_scraps,
    update_scrap_memo,
    delete_scrap,
    get_scraped_urls,
)


def test_scrap_crud_flow():
    repo = PortfolioRepository(client=None)
    user_id = "test-scrap-user-123"

    # 1. 초기 상태: 스크랩 없음
    scraps_init = get_scraps(user_id, repo=repo)
    assert len(scraps_init) == 0
    urls_init = get_scraped_urls(user_id, repo=repo)
    assert len(urls_init) == 0

    # 2. 기사 스크랩 저장
    ok, msg, item1 = save_scrap(
        user_id=user_id,
        ticker="449170",
        item_name="TIGER 미국배당다우존스",
        title="10월 분배금 주당 38원 확정 공시",
        origin_url="https://finance.naver.com/news/101",
        source="한국경제",
        memo="분할매수 진입 검토",
        repo=repo
    )
    assert ok is True
    assert item1 is not None
    assert item1["title"] == "10월 분배금 주당 38원 확정 공시"

    # 3. 추가 스크랩 저장 (다른 기사)
    ok2, _, item2 = save_scrap(
        user_id=user_id,
        ticker="0155M0",
        item_name="ACE 미국SMR원자력TOP10",
        title="글로벌 빅테크 SMR 전력 계약 발표",
        origin_url="https://finance.naver.com/news/102",
        source="매일경제",
        memo="원전 테마 관심",
        repo=repo
    )
    assert ok2 is True

    # 4. 목록 조회 (전체)
    scraps = get_scraps(user_id, ticker_filter="전체", repo=repo)
    assert len(scraps) == 2

    # 5. 종목 필터링 조회
    tiger_scraps = get_scraps(user_id, ticker_filter="TIGER 미국배당다우존스", repo=repo)
    assert len(tiger_scraps) == 1
    assert tiger_scraps[0]["ticker"] == "449170"

    ace_scraps = get_scraps(user_id, ticker_filter="0155M0", repo=repo)
    assert len(ace_scraps) == 1
    assert ace_scraps[0]["item_name"] == "ACE 미국SMR원자력TOP10"

    # 6. 스크랩 URL 집합 조회
    urls = get_scraped_urls(user_id, repo=repo)
    assert "https://finance.naver.com/news/101" in urls
    assert "https://finance.naver.com/news/102" in urls

    # 7. 동일 기사 중복 저장 시 메모 업데이트 (Upsert)
    ok_up, _, updated_item = save_scrap(
        user_id=user_id,
        ticker="449170",
        item_name="TIGER 미국배당다우존스",
        title="10월 분배금 주당 38원 확정 공시",
        origin_url="https://finance.naver.com/news/101",
        source="한국경제",
        memo="메모 수정: 추가 매수 완료!",
        repo=repo
    )
    assert ok_up is True
    scraps_after_dup = get_scraps(user_id, repo=repo)
    assert len(scraps_after_dup) == 2  # 개수 증가 없이 메모만 업데이트
    assert scraps_after_dup[1]["memo"] == "메모 수정: 추가 매수 완료!"

    # 8. 메모 직접 수정 (update_scrap_memo)
    scrap_id = item2["id"]
    ok_memo, _ = update_scrap_memo(scrap_id=scrap_id, new_memo="SMR 비중 확대 완료", repo=repo)
    assert ok_memo is True
    scraps_updated = get_scraps(user_id, repo=repo)
    updated_item2 = next(s for s in scraps_updated if s["id"] == scrap_id)
    assert updated_item2["memo"] == "SMR 비중 확대 완료"

    # 9. 삭제 (delete_scrap)
    ok_del, _ = delete_scrap(scrap_id=scrap_id, repo=repo)
    assert ok_del is True
    scraps_final = get_scraps(user_id, repo=repo)
    assert len(scraps_final) == 1
    urls_final = get_scraped_urls(user_id, repo=repo)
    assert "https://finance.naver.com/news/102" not in urls_final


def test_save_scrap_validation():
    repo = PortfolioRepository(client=None)
    # 필수값 누락 시 실패
    ok1, msg1, _ = save_scrap(user_id="", ticker="A", item_name="B", title="C", origin_url="http://x", repo=repo)
    assert ok1 is False

    ok2, msg2, _ = save_scrap(user_id="u1", ticker="A", item_name="B", title="", origin_url="http://x", repo=repo)
    assert ok2 is False

    ok3, msg3, _ = save_scrap(user_id="u1", ticker="A", item_name="B", title="T", origin_url="", repo=repo)
    assert ok3 is False
