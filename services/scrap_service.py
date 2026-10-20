"""
services/scrap_service.py
개인 기사 및 공시 스크랩북 비즈니스 로직 모듈.
포트폴리오 페이지 및 스크랩북 관리 페이지에서 재사용됩니다.
"""
import logging
from typing import Optional, Any

from db.portfolio_repo import PortfolioRepository

logger = logging.getLogger(__name__)


def _ensure_repo(repo: Optional[PortfolioRepository] = None) -> PortfolioRepository:
    """PortfolioRepository 인스턴스를 보장하며 필요시 최신 클래스로 동적 리로드합니다."""
    if repo is None or not hasattr(repo, "save_scrap"):
        import importlib
        import db.portfolio_repo
        importlib.reload(db.portfolio_repo)
        return db.portfolio_repo.PortfolioRepository()
    return repo


def save_scrap(
    user_id: str,
    ticker: str,
    item_name: str,
    title: str,
    origin_url: str,
    source: str = "",
    memo: str = "",
    repo: Optional[PortfolioRepository] = None
) -> tuple[bool, str, Optional[dict]]:
    """
    기사를 스크랩북에 추가하거나 메모를 갱신합니다 (Upsert).
    """
    active_repo = _ensure_repo(repo)
    return active_repo.save_scrap(
        user_id=user_id,
        ticker=ticker,
        item_name=item_name,
        title=title,
        origin_url=origin_url,
        source=source,
        memo=memo
    )


def get_scraps(
    user_id: str,
    ticker_filter: str = "전체",
    repo: Optional[PortfolioRepository] = None
) -> list[dict]:
    """
    사용자의 스크랩 목록을 최신순(created_at DESC)으로 조회합니다.
    """
    active_repo = _ensure_repo(repo)
    return active_repo.get_scraps(user_id=user_id, ticker_filter=ticker_filter)


def update_scrap_memo(
    scrap_id: str,
    new_memo: str,
    user_id: Optional[str] = None,
    repo: Optional[PortfolioRepository] = None
) -> tuple[bool, str]:
    """
    기존 저장된 스크랩 항목의 메모를 수정합니다.
    """
    active_repo = _ensure_repo(repo)
    return active_repo.update_scrap_memo(scrap_id=scrap_id, new_memo=new_memo, user_id=user_id)


def delete_scrap(
    scrap_id: str,
    user_id: Optional[str] = None,
    repo: Optional[PortfolioRepository] = None
) -> tuple[bool, str]:
    """
    스크랩 항목을 삭제합니다.
    """
    active_repo = _ensure_repo(repo)
    return active_repo.delete_scrap(scrap_id=scrap_id, user_id=user_id)


def get_scraped_urls(
    user_id: str,
    repo: Optional[PortfolioRepository] = None
) -> set[str]:
    """
    이미 스크랩한 기사들의 URL 집합(Set)을 반환하여 UI 상의 버튼 상태 표시에 활용합니다.
    """
    active_repo = _ensure_repo(repo)
    return active_repo.get_scraped_urls(user_id=user_id)
