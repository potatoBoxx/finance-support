# FinScope 개인 투자 분석 대시보드 구현 계획서 (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Streamlit과 Supabase(PostgreSQL) 기반의 반응형 개인 투자 분석 대시보드를 구축하고, GitHub 및 Streamlit Community Cloud에 무료 배포할 수 있는 완전한 소프트웨어를 완성한다.

**Architecture:** UI(Streamlit 멀티페이지), 서비스 계층(Npay 증권 API, yfinance 지수, 퀀트 스코어링, 손익 계산), DB 영속성 계층(Supabase PostgreSQL + 로컬 데모 폴백)으로 명확히 분리된 레이어드 아키텍처를 채택한다. 외부 API는 Streamlit 캐시(`@st.cache_data`)를 활용하여 인메모리로 초고속 서빙하며, 세션 상태 방어 코드로 멀티페이지 안정성을 보장한다.

**Tech Stack:** Python 3.10+, Streamlit (>=1.36.0), Pandas (>=2.0.0), NumPy, Supabase (supabase-py >=2.5.0), yfinance (>=0.2.40), Requests, Plotly, pytest, uv

**Spec:** [docs/superpowers/specs/2026-10-04-finance-dashboard-design.md](file:///e:/Antigravity/project/finance-support/docs/superpowers/specs/2026-10-04-finance-dashboard-design.md)

## Global Constraints

- Python 가상환경은 반드시 `uv`만을 사용하여 관리한다.
- 파일 참조 및 코드 경로 작성 시 특별한 시스템 제약이 없는 한 상대경로를 사용한다.
- Npay 증권 API 요청 시 User-Agent 헤더를 필수 지정하여 차단을 방지한다.
- Npay 데이터 캐싱은 `@st.cache_data(ttl=1800)`, 지수 데이터는 `@st.cache_data(ttl=900)`을 엄수한다.
- 사용자 PIN은 SHA-256 해시값으로만 처리 및 저장하며, 평문 PIN을 DB에 보관하지 않는다.
- Supabase 미연동 또는 네트워크 오류 발생 시 크래시 없이 로컬 인메모리 데모 모드로 안전하게 폴백한다.
- `app.py` 및 모든 하위 `pages/*.py` 상단에 `ensure_session_state()` 세션 방어 코드를 배치한다.

## Review Focus

1. **Npay 해외 API 응답 포맷 차이**: 국내 ETF 응답(`result.etfItemList`)과 미국 주식 응답(`result.stockList`)의 키 구조가 다를 때 어댑터가 KeyError 없이 동일 DataFrame 스키마(`ticker`, `name`, `current_price`, `change_rate`, `trading_value`, `market`)로 변환하는지 검증.
2. **Supabase 미설정 / 연결 불가 환경**: `.streamlit/secrets.toml`이 없거나 DB 장애 시 앱이 중단되지 않고 데모 모드로 정상 렌더링 및 CRUD 동작을 유지하는지 검증.
3. **직접 URL 접근 시 세션 손실 방어**: 사용자가 `app.py`를 거치지 않고 `pages/2_포트폴리오.py`로 직접 새로고침했을 때 `st.session_state` 누락 오류 없이 기본 상태로 렌더링되는지 검증.
4. **손절가 도달 판정 (🚨)**: 현재가가 손절가 이하(`current_price <= stop_loss_price`)일 때 정확히 손절 경고 플래그(`is_stop_loss = True`)가 계산되는지 검증.
5. **0 수량 또는 음수 입력 검증**: 종목 등록 폼에서 수량 <= 0 또는 매수가 <= 0인 비정상 입력값에 대한 사전 유효성 검사 검증.

---

## Task Decomposition

### Task 1: 환경 설정 및 프로젝트 스캐폴딩

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `.streamlit/config.toml`
- Create: `.streamlit/secrets.toml.example`
- Create: `assets/style.css`
- Create: `.gitignore`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: 패키지 의존성 정의, Streamlit 테마 설정, 기본 CSS 스타일시트, 테스트 환경

- [ ] **Step 1: Write the failing test for configuration files**

```python
# tests/test_config.py
import os
import toml

def test_requirements_file_exists_and_contains_dependencies():
    assert os.path.exists("requirements.txt")
    with open("requirements.txt", encoding="utf-8") as f:
        content = f.read()
    for pkg in ["streamlit", "pandas", "supabase", "yfinance", "requests", "pytest"]:
        assert pkg in content.lower()

def test_streamlit_config_exists():
    assert os.path.exists(".streamlit/config.toml")
    config = toml.load(".streamlit/config.toml")
    assert "theme" in config
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`  
Expected: FAIL with `AssertionError: assert False` (files do not exist yet)

- [ ] **Step 3: Implement configuration files and styling**

- `requirements.txt`: streamlit, pandas, numpy, requests, supabase, yfinance, plotly, pytest, toml
- `pytest.ini`: `pythonpath = .` 및 테스트 옵션 정의
- `.streamlit/config.toml`: 다크 테마 설정 (`base = "dark"`, `primaryColor = "#3B82F6"`, `backgroundColor = "#0E1117"`)
- `.streamlit/secrets.toml.example`: `SUPABASE_URL`, `SUPABASE_KEY` 가이드 주석
- `assets/style.css`: 카드 디자인, 배지, 반응형 그리드 CSS
- `.gitignore`: `.venv/`, `.streamlit/secrets.toml`, `__pycache__/`, `.pytest_cache/`

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`  
Expected: PASS

---

### Task 2: Supabase DDL 및 데이터베이스 계층 (클라이언트 & 레포지토리)

**Files:**
- Create: `schema.sql`
- Create: `db/__init__.py`
- Create: `db/supabase_client.py`
- Create: `db/portfolio_repo.py`
- Test: `tests/test_portfolio_repo.py`

**Interfaces:**
- Consumes: `.streamlit/secrets.toml` (환경 변수 또는 Streamlit secrets)
- Produces:
  - `get_supabase_client() -> Optional[Client]`
  - `hash_pin(pin: str) -> str`
  - `authenticate_or_create_user(username: str, pin: str) -> tuple[bool, Optional[dict], str]`
  - `get_portfolio(user_id: str) -> list[dict]`
  - `add_portfolio_item(user_id: str, item_data: dict) -> bool`
  - `update_portfolio_item(item_id: str, item_data: dict) -> bool`
  - `delete_portfolio_item(item_id: str) -> bool`

- [ ] **Step 1: Write the failing test for db repository**

```python
# tests/test_portfolio_repo.py
import pytest
from db.portfolio_repo import hash_pin, PortfolioRepository

def test_hash_pin():
    pin = "1234"
    hashed = hash_pin(pin)
    assert len(hashed) == 64
    assert hashed == hash_pin("1234")
    assert hashed != hash_pin("5678")

def test_mock_fallback_repository():
    # Supabase 클라이언트가 None일 때 인메모리 데모 모드로 CRUD 동작
    repo = PortfolioRepository(client=None)
    success, user, msg = repo.authenticate_user("testuser", "1234")
    assert success is True
    assert user["username"] == "testuser"
    
    # 종목 추가
    item = {"market": "KRX", "ticker": "005930", "name": "삼성전자", "buy_price": 70000, "quantity": 10}
    add_ok = repo.add_item(user["id"], item)
    assert add_ok is True
    
    # 목록 조회
    items = repo.get_items(user["id"])
    assert len(items) == 1
    assert items[0]["ticker"] == "005930"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_portfolio_repo.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'db'`

- [ ] **Step 3: Implement `schema.sql`, `db/supabase_client.py` and `db/portfolio_repo.py`**

- `schema.sql`: spec 3.1절에 정의된 DDL (users, portfolio_items, 인덱스, RLS 정책)
- `db/supabase_client.py`: `st.secrets`에서 URL/Key 확인 후 클라이언트 인스턴스 반환 (실패 시 None 반환 및 로깅)
- `db/portfolio_repo.py`: SHA-256 PIN 해싱, Supabase 연동 CRUD + 클라이언트 부재 시 인메모리 딕셔너리 기반 Mock Fallback 구현

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_portfolio_repo.py -v`  
Expected: PASS

---

### Task 3: Npay 증권 API 어댑터 및 퀀트 Top 3 스코어링 서비스

**Files:**
- Create: `services/__init__.py`
- Create: `services/npay_service.py`
- Test: `tests/test_npay_service.py`

**Interfaces:**
- Produces:
  - `normalize_market_data(raw_data: dict, market: str) -> pd.DataFrame`
  - `fetch_npay_items(market: str) -> pd.DataFrame`
  - `calculate_top3_quant(df: pd.DataFrame) -> pd.DataFrame`

- [ ] **Step 1: Write the failing test for Npay normalizer and quant scoring**

```python
# tests/test_npay_service.py
import pandas as pd
import pytest
from services.npay_service import normalize_market_data, calculate_top3_quant

def test_normalize_domestic_data():
    sample_domestic_raw = {
        "result": {
            "etfItemList": [
                {"itemcode": "069500", "itemname": "KODEX 200", "nowVal": 35000, "changeRate": 1.25, "amount": 50000000},
                {"itemcode": "379800", "itemname": "KODEX 미국S&P500TR", "nowVal": 18000, "changeRate": -0.5, "amount": 30000000}
            ]
        }
    }
    df = normalize_market_data(sample_domestic_raw, "KRX")
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["ticker", "name", "current_price", "change_rate", "trading_value", "market"]
    assert len(df) == 2
    assert df.iloc[0]["ticker"] == "069500"
    assert df.iloc[0]["market"] == "KRX"

def test_normalize_global_data():
    sample_global_raw = {
        "result": {
            "stockList": [
                {"reutersCode": "AAPL.O", "stockName": "Apple Inc", "closePrice": "220.5", "fluctuationsRatio": "2.1", "marketValue": 3000000000},
                {"reutersCode": "NVDA.O", "stockName": "NVIDIA Corp", "closePrice": "125.0", "fluctuationsRatio": "-1.5", "marketValue": 2500000000}
            ]
        }
    }
    df = normalize_market_data(sample_global_raw, "US")
    assert len(df) == 2
    assert df.iloc[0]["ticker"] == "AAPL"
    assert df.iloc[0]["current_price"] == 220.5
    assert df.iloc[0]["market"] == "US"

def test_calculate_top3_quant():
    df = pd.DataFrame([
        {"ticker": "A", "name": "Item A", "current_price": 100, "change_rate": 5.0, "trading_value": 1000, "market": "KRX"},
        {"ticker": "B", "name": "Item B", "current_price": 200, "change_rate": -1.0, "trading_value": 5000, "market": "KRX"},
        {"ticker": "C", "name": "Item C", "current_price": 300, "change_rate": 2.0, "trading_value": 3000, "market": "KRX"},
        {"ticker": "D", "name": "Item D", "current_price": 400, "change_rate": 0.5, "trading_value": 500, "market": "KRX"}
    ])
    top3 = calculate_top3_quant(df)
    assert len(top3) == 3
    assert "total_score" in top3.columns
    assert "value_score" in top3.columns
    assert "supply_score" in top3.columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_npay_service.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'services.npay_service'`

- [ ] **Step 3: Implement `services/npay_service.py`**

- User-Agent 헤더 상수를 정의하고, `normalize_market_data` 어댑터 구현
- `@st.cache_data(ttl=1800)` 데코레이터를 적용한 `fetch_npay_items` 구현 (네트워크 실패 시 fallback mock 데이터 반환)
- 가치 점수(50%)와 수급 점수(50%) 정규화 합산 퀀트 랭킹 알고리즘 구현

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_npay_service.py -v`  
Expected: PASS

---

### Task 4: 시장 주요 지수 및 3줄 브리핑 & 뉴스 서비스

**Files:**
- Create: `services/market_service.py`
- Create: `services/news_service.py`
- Test: `tests/test_market_news_service.py`

**Interfaces:**
- Produces:
  - `fetch_market_indices() -> dict[str, dict]` (KOSPI, KOSDAQ, S&P 500, NASDAQ, US10Y, USD/KRW)
  - `generate_3line_briefing(indices: dict) -> list[dict]`
  - `fetch_stock_news(tickers: list[str]) -> list[dict]`

- [ ] **Step 1: Write the failing test for market & news service**

```python
# tests/test_market_news_service.py
from services.market_service import generate_3line_briefing, get_mock_indices
from services.news_service import fetch_stock_news

def test_generate_3line_briefing():
    indices = get_mock_indices()
    briefing = generate_3line_briefing(indices)
    assert len(briefing) == 3
    for item in briefing:
        assert "category" in item
        assert "title" in item
        assert "summary" in item

def test_fetch_stock_news():
    news = fetch_stock_news(["005930", "AAPL"])
    assert isinstance(news, list)
    assert len(news) > 0
    assert "title" in news[0]
    assert "ticker" in news[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_market_news_service.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'services.market_service'`

- [ ] **Step 3: Implement `services/market_service.py` and `services/news_service.py`**

- `services/market_service.py`: yfinance 기반 코스피/나스닥/환율/금리 수집 (`@st.cache_data(ttl=900)`), 실패 시 모의 데이터 폴백, 거시/지수/전략 3줄 룰 기반 브리핑 생성
- `services/news_service.py`: 보유 종목 티커에 연계된 최신 뉴스/공시 헤드라인 생성 및 반환 (`@st.cache_data(ttl=600)`)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_market_news_service.py -v`  
Expected: PASS

---

### Task 5: 포트폴리오 수익률 계산 및 손절가 경고 비즈니스 로직

**Files:**
- Create: `services/portfolio_service.py`
- Test: `tests/test_portfolio_service.py`

**Interfaces:**
- Produces:
  - `calculate_portfolio_performance(items: list[dict], price_map: dict[str, float]) -> tuple[pd.DataFrame, dict]`

- [ ] **Step 1: Write the failing test for portfolio calculation and stop-loss alert**

```python
# tests/test_portfolio_service.py
import pytest
from services.portfolio_service import calculate_portfolio_performance

def test_calculate_portfolio_performance_with_stop_loss():
    items = [
        {
            "id": "1",
            "market": "KRX",
            "ticker": "005930",
            "name": "삼성전자",
            "buy_price": 70000.0,
            "quantity": 10.0,
            "target_price": 80000.0,
            "stop_loss_price": 65000.0,
            "memo": "장기투자"
        },
        {
            "id": "2",
            "market": "US",
            "ticker": "AAPL",
            "name": "Apple",
            "buy_price": 200.0,
            "quantity": 5.0,
            "target_price": 250.0,
            "stop_loss_price": 180.0,
            "memo": None
        }
    ]
    # 삼성전자는 현재가 64000 (손절가 65000 이하 -> 🚨 손절 경고 발생)
    # 애플은 현재가 220 (수익 발생)
    price_map = {"005930": 64000.0, "AAPL": 220.0}
    
    df, summary = calculate_portfolio_performance(items, price_map)
    
    assert len(df) == 2
    # 삼성전자 손절 경고 검증
    samsung_row = df[df["ticker"] == "005930"].iloc[0]
    assert samsung_row["is_stop_loss"] is True
    assert samsung_row["eval_profit"] == -60000.0  # (64000 - 70000) * 10
    
    # 애플 정상 수익 검증
    apple_row = df[df["ticker"] == "AAPL"].iloc[0]
    assert apple_row["is_stop_loss"] is False
    assert apple_row["profit_rate"] == 10.0  # (220 - 200) / 200 * 100
    
    # 포트폴리오 요약 검증
    assert "total_invested" in summary
    assert "total_eval" in summary
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_portfolio_service.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'services.portfolio_service'`

- [ ] **Step 3: Implement `services/portfolio_service.py`**

- 평가금액, 평가손익, 수익률(%), 목표가 달성률(%) 연산
- `current_price <= stop_loss_price` 시 `is_stop_loss = True` 플래그 및 배지 문자열 생성
- 총 원금, 총 평가액, 총 손익 요약 딕셔너리 생성

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_portfolio_service.py -v`  
Expected: PASS

---

### Task 6: Streamlit 메인 엔트리포인트 및 세션 방어 가드

**Files:**
- Create: `app.py`
- Test: `tests/test_session_guard.py`

**Interfaces:**
- Produces:
  - `ensure_session_state()`
  - 메인 라우팅 및 테마/CSS 주입 인터페이스

- [ ] **Step 1: Write the failing test for session guard function**

```python
# tests/test_session_guard.py
import pytest
from app import ensure_session_state

class MockSessionState(dict):
    pass

def test_ensure_session_state_initializes_defaults(monkeypatch):
    mock_state = MockSessionState()
    import streamlit as st
    monkeypatch.setattr(st, "session_state", mock_state)
    
    ensure_session_state()
    assert "user" in mock_state
    assert mock_state["user"] is None
    assert mock_state["authenticated"] is False
    assert mock_state["portfolio_items"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_session_guard.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: Implement `app.py`**

- `ensure_session_state()` 함수 구현
- `st.set_page_config(page_title="FinScope", page_icon="📈", layout="wide")`
- `assets/style.css` 로드 및 주입
- 메인 대시보드 랜딩 안내 및 사이드바 내비게이션 구성

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_session_guard.py -v`  
Expected: PASS

---

### Task 7: 1페이지 - [시장 브리핑 및 발굴] UI 구현

**Files:**
- Create: `pages/1_시장_브리핑.py`
- Test: `tests/test_page1_smoke.py`

**Interfaces:**
- Consumes: `services.market_service`, `services.npay_service`, `app.ensure_session_state`
- Produces: 6대 지수 카드, 3줄 브리핑 카드, 국내/미국 탭 Top 3 퀀트 발굴 뷰

- [ ] **Step 1: Write smoke test for Page 1 imports and execution functions**

```python
# tests/test_page1_smoke.py
import pytest
from services.market_service import fetch_market_indices
from services.npay_service import fetch_npay_items, calculate_top3_quant

def test_page1_data_pipeline_smoke():
    # 1페이지에서 소비하는 데이터 파이프라인 무결성 확인
    indices = fetch_market_indices()
    assert "KOSPI" in indices
    
    krx_df = fetch_npay_items("KRX")
    assert len(krx_df) > 0
    top3 = calculate_top3_quant(krx_df)
    assert len(top3) == 3
```

- [ ] **Step 2: Run test to verify it passes or fails**

Run: `uv run pytest tests/test_page1_smoke.py -v`  
Expected: PASS (services already validated)

- [ ] **Step 3: Implement `pages/1_시장_브리핑.py`**

- 상단: `ensure_session_state()` 세션 방어 가드 호출
- 6대 지수 요약 메트릭 카드 (`st.columns(6)` 및 반응형 CSS 클래스 적용)
- 중단: 오늘의 시장 3줄 핵심 브리핑 (거시, 지수, 전략)
- 하단: `st.tabs(["🇰🇷 국내 시장 Top 3", "🇺🇸 미국 시장 Top 3"])` 발굴 카드 및 게이지 바 시각화

- [ ] **Step 4: Verify Page 1 with Python syntax check**

Run: `python -m py_compile pages/1_시장_브리핑.py`  
Expected: Exit code 0 (문법 오류 없음)

---

### Task 8: 2페이지 - [개인 포트폴리오 관리] UI 구현

**Files:**
- Create: `pages/2_포트폴리오.py`
- Test: `tests/test_page2_smoke.py`

**Interfaces:**
- Consumes: `db.portfolio_repo`, `services.portfolio_service`, `services.news_service`, `app.ensure_session_state`
- Produces: ID/PIN 로그인 & 데모 체험, 종목 등록/수정/삭제 폼, 평가손익 테이블 & 🚨 손절 경고 배지, 뉴스 헤드라인 타임라인

- [ ] **Step 1: Write smoke test for Page 2 repository & service integration**

```python
# tests/test_page2_smoke.py
import pytest
from db.portfolio_repo import PortfolioRepository
from services.portfolio_service import calculate_portfolio_performance

def test_page2_integration_flow():
    repo = PortfolioRepository(client=None)
    success, user, _ = repo.authenticate_user("investor1", "9999")
    assert success is True
    
    repo.add_item(user["id"], {
        "market": "KRX", "ticker": "005930", "name": "삼성전자",
        "buy_price": 75000, "quantity": 10, "target_price": 85000, "stop_loss_price": 70000
    })
    items = repo.get_items(user["id"])
    df, summary = calculate_portfolio_performance(items, {"005930": 68000})
    assert len(df) == 1
    assert df.iloc[0]["is_stop_loss"] is True
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run pytest tests/test_page2_smoke.py -v`  
Expected: PASS

- [ ] **Step 3: Implement `pages/2_포트폴리오.py`**

- 최상단 `ensure_session_state()` 세션 기본값 방어 코드 적용
- 로그인 상태 헤더 (ID/PIN 입력, 데모 1클릭 로그인, 로그아웃)
- 포트폴리오 요약 메트릭 (총 원금, 총 평가금, 총 손익, 총 수익률)
- 보유 종목 등록/수정/삭제 폼 (유효성 검사: 수량 > 0, 매수가 > 0)
- 실시간 평가손익 테이블 뷰 및 🚨 손절 경고 하이라이트 배지
- 보유 종목 맞춤 최신 뉴스/공시 헤드라인 타임라인

- [ ] **Step 4: Verify Page 2 with Python syntax check**

Run: `python -m py_compile pages/2_포트폴리오.py`  
Expected: Exit code 0 (문법 오류 없음)

---

### Task 9: 엔드투엔드 통합 테스트 및 배포 가이드 문서화

**Files:**
- Create: `tests/test_e2e_integration.py`
- Create/Update: `README.md`

- [ ] **Step 1: Write comprehensive end-to-end integration test**

```python
# tests/test_e2e_integration.py
import pytest
from db.portfolio_repo import PortfolioRepository
from services.market_service import fetch_market_indices
from services.npay_service import fetch_npay_items, calculate_top3_quant
from services.portfolio_service import calculate_portfolio_performance

def test_full_application_flow():
    # 1. 시장 지수 및 퀀트 발굴 파이프라인 검증
    indices = fetch_market_indices()
    assert len(indices) >= 4
    
    krx_df = fetch_npay_items("KRX")
    assert not krx_df.empty
    top3 = calculate_top3_quant(krx_df)
    assert len(top3) == 3
    
    # 2. 포트폴리오 CRUD 및 손익 연산 검증
    repo = PortfolioRepository(client=None)
    ok, user, _ = repo.authenticate_user("e2e_user", "1234")
    assert ok is True
    
    repo.add_item(user["id"], {
        "market": "KRX", "ticker": top3.iloc[0]["ticker"], "name": top3.iloc[0]["name"],
        "buy_price": top3.iloc[0]["current_price"], "quantity": 10
    })
    items = repo.get_items(user["id"])
    assert len(items) == 1
    
    price_map = {items[0]["ticker"]: items[0]["buy_price"] * 1.05}
    perf_df, summary = calculate_portfolio_performance(items, price_map)
    assert perf_df.iloc[0]["profit_rate"] == 5.0
```

- [ ] **Step 2: Run all tests in the project**

Run: `uv run pytest -v`  
Expected: All tests PASS

- [ ] **Step 3: Update `README.md` with complete local run & Streamlit Community Cloud deployment guide**

- `uv venv` 가상환경 설정 및 실행 가이드
- Supabase 무료 티어 프로젝트 생성 및 `schema.sql` 실행 방법
- Streamlit Community Cloud 배포 시 `Advanced settings` > `Secrets`에 `SUPABASE_URL` / `SUPABASE_KEY` 등록하는 방법 명시

---
