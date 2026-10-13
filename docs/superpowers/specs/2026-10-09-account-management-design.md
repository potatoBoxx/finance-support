# 계좌 관리 테이블 신설 및 포트폴리오 연동 아키텍처 설계서

## 1. 개요 및 배경 (Context & Purpose)
현재 FinScope의 포트폴리오 관리는 보유 종목 단위(`portfolio_items`)에서 단순 문자열 텍스트(`account`, 예: '토스증권', '키움증권')로 계좌를 구분하고 있습니다.
다중 사용자 확장 및 고도화된 자산 관리(일반 계좌, ISA 계좌, 연금저축, IRP 등)를 지원하기 위해 다음과 같은 한계를 개선합니다:
1. 계좌별 개설일, 만기일(예: ISA 3년 의무가입), 계좌 유형 정보의 부재
2. 증권사 및 계좌 별칭의 구조화된 관리 불가
3. ISA 만기 도래 시 연금계좌 전환 세액공제(최대 300만 원) 등 맞춤형 절세 가이드 제공 불가

본 설계서는 신규 `accounts` 관계형 테이블을 신설하고, 기존 `portfolio_items`와의 외래키 매핑, 하위 호환성 유지, Streamlit `@st.dialog` 모달 기반 계좌 관리 UI, 그리고 ISA 만기 D-Day 및 절세 AI 룰 엔진을 구축하는 아키텍처를 정의합니다.

---

## 2. 목표 및 비목표 (Goals & Non-Goals)

### 목표 (Goals)
1. **데이터 모델 연동**:
   - `accounts` 테이블 정의 (`id`, `user_id`, `broker_name`, `account_alias`, `account_type`, `opened_at`, `maturity_at`, `created_at`, `updated_at`).
   - `portfolio_items.account_id` (UUID, FK) 컬럼 추가 및 관계 매핑.
   - 기존 텍스트 `account` 필드를 유지하여 레거시 데이터 호환성 보장.
   - 기존 사용자의 기존 보유 종목에서 고유 계좌명을 추출해 기본 `accounts` 레코드를 자동 생성(Auto-seed)하는 마이그레이션 로직 구현.
2. **계좌 관리 UI (Streamlit `@st.dialog`)**:
   - 종목 등록 및 수정 폼의 [계좌/금융앱 구분] 셀렉트박스에 사용자 계좌 동적 로드 (`"{증권사} - {별칭 or 유형}"`).
   - [➕ 계좌 관리] 버튼 클릭 시 모달 다이얼로그(`@st.dialog`)를 통해 새 계좌 추가 및 기존 계좌 목록 확인/삭제 제공.
   - 계좌 추가 시 'ISA' 선택 시 `opened_at + 3년`을 만기일 기본값으로 자동 계산하는 편의 로직 제공.
3. **상단 계좌 필터 & ISA 절세 AI 어드바이스**:
   - 상단 계좌 필터에서 ISA 계좌 선택 시 만기 D-Day 배지(`⏳ 만기 D-180`) 렌더링.
   - ISA 만기 연금 전환 추가 세액공제(전환액의 10%, 최대 300만 원) 룰 엔진 연동.
4. **로컬 데모(Mock) 모드 100% 지원**:
   - Supabase 미연결 환경에서도 `_fallback_accounts`를 통해 동일한 기능 동작 보장.

### 비목표 (Non-Goals)
- 오픈뱅킹/마이데이터 실시간 계좌 잔고 스크래핑 (사용자가 직접 계좌 정보 및 종목을 관리하는 구조 유지)
- 계좌 간 종목 즉시 이체 기능 (기존 종목 수정 기능을 통해 계좌 변경 가능)

---

## 3. 데이터베이스 스키마 설계 (`schema.sql`)

### 3.1. `accounts` 테이블 DDL
```sql
CREATE TABLE IF NOT EXISTS accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    broker_name VARCHAR(50) NOT NULL,
    account_alias VARCHAR(50),
    account_type VARCHAR(20) NOT NULL CHECK (account_type IN ('일반', 'ISA', '연금저축', 'IRP')),
    opened_at DATE,
    maturity_at DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON accounts(user_id);

ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow all operations for authenticated or service role" ON accounts;
CREATE POLICY "Allow all operations for authenticated or service role" ON accounts
    FOR ALL USING (true) WITH CHECK (true);
```

### 3.2. `portfolio_items` 테이블 수정 (외래키 매핑)
```sql
ALTER TABLE portfolio_items ADD COLUMN IF NOT EXISTS account_id UUID REFERENCES accounts(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_portfolio_account_id ON portfolio_items(account_id);
```

---

## 4. 백엔드 및 레포지토리 계층 (`db/portfolio_repo.py`)

### 4.1. `PortfolioRepository` 확장 메서드
1. `get_accounts(user_id: str) -> list[dict]`:
   - 해당 사용자의 `accounts` 목록을 조회하여 반환 (정렬: `created_at` 오름차순).
   - 계좌가 하나도 없거나 기존 종목이 있는 경우 `auto_seed_accounts_from_items(user_id)`를 호출하여 자동 동기화.
2. `create_account(user_id: str, account_data: dict) -> tuple[bool, Optional[dict], str]`:
   - `broker_name`, `account_type` 필수 검증.
   - `account_alias`, `opened_at`, `maturity_at` 저장.
   - 성공 시 `(True, created_account, "성공 메시지")` 반환.
3. `delete_account(account_id: str) -> tuple[bool, str]`:
   - 계좌 삭제 시 연결된 `portfolio_items`의 `account_id`는 NULL로 안전 처리 (종목 데이터 보존).
4. `auto_seed_accounts_from_items(user_id: str) -> list[dict]`:
   - 해당 유저의 `portfolio_items` 목록에서 고유한 `account` 텍스트를 추출.
   - 예: `토스증권`, `키움증권`, `한국투자증권`, `기본`
   - 각 계좌명을 바탕으로 기본 `accounts` 레코드를 생성:
     - `broker_name`: 파싱된 증권사명 (기본값: '기본')
     - `account_type`: 이름에 'ISA'가 포함되면 'ISA', '연금'이면 '연금저축', 'IRP'면 'IRP', 그 외는 '일반'
     - `account_alias`: 파싱된 이름
   - 생성된 `accounts.id`를 기존 `portfolio_items.account_id`에 자동 업데이트 매핑.

### 4.2. 로컬 데모(Mock) 모드 폴백 지원
- `_fallback_accounts: dict[str, list[dict]]`를 구성하여 데모 유저(`demo_user_id`)에게 초기 기본 계좌 3종 자동 부여:
  1. `토스증권 - 일반`
  2. `키움증권 - 일반`
  3. `미래에셋 - 절세ISA` (개설일: 오늘 기준 -1년, 만기일: 오늘 기준 +2년)
  4. `한국투자증권 - 연금저축`
- Supabase 클라이언트 미연결 시 세션 상태(`st.session_state.mock_db_accounts`)와 완벽 동기화.

---

## 5. 비즈니스 로직 및 서비스 계층 (`services/portfolio_service.py`)

### 5.1. ISA 만기 D-Day 계산 (`calculate_isa_dday`)
```python
def calculate_isa_dday(maturity_at: str | datetime.date) -> dict[str, Any]:
    """
    만기일을 기준으로 잔여 D-Day 및 표시 뱃지 메타데이터 반환:
    - d_day > 0: 'D-180' (안전/진행중)
    - d_day == 0: 'D-Day' (오늘 만기)
    - d_day < 0: 'D+30' (만기 경과)
    """
```

### 5.2. ISA 만기 연금 전환 세액공제 AI 룰 엔진 (`evaluate_isa_tax_advice`)
```python
def evaluate_isa_tax_advice(account: dict, summary: dict) -> Optional[dict]:
    """
    선택된 계좌가 ISA인 경우, 평가금액 및 만기일정에 맞춰 절세 조언 카드 생성:
    - 조세특례제한법 제91조의18 및 소득세법 제59조의3 기반:
      ISA 만기 해지 자금을 60일 이내에 연금계좌(연금저축/IRP)로 전환 납입 시,
      전환 금액의 10%(최대 300만 원)를 추가 세액공제.
    - 예상 세액공제 효과 계산: min(total_eval * 0.1, 3_000_000) 원
    """
```

### 5.3. ISA 만기일 자동 계산 헬퍼 (`calculate_isa_default_maturity`)
- 개설일(`opened_at`)로부터 정확히 +3년(의무가입 기간 36개월)을 계산하여 반환 (`opened_at.replace(year=opened_at.year + 3)`).

---

## 6. 사용자 인터페이스 (UI) 설계 (`pages/2_포트폴리오.py`)

### 6.1. 상단 계좌 필터 & D-Day 뱃지 렌더링
- `📁 계좌 / 금융앱 선택` 드롭다운:
  - `전체 계좌 보기`
  - 등록된 계좌 목록: `"{broker_name} - {account_alias or account_type}"`
- 특정 ISA 계좌가 선택되었을 때:
  - 필터 우측에 만기 D-Day 배지 렌더링 (예: `⏳ 만기 D-180 (2027-10-15)`)
  - 필터 바로 아래에 **💡 ISA 만기 연금 전환 추가 세액공제 안내 카드** 표시.

### 6.2. 종목 등록 및 수정 폼 드롭다운 연동
- [계좌/금융앱 구분] 셀렉트박스:
  - 사용자 계좌 목록을 `{broker_name} - {alias}`로 노출
  - 드롭다운 바로 우측에 `[➕ 계좌 관리]` 버튼 배치

### 6.3. 계좌 관리 모달 다이얼로그 (`@st.dialog`)
- 함수명: `manage_accounts_dialog(user_id: str, repo: PortfolioRepository)`
- 구성:
  1. **새 계좌 등록 카드**:
     - 증권사 선택 (`selectbox`: 토스증권, 키움증권, 미래에셋, KB증권, 한국투자증권, NH투자증권, 삼성증권, 신한투자증권, 기타 직접 입력)
     - 계좌 유형 선택 (`selectbox`: 일반, ISA, 연금저축, IRP)
     - 계좌 별칭 입력 (`text_input`, 선택)
     - 개설일 입력 (`date_input`, 기본값 오늘)
     - 만기일 입력 (`date_input`): ISA 선택 시 `opened_at + 3년` 자동 기본값!
     - `[💾 새 계좌 등록]` 버튼
  2. **현재 등록된 계좌 목록**:
     - 계좌 유형 배지, 증권사명, 별칭, 개설/만기일
     - `[🗑️ 삭제]` 버튼 제공 (안전 삭제 처리)

---

## 7. 하위 호환성 및 마이그레이션 전략 (Compatibility)
1. **기존 데이터 100% 보존**:
   - `portfolio_items.account` (텍스트) 필드를 유지하므로 기존 쿼리나 화면이 깨지지 않음.
   - 첫 로드 시 `auto_seed_accounts_from_items`를 통해 기존 텍스트 계좌가 `accounts` 테이블에 자동 레코드화되고 외래키 `account_id`가 연결됨.
2. **점진적 전환**:
   - 신규 등록/수정되는 종목은 `account_id`와 `account` 텍스트가 동시에 저장됨.

---

## 8. 테스트 및 품질 보증 계획 (Testing Strategy)
1. `tests/test_portfolio_repo.py`:
   - `accounts` CRUD 기능 단위 테스트
   - `auto_seed_accounts_from_items` 기존 종목 연동 검증
   - `delete_account` 시 종목 보존 검증
2. `tests/test_portfolio_service.py`:
   - `calculate_isa_dday` D-Day 경과/잔여 계산 검증
   - `calculate_isa_default_maturity` +3년 계산 검증
   - `evaluate_isa_tax_advice` 세액공제 10% (최대 300만) 룰 엔진 검증
3. `tests/test_ui_smoke.py`:
   - UI 렌더링 스모크 테스트 (다이얼로그, 계좌 드롭다운, D-Day 배지 등)
4. 회귀 테스트:
   - 전체 37개 기존 테스트 포함 총 40개+ 테스트가 `uv run pytest`로 100% 통과하도록 검증.
