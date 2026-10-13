# 계좌 관리 및 ISA 절세 연동 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 다중 사용자 확장을 위해 `accounts` 계좌 관리 테이블을 신설하고, `portfolio_items`와 외래키로 조인 연동하며, Streamlit 모달 다이얼로그(`@st.dialog`) 기반 계좌 관리 UI 및 ISA 만기 D-Day/절세 AI 룰 엔진을 구현합니다.

**Architecture:** PostgreSQL Supabase 스키마(`accounts` 신설, `portfolio_items.account_id` 외래키 추가) 및 `PortfolioRepository` 계층에 계좌 CRUD/자동 시딩 로직을 추가합니다. 비즈니스 로직 계층(`services/portfolio_service.py`)에 ISA 만기(+3년) 계산, D-Day 산출, 세액공제(10%, 최대 300만) 룰 엔진을 구축하고, `pages/2_포트폴리오.py`에서 모달 다이얼로그와 연동합니다.

**Tech Stack:** Python 3.13, Streamlit >= 1.36.0, Supabase PostgreSQL, Pandas, Pytest, UV

**Spec:** [docs/superpowers/specs/2026-10-09-account-management-design.md](file:///e:/Antigravity/project/finance-support/docs/superpowers/specs/2026-10-09-account-management-design.md)

## Global Constraints
- Python 가상환경은 항상 `uv`만 사용 (`uv run pytest`)
- 파일 경로는 상대경로 및 markdown link (`file:///...`) 사용
- 기존 텍스트 기반 `account` 필드 및 레거시 데이터 조회 100% 하위 호환성 보장
- Supabase 미연결 환경(로컬 데모/Mock 모드)에서도 `_fallback_accounts`를 통해 동일 기능 보장

## Review Focus
1. 기존에 `account_id`가 NULL인 기존 보유 종목이 조회되거나 계좌 필터링될 때 누락 없이 정상 동작하는지 확인
2. 계좌 유형을 'ISA'로 선택했을 때 개설일 기준 정확히 +3년(36개월)이 만기일 기본값으로 자동 계산되는지 확인
3. ISA 만기 D-Day 계산 시 미래/당일/과거(경과) 날짜가 각각 `D-180`, `D-Day`, `D+30`으로 정확히 판정되는지 확인
4. ISA 만기 연금 전환 추가 세액공제 한도(전환액의 10%, 최대 300만 원)가 룰 엔진에서 정확히 산출되는지 확인
5. 계좌 삭제 시 연결된 종목이 함께 삭제되지 않고 `account_id`가 NULL 또는 '기본' 계좌로 안전 처리되는지 확인

---

### Task 1: Supabase DDL 스키마 확장 (`schema.sql`)

**Files:**
- Modify: `schema.sql:1-55`
- Test: `tests/test_portfolio_repo.py`

**Interfaces:**
- Produces: `accounts` DDL 및 `portfolio_items.account_id` 외래키 마이그레이션 SQL 스크립트

- [x] **Step 1: Write the failing test for schema definition check**

```python
def test_schema_contains_accounts_table():
    with open("schema.sql", "r", encoding="utf-8") as f:
        schema = f.read()
    assert "CREATE TABLE IF NOT EXISTS accounts" in schema
    assert "account_id UUID REFERENCES accounts(id)" in schema
    assert "account_type VARCHAR(20) NOT NULL CHECK" in schema
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_portfolio_repo.py::test_schema_contains_accounts_table -v`
Expected: FAIL with assertion error

- [x] **Step 3: Update `schema.sql`**

`accounts` 테이블 생성 DDL(UUID, user_id, broker_name, account_alias, account_type, opened_at, maturity_at) 및 `portfolio_items.account_id` 외래키 추가 DDL 작성.

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_portfolio_repo.py::test_schema_contains_accounts_table -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add schema.sql tests/test_portfolio_repo.py
git commit -m "feat(db): add accounts table and foreign key to schema.sql"
```

---

### Task 2: Repository Layer - Account CRUD 및 Auto-seed 구현 (`db/portfolio_repo.py`)

**Files:**
- Modify: `db/portfolio_repo.py:30-374`
- Test: `tests/test_portfolio_repo.py`

**Interfaces:**
- Consumes: `schema.sql`의 `accounts` 및 `portfolio_items` 테이블 구조
- Produces:
  - `get_accounts(user_id: str) -> list[dict]`
  - `create_account(user_id: str, account_data: dict) -> tuple[bool, Optional[dict], str]`
  - `delete_account(account_id: str) -> tuple[bool, str]`
  - `auto_seed_accounts_from_items(user_id: str) -> list[dict]`

- [x] **Step 1: Write failing tests for accounts CRUD and auto-seed**

```python
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
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_portfolio_repo.py::test_accounts_crud_and_autoseed -v`
Expected: FAIL with AttributeError (`get_accounts` not found)

- [x] **Step 3: Implement Account CRUD & Auto-seed in `db/portfolio_repo.py`**

- `_fallback_accounts` Mock 딕셔너리 구성 및 초기 데모 계좌 데이터 세팅
- `get_accounts`, `create_account`, `delete_account`, `auto_seed_accounts_from_items` 구현 (Supabase Client 및 Mock 모드 양방향 지원)
- `add_item`, `update_item` 시 `account_id` 파라미터 연동 지원

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_portfolio_repo.py::test_accounts_crud_and_autoseed -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add db/portfolio_repo.py tests/test_portfolio_repo.py
git commit -m "feat(repo): implement account CRUD and auto-seeding"
```

---

### Task 3: Service Layer - ISA 만기일, D-Day 및 절세 AI 룰 엔진 (`services/portfolio_service.py`)

**Files:**
- Modify: `services/portfolio_service.py:1-427`
- Test: `tests/test_portfolio_service.py`

**Interfaces:**
- Consumes: `accounts` 레코드 딕셔너리 (`maturity_at`, `account_type`, `broker_name` 등)
- Produces:
  - `calculate_isa_default_maturity(opened_at: str | datetime.date) -> datetime.date`
  - `calculate_isa_dday(maturity_at: str | datetime.date, base_date: Optional[datetime.date] = None) -> dict[str, Any]`
  - `evaluate_isa_tax_advice(account: dict, summary: dict) -> Optional[dict[str, Any]]`

- [x] **Step 1: Write failing tests for ISA D-Day and tax advice rule engine**

```python
from datetime import date
from services.portfolio_service import (
    calculate_isa_default_maturity,
    calculate_isa_dday,
    evaluate_isa_tax_advice
)

def test_calculate_isa_default_maturity():
    opened = date(2024, 5, 10)
    expected_maturity = date(2027, 5, 10)
    assert calculate_isa_default_maturity(opened) == expected_maturity

def test_calculate_isa_dday():
    today = date(2026, 10, 9)
    # 1. 만기 전
    res_future = calculate_isa_dday(date(2027, 4, 7), base_date=today)
    assert res_future["d_day"] == 180
    assert res_future["label"] == "D-180"
    assert res_future["status"] == "active"

    # 2. 오늘 만기
    res_today = calculate_isa_dday(today, base_date=today)
    assert res_today["d_day"] == 0
    assert res_today["label"] == "D-Day"
    assert res_today["status"] == "due"

    # 3. 만기 경과
    res_past = calculate_isa_dday(date(2026, 9, 9), base_date=today)
    assert res_past["d_day"] == -30
    assert res_past["label"] == "D+30"
    assert res_past["status"] == "expired"

def test_evaluate_isa_tax_advice():
    account = {
        "account_type": "ISA",
        "broker_name": "미래에셋",
        "account_alias": "절세ISA",
        "maturity_at": "2026-10-15"
    }
    summary = {
        "total_eval": 40_000_000.0
    }
    advice = evaluate_isa_tax_advice(account, summary)
    assert advice is not None
    assert advice["max_deduction"] == 3_000_000.0  # 4000만의 10% = 400만 -> 한도 300만
    assert "연금계좌" in advice["title"]
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_portfolio_service.py::test_calculate_isa_default_maturity -v`
Expected: FAIL with ImportError

- [x] **Step 3: Implement business logic in `services/portfolio_service.py`**

- `calculate_isa_default_maturity` 구현 (개설일 + 3년)
- `calculate_isa_dday` 구현 (날짜 차이 계산 및 배지 상태 판정)
- `evaluate_isa_tax_advice` 구현 (조세특례제한법 기반 세액공제 10%, 최대 300만 원 한도 및 맞춤 어드바이스 생성)

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_portfolio_service.py::test_calculate_isa_default_maturity tests/test_portfolio_service.py::test_calculate_isa_dday tests/test_portfolio_service.py::test_evaluate_isa_tax_advice -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add services/portfolio_service.py tests/test_portfolio_service.py
git commit -m "feat(service): add ISA maturity calculation and tax advice rule engine"
```

---

### Task 4: UI Layer - 계좌 관리 모달 다이얼로그 및 종목 등록/수정 폼 연동 (`pages/2_포트폴리오.py`)

**Files:**
- Modify: `pages/2_포트폴리오.py:1180-1460`
- Test: `tests/test_ui_smoke.py`

**Interfaces:**
- Consumes: `repo.get_accounts`, `repo.create_account`, `repo.delete_account`, `calculate_isa_default_maturity`
- Produces: `@st.dialog("🏦 계좌 관리 및 신규 등록")` 모달 및 종목 등록/수정 폼의 계좌 목록 동적 연동

- [x] **Step 1: Write failing UI smoke test for account management dialog**

```python
def test_account_management_dialog_elements():
    with open("pages/2_포트폴리오.py", "r", encoding="utf-8") as f:
        code = f.read()
    assert "manage_accounts_dialog" in code
    assert "repo.get_accounts" in code
    assert "repo.create_account" in code
    assert "calculate_isa_default_maturity" in code
    assert "➕ 계좌 관리" in code
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui_smoke.py::test_account_management_dialog_elements -v`
Expected: FAIL with assertion error

- [x] **Step 3: Implement modal dialog and account selectbox in `pages/2_포트폴리오.py`**

1. `@st.dialog("🏦 계좌 관리 및 신규 등록", width="medium") def manage_accounts_dialog(user_id, repo):` 모달 구현:
   - 신규 계좌 폼: 증권사 선택, 계좌 유형(일반, ISA, 연금저축, IRP), 별칭, 개설일, 만기일(ISA 선택 시 +3년 자동 계산)
   - 등록된 계좌 목록 및 삭제 버튼
2. [신규 보유 종목 등록] 폼 및 [보유 정보 직접 수정] 폼의 계좌 셀렉트박스를 사용자 계좌 목록(`"{broker_name} - {alias/type}"`)으로 바인딩.
3. 드롭다운 옆에 `[➕ 계좌 관리]` 버튼 배치하여 다이얼로그 호출.
4. 종목 저장 시 `account_id`와 `account` 동시 저장.

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ui_smoke.py::test_account_management_dialog_elements -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add pages/2_포트폴리오.py tests/test_ui_smoke.py
git commit -m "feat(ui): add account management dialog and dynamic account selectbox"
```

---

### Task 5: UI Layer - 상단 계좌 필터, ISA 만기 D-Day 배지 및 절세 AI 어드바이스 카드 연동 (`pages/2_포트폴리오.py`)

**Files:**
- Modify: `pages/2_포트폴리오.py:230-310, 840-950`
- Test: `tests/test_ui_smoke.py`

**Interfaces:**
- Consumes: `calculate_isa_dday`, `evaluate_isa_tax_advice`, `repo.get_accounts`
- Produces: 상단 계좌 필터 D-Day 뱃지 UI 및 ISA 절세 AI 어드바이스 카드 UI

- [x] **Step 1: Write failing UI smoke test for D-Day badge and ISA advice card**

```python
def test_isa_dday_and_tax_advice_ui():
    with open("pages/2_포트폴리오.py", "r", encoding="utf-8") as f:
        code = f.read()
    assert "calculate_isa_dday" in code
    assert "evaluate_isa_tax_advice" in code
    assert "ISA 만기" in code
    assert "badge-tag" in code
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui_smoke.py::test_isa_dday_and_tax_advice_ui -v`
Expected: FAIL with assertion error

- [x] **Step 3: Implement D-Day badge and ISA advice card in `pages/2_포트폴리오.py`**

1. 상단 계좌 필터에서 `ISA` 계좌 선택 시:
   - 만기일이 있으면 `calculate_isa_dday`를 호출하여 필터 옆에 `⏳ 만기 D-180` 배지 렌더링.
   - `evaluate_isa_tax_advice`를 호출하여 필터 하단 및 AI 추천 탭 상단에 절세 AI 어드바이스 카드 렌더링.
2. 필터링 로직에서 `account_id` 매핑 및 레거시 텍스트 `account` 동시 지원.

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ui_smoke.py::test_isa_dday_and_tax_advice_ui -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add pages/2_포트폴리오.py tests/test_ui_smoke.py
git commit -m "feat(ui): render ISA D-Day badge and tax advice card"
```

---

### Task 6: 전체 회귀 테스트 및 엔드투엔드 검증

**Files:**
- Test: `tests/` 전체 테스트 스위트

- [x] **Step 1: Run full test suite with `uv run pytest`**

Run: `uv run pytest -v`
Expected: All tests pass (>= 40 passed)

- [x] **Step 2: Verify smoke tests and formatting**

Check code style and syntax error across all files.

- [x] **Step 3: Final Commit**

```bash
git commit -m "chore: complete accounts management and ISA tax advice integration"
```
