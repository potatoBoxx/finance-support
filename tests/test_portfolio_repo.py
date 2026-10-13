import pytest
from db.portfolio_repo import hash_pin, PortfolioRepository
from db.supabase_client import is_supabase_configured, get_supabase_client

def test_hash_pin():
    pin = "1234"
    h1 = hash_pin(pin)
    assert len(h1) == 64
    assert h1 == hash_pin("1234")
    assert h1 != hash_pin("5678")

def test_mock_fallback_mode_authentication_and_crud():
    # client=None 강제 주입하여 Graceful Fallback(Mock 모드) 테스트
    repo = PortfolioRepository(client=None)
    assert repo.is_demo_mode() is True

    # 1. 데모 유저 기본 로그인
    ok, demo_user, msg = repo.authenticate_or_create_user("demo", "1234")
    assert ok is True
    assert demo_user["username"] == "demo"
    assert "환영합니다" in msg

    # 데모 유저 초기 종목 확인
    items = repo.get_items(demo_user["id"])
    assert len(items) >= 2
    tickers = [item["ticker"] for item in items]
    assert "005930" in tickers
    # 데모 유저의 종목에는 account 필드가 존재해야 함
    assert all("account" in item and item["account"] for item in items)

    # 2. 신규 유저 생성
    ok, new_user, msg = repo.authenticate_or_create_user("investor99", "7777")
    assert ok is True
    assert new_user["username"] == "investor99"
    assert "생성" in msg

    # 3. 잘못된 PIN 테스트
    ok_fail, user_fail, msg_fail = repo.authenticate_or_create_user("investor99", "0000")
    assert ok_fail is False
    assert user_fail is None
    assert "일치하지 않습니다" in msg_fail

    # 4. 종목 등록 (정상 - 기본 계좌)
    item_data = {
        "market": "KRX",
        "ticker": "000660",
        "name": "SK하이닉스",
        "buy_price": 180000,
        "quantity": 5,
        "target_price": 220000,
        "stop_loss_price": 160000,
        "memo": "HBM 주도주",
        "account": "키움증권"
    }
    add_ok, add_msg = repo.add_item(new_user["id"], item_data)
    assert add_ok is True
    assert "등록되었습니다" in add_msg

    # 5. 동일 계좌 내 중복 종목 등록 시도 (실패해야 함)
    add_dup_ok, add_dup_msg = repo.add_item(new_user["id"], item_data)
    assert add_dup_ok is False
    assert "이미" in add_dup_msg

    # 5-1. 동일 종목이지만 다른 계좌로 등록 시도 (성공해야 함)
    diff_acc_item = dict(item_data)
    diff_acc_item["account"] = "토스증권"
    diff_acc_item["quantity"] = 3
    add_diff_ok, add_diff_msg = repo.add_item(new_user["id"], diff_acc_item)
    assert add_diff_ok is True
    assert "등록되었습니다" in add_diff_msg

    # 6. 유효성 검사 (0 이하 가격)
    bad_item = dict(item_data)
    bad_item["ticker"] = "035420"
    bad_item["buy_price"] = -100
    bad_ok, bad_msg = repo.add_item(new_user["id"], bad_item)
    assert bad_ok is False
    assert "0보다 커야" in bad_msg

    # 7. 목록 조회 (동일 종목 2개 계좌 분리 확인)
    user_items = repo.get_items(new_user["id"])
    assert len(user_items) == 2
    accounts = {it["account"] for it in user_items}
    assert accounts == {"키움증권", "토스증권"}
    target_item_id = [it["id"] for it in user_items if it["account"] == "키움증권"][0]

    # 8. 종목 수정 (계좌 변경 포함)
    update_data = {
        "buy_price": 185000,
        "quantity": 8,
        "target_price": 230000,
        "stop_loss_price": 165000,
        "memo": "수량 추가 매수",
        "account": "미래에셋"
    }
    update_ok, update_msg = repo.update_item(target_item_id, update_data)
    assert update_ok is True

    # 수정 결과 확인
    updated_items = repo.get_items(new_user["id"])
    updated_target = [it for it in updated_items if it["id"] == target_item_id][0]
    assert updated_target["quantity"] == 8
    assert updated_target["buy_price"] == 185000
    assert updated_target["account"] == "미래에셋"

    # 9. 종목 삭제
    del_ok, del_msg = repo.delete_item(target_item_id)
    assert del_ok is True
    remaining_items = repo.get_items(new_user["id"])
    assert len(remaining_items) == 1
    assert remaining_items[0]["account"] == "토스증권"

    # 나머지 종목도 삭제
    repo.delete_item(remaining_items[0]["id"])
    assert len(repo.get_items(new_user["id"])) == 0

def test_schema_contains_accounts_table():
    with open("schema.sql", "r", encoding="utf-8") as f:
        schema = f.read()
    assert "CREATE TABLE IF NOT EXISTS accounts" in schema
    assert "account_id UUID REFERENCES accounts(id)" in schema
    assert "account_type VARCHAR(20) NOT NULL CHECK" in schema

def test_accounts_crud_and_autoseed():
    from db.portfolio_repo import PortfolioRepository
    repo = PortfolioRepository(client=None)
    demo_uid = "00000000-0000-0000-0000-000000000001"

    # 1. 자동 시딩 검증
    accounts = repo.get_accounts(demo_uid)
    assert len(accounts) >= 1
    broker_names = [a["broker_name"] for a in accounts]
    assert "토스증권" in broker_names or "키움증권" in broker_names

    # 2. 신규 계좌 생성 검증
    ok, new_acc, msg = repo.create_account(demo_uid, {
        "broker_name": "미래에셋",
        "account_alias": "절세ISA",
        "account_type": "ISA",
        "opened_at": "2024-01-01",
        "maturity_at": "2027-01-01"
    })
    assert ok is True
    assert new_acc["account_type"] == "ISA"

    # 3. 계좌 목록 재조회 검증
    updated_accs = repo.get_accounts(demo_uid)
    assert any(a["account_alias"] == "절세ISA" for a in updated_accs)

    # 4. 계좌 삭제 검증
    del_ok, _ = repo.delete_account(new_acc["id"])
    assert del_ok is True

def test_accounts_edge_cases():
    from db.portfolio_repo import PortfolioRepository
    repo = PortfolioRepository(client=None)
    uid = "test-user-edge-case"

    # 유효하지 않은 계좌 유형 검증
    ok, acc, msg = repo.create_account(uid, {
        "broker_name": "KB증권",
        "account_type": "유효하지않음"
    })
    assert ok is False
    assert "지원하지 않는" in msg

    # 빈 계좌 목록에서 auto-seed 검증 (신규 유저 기본값 생성)
    seeded = repo.get_accounts(uid)
    assert len(seeded) >= 1
    assert seeded[0]["broker_name"] == "토스증권"

    # 계좌 연동된 종목 생성 후 계좌 삭제 시 종목 보존 및 account_id=None 검증
    acc_id = seeded[0]["id"]
    item_ok, _ = repo.add_item(uid, {
        "market": "KRX",
        "ticker": "005930",
        "name": "삼성전자",
        "buy_price": 70000,
        "quantity": 10,
        "account": "토스증권",
        "account_id": acc_id
    })
    assert item_ok is True

    items_before = repo.get_items(uid)
    assert items_before[0]["account_id"] == acc_id

    # 계좌 삭제
    del_ok, _ = repo.delete_account(acc_id)
    assert del_ok is True

    # 종목은 유지되나 account_id는 None으로 설정됨
    items_after = repo.get_items(uid)
    assert len(items_after) == 1
    assert items_after[0]["account_id"] is None


def test_daily_briefing_caching():
    from db.portfolio_repo import PortfolioRepository
    repo = PortfolioRepository(client=None)
    uid = "test-briefing-user"
    today_str = "2026-10-11"

    # 1. 초기 상태: 브리핑 없음
    assert repo.get_daily_briefing(uid, today_str) is None

    # 2. 브리핑 저장
    mock_content = {
        "summary_metrics": {"total_eval": 50000000.0},
        "market_benchmark": {"status_tag": "시장 대비 선방"},
        "risk_analysis": {"level": "안정"}
    }
    saved = repo.save_daily_briefing(uid, today_str, mock_content)
    assert saved is True

    # 3. 브리핑 조회 및 무결성 확인
    loaded = repo.get_daily_briefing(uid, today_str)
    assert loaded is not None
    assert loaded["summary_metrics"]["total_eval"] == 50000000.0
    assert loaded["risk_analysis"]["level"] == "안정"

    # 4. 다른 날짜 또는 다른 유저는 None
    assert repo.get_daily_briefing(uid, "2026-10-12") is None
    assert repo.get_daily_briefing("other-user", today_str) is None

    # 5. 빈 입력값 방어
    assert repo.save_daily_briefing("", today_str, mock_content) is False
    assert repo.save_daily_briefing(uid, "", mock_content) is False
    assert repo.get_daily_briefing("", today_str) is None



