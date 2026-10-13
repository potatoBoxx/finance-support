# FinScope: 개인 투자 분석 및 포트폴리오 대시보드 설계 문서 (Design Specification)

- **작성일자**: 2026-10-04
- **작성자**: Antigravity Assistant & Human Partner
- **배포 타깃**: GitHub + Streamlit Community Cloud (무료 티어)
- **핵심 기술 스택**: Python, Streamlit, Supabase (PostgreSQL), Pandas, yfinance, requests

---

## 1. 프로젝트 개요 및 목표

본 프로젝트는 주식 및 ETF 투자자를 위한 모바일/PC 반응형 개인 투자 분석 대시보드 웹 애플리케이션이다.  
별도의 무거운 서버나 상용 유료 DB 없이, **Streamlit 인메모리 캐시(`@st.cache_data`)**와 **Supabase(PostgreSQL) 무료 티어**를 결합하여 초고속 시세 조회와 안전한 영구 포트폴리오 관리를 제공한다.

### 핵심 목표
1. **무료 클라우드 배포 최적화**: Streamlit Community Cloud 환경에서 컨테이너가 재부팅되어도 Supabase를 통해 사용자 포트폴리오 데이터가 영구 보존됨.
2. **초고속 시세/발굴 인메모리 파이프라인**: Npay 증권 API(국내/미국 ETF 및 주식 각 Top 100)를 30분 TTL 캐시로 고속 조회하고, 퀀트 알고리즘(가치 50% + 수급 50%)을 통해 실시간 Top 3 유망 종목을 발굴.
3. **간편하고 안전한 인증**: 복잡한 회원가입 없이 사용자 식별값(ID)과 4자리 PIN(SHA-256 해시 암호화) 기반으로 안전하게 개인 포트폴리오를 분리 격리.
4. **반응형 멀티페이지 UI**: PC 대형 화면과 모바일 화면 모두에서 가독성을 보장하는 다크 테마 기반 2페이지 인터페이스.

---

## 2. 전체 디렉터리 구조 및 모듈 역할

워크스페이스 루트를 기준으로 Streamlit 배포 표준 구조를 구성한다.

```text
finance-support/
├── .agents/                        # 워크스페이스 에이전트 스킬 및 규칙 (superpowers 등)
├── .streamlit/
│   ├── config.toml                 # Streamlit 테마(다크 모드) 및 서버 옵션
│   └── secrets.toml.example        # Supabase 접속 정보 환경변수 템플릿
├── assets/
│   └── style.css                   # 반응형 메트릭 카드, 테이블, 모바일 최적화 CSS
├── db/                             # Supabase PostgreSQL 영속성 계층
│   ├── __init__.py
│   ├── supabase_client.py          # Supabase 클라이언트 싱글톤 생성 및 연결 관리
│   └── portfolio_repo.py           # 사용자 인증(PIN 검증) 및 포트폴리오 CRUD 전담
├── services/                       # 금융 데이터 수집, 퀀트 스코어링 및 비즈니스 로직
│   ├── __init__.py
│   ├── market_service.py           # 주요 시장 지수(KOSPI, S&P 500 등) 수집 및 3줄 브리핑 룰 엔진
│   ├── npay_service.py             # Npay 증권 API 수집(국내/미국 Top 100) 및 Top 3 가치/수급 퀀트 스코어링
│   ├── portfolio_service.py        # 평가손익, 수익률, 목표가 달성률 및 손절 경고(🚨) 비즈니스 로직
│   └── news_service.py             # 보유 종목 관련 최신 뉴스/공시 헤드라인 수집
├── pages/                          # Streamlit 멀티페이지 프레젠테이션 계층
│   ├── 1_시장_브리핑.py             # 1페이지: 지수 카드, 오늘의 3줄 브리핑, 발굴 Top 3
│   └── 2_포트폴리오.py             # 2페이지: ID/PIN 로그인, 보유 종목 CRUD, 실시간 손익 계산, 뉴스
├── app.py                          # 메인 엔트리포인트 (페이지 라우터, 글로벌 테마/CSS 주입, 세션 초기화)
├── schema.sql                      # Supabase 데이터베이스 테이블 및 인덱스 생성 DDL
├── requirements.txt                # 배포용 필수 파이썬 패키지 의존성 목록
├── .gitignore                      # .venv, secrets.toml, 캐시 파일 제외
└── README.md                       # 프로젝트 소개, 로컬 실행법 및 Streamlit Cloud 배포 가이드
```

### 계층별 책임 정의
- **DB Layer (`db/`)**: UI나 외부 API에 의존하지 않으며, 오직 Supabase와의 통신 및 SQL 질의만을 전담한다. Supabase 미설정 시 안전하게 데모(Mock) 저장소로 폴백한다.
- **Service Layer (`services/`)**: 외부 시세(Npay, yfinance) 및 뉴스 API와 통신하며 데이터를 정제하고 퀀트 점수 산출 및 손익 계산 로직을 순수 함수 형태로 실행한다.
- **Presentation Layer (`pages/`, `app.py`)**: `st.session_state`를 기반으로 상태를 관리하고 사용자 인터랙션을 처리하며, 비즈니스 계산이나 DB 쿼리를 직접 수행하지 않고 서비스를 호출한다.

---

## 3. Supabase 데이터베이스 설계 및 DDL

### 3.1 DDL 스크립트 (`schema.sql`)

```sql
-- 1. 확장 기능 활성화 (UUID 생성용)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. 사용자 테이블 (users)
-- ID와 PIN 기반의 경량 인증 지원 (PIN은 SHA-256 해시값으로만 저장)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    pin_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. 포트폴리오 보유 종목 테이블 (portfolio_items)
CREATE TABLE IF NOT EXISTS portfolio_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    market VARCHAR(10) NOT NULL CHECK (market IN ('KRX', 'US')),
    ticker VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    buy_price NUMERIC(14, 2) NOT NULL CHECK (buy_price > 0),
    quantity NUMERIC(14, 4) NOT NULL CHECK (quantity > 0),
    target_price NUMERIC(14, 2),
    stop_loss_price NUMERIC(14, 2),
    memo TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. 인덱스 생성 (조회 성능 최적화)
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_portfolio_user_id ON portfolio_items(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_ticker ON portfolio_items(user_id, ticker);

-- 5. Row Level Security (RLS) 활성화
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_items ENABLE ROW LEVEL SECURITY;

-- Streamlit 서버가 service_role 키를 사용하는 경우 모든 작업 허용 정책
CREATE POLICY "Allow all operations for service role" ON users
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Allow all operations for service role" ON portfolio_items
    FOR ALL USING (true) WITH CHECK (true);
```

### 3.2 보안 및 인증 메커니즘
- 사용자가 입력한 4자리 숫자 PIN은 `hashlib.sha256(pin.encode()).hexdigest()`로 암호화된 후 DB에 저장 및 검증된다.
- Streamlit Cloud의 `Secrets`를 통해 `SUPABASE_URL`과 `SUPABASE_KEY`가 주입되므로 코드나 깃허브에 인증 정보가 절대 노출되지 않는다.

---

## 4. 데이터 파이프라인 및 비즈니스 로직

### 4.1 Npay 증권 API 연동 및 인메모리 캐싱 (`services/npay_service.py`)
- **엔드포인트**:
  - 국내 주식/ETF (거래대금 순 상위 100):  
    `https://stock.naver.com/api/stockSecurity/etfs/v2/domestic?listingType=tradingValueDesc&size=100&index=0`
  - 미국 주식/ETF (주가/거래 순 상위 100):  
    `https://stock.naver.com/api/foreign/market/stock/global?nation=USA&tradeType=ALL&orderType=priceTop&startIdx=0&pageSize=100`
- **헤더 설정 (User-Agent 필수)**:
  ```python
  HEADERS = {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
      "Referer": "https://stock.naver.com/"
  }
  ```
- **응답 스키마 정규화 어댑터 (`normalize_market_data(raw_json, market_type) -> pd.DataFrame`)**:
  - 국내 API(`result.etfItemList` 계열)와 해외 API(`result.stockList` 계열)의 서로 다른 필드명(예: `itemcode` vs `reutersCode`, `nowVal` vs `closePrice`)을 파싱하여 다음의 **동일 규격 pandas DataFrame**으로 변환하는 전처리 어댑터를 거치도록 구현:
    * `ticker` (str): 종목/ETF 티커 (예: `069500`, `AAPL`)
    * `name` (str): 종목/ETF 명칭
    * `current_price` (float): 현재가
    * `change_rate` (float): 등락률 (%)
    * `trading_value` (float): 거래대금
    * `market` (str): `'KRX'` 또는 `'US'`
  - 모든 하위 분석(퀀트 스코어링, 실시간 현재가 매핑, 테이블 시각화)은 이 정규화된 DataFrame만을 소비하여 데이터 호환성 보장.
- **캐싱 정책**:
  - `@st.cache_data(ttl=1800)`: 30분 단위 자동 갱신. 불필요한 반복 네트워크 요청 차단 및 초고속 화면 렌더링.

### 4.2 가치(50%) + 수급(50%) 퀀트 Top 3 산출 알고리즘
1. **데이터 정규화 (Min-Max Scaling)**:
   - **가치 점수 (50%)**:
     - ETF/주식의 저평가 정도(낮은 괴리율/PER 또는 가격 변동성 대비 안정성 지표)를 0~100점으로 정규화.
   - **수급 점수 (50%)**:
     - 당일 거래대금 및 거래량 회전율을 0~100점으로 정규화.
2. **종합 점수 계산**:
   $$\text{Total Score} = (\text{Value Score} \times 0.5) + (\text{Supply Score} \times 0.5)$$
3. **Top 3 랭킹 필터링**:
   - 국내 시장 Top 3 및 미국 시장 Top 3를 각각 산출하여 카드 및 게이지 바 형태로 시각화.

### 4.3 주요 지수 요약 및 3줄 브리핑 (`services/market_service.py`)
- **지표 목록**:
  - 코스피(`^KS11`), 코스닥(`^KQ11`), S&P 500(`^GSPC`), 나스닥(`^IXIC`), 원/달러 환율(`KRW=X`), 미국 10년물 국채 금리(`^TNX`)
- **캐싱 정책**: `@st.cache_data(ttl=900)` (15분 캐시)
- **오늘의 시장 3줄 브리핑 룰 엔진**:
  - 거시(Macro): 환율 및 미국 국채 금리 변동성에 따른 달러 강세/약세 평가
  - 지수(Index): 코스피/나스닥 주요 지표 상승/하락 폭에 따른 시장 심리(공포/중립/탐욕) 요약
  - 전략(Action): 당일 수급 집중 테마 및 변동성 대응 권고사항 1줄 제시

### 4.4 개인 포트폴리오 손익 및 손절 경고 (`services/portfolio_service.py`)
- 등록된 각 종목에 대해 실시간 현재가를 매핑:
  - 평가금액 = $\text{현재가} \times \text{보유수량}$
  - 평가손익 = $(\text{현재가} - \text{매수가}) \times \text{보유수량}$
  - 수익률(%) = $\frac{\text{현재가} - \text{매수가}}{\text{매수가}} \times 100$
  - 목표가 달성률(%) = $\frac{\text{현재가}}{\text{목표가}} \times 100$
- **손절가 경고 알림 (🚨)**:
  - $\text{현재가} \le \text{손절가}$ 인 경우, 즉시 상태를 `🚨 손절 경고`로 지정하고 붉은색 강조 배지 노출.

---

## 5. UI/UX 화면 구성 및 반응형 인터랙션

### 5.1 공통 레이아웃 및 테마 (`app.py`, `assets/style.css`)
- `st.set_page_config(layout="wide", initial_sidebar_state="expanded")`
- 다크/블루 톤의 현대적인 카드 디자인 (`glassmorphism` 및 부드러운 호버 애니메이션)
- 모바일 화면 가로 스크롤 방지 및 유동적 그리드 (`flex-wrap`, 반응형 미디어 쿼리)

### 5.2 1페이지: [시장 브리핑 및 발굴] (`pages/1_시장_브리핑.py`)
1. **상단**: 국장 3대 지표 + 미장 3대 지표 2열 메트릭 카드 (현재값, 등락률)
2. **중단**: 오늘의 시장 3줄 요약 카드 (배경 강조 박스 및 태그)
3. **하단**: 국내 / 미국 탭 기반 Top 3 유망 종목 카드
   - 종목명, 티커, 현재가, 등락률
   - 종합 점수, 가치 점수(50%), 수급 점수(50%) 프로그레스 바
   - 핵심 선정 사유 칩(Chip)

### 5.3 2페이지: [개인 포트폴리오 관리] (`pages/2_포트폴리오.py`)
0. **멀티페이지 세션 상태 방어 초기화 (Session Guard)**:
   - 사용자가 `pages/2_포트폴리오.py`로 직접 진입하거나 브라우저 새로고침을 할 때 `app.py`를 거치지 않더라도 세션이 손상되지 않도록 최상단에 방어 초기화 코드를 배치:
   ```python
   # 세션 상태 기본값 보장 방어 코드
   if "user" not in st.session_state:
       st.session_state.user = None
   if "authenticated" not in st.session_state:
       st.session_state.authenticated = False
   if "portfolio_items" not in st.session_state:
       st.session_state.portfolio_items = []
   if "is_demo_mode" not in st.session_state:
       st.session_state.is_demo_mode = False
   ```
1. **사용자 식별 헤더**:
   - 미로그인 시: ID 입력 및 PIN 4자리 입력창, "데모 계정 체험" 빠른 로그인 버튼
   - 로그인 완료 시: "👤 [사용자ID]님 포트폴리오" 상태 배너 및 로그아웃 버튼
2. **포트폴리오 요약 대시보드**:
   - 총 투자원금, 총 평가금액, 총 평가손익, 총 수익률(%) 4개 요약 카드
3. **보유 종목 관리 폼 (등록/수정/삭제)**:
   - 시장 선택(국내 KRX / 미국 US), 티커, 종목명, 매수가, 수량, 목표가, 손절가, 투자 메모
4. **실시간 평가손익 테이블 & 카드뷰**:
   - PC: 고밀도 데이터프레임 (수익률 컬러링, 손절 경고 배지)
   - 모바일: 카드형 스택 뷰
5. **보유 종목 관련 최신 뉴스/공시 헤드라인**:
   - 포트폴리오 보유 종목별 최신 뉴스 헤드라인 타임라인 목록

---

## 6. 예외 처리 및 장애 격리 전략

1. **Supabase 미연동 / 접속 불가 시 (Graceful Fallback)**:
   - `.streamlit/secrets.toml`에 키가 없거나 네트워크 연결 실패 시, 에러로 크래시되지 않고 상단에 "⚠️ 로컬 데모 모드로 동작 중입니다 (세션 종료 시 데이터 초기화)" 경고를 띄우며 인메모리 `st.session_state`로 안전하게 폴백 동작.
2. **Npay 증권 API 차단 / 요청 실패 시**:
   - HTTP Status 429/403 또는 네트워크 타임아웃 발생 시, 캐시된 이전 데이터 또는 내장된 Mock 데이터를 즉시 반환하여 대시보드 렌더링 유지.
3. **yfinance 지수 수집 지연 시**:
   - 타임아웃 5초 제한 및 실패 시 최근 종가 기준 대체 값 표시.

---

## 7. 의존성 패키지 및 환경 설정

### 7.1 `requirements.txt`
```text
streamlit>=1.36.0
pandas>=2.0.0
numpy>=1.24.0
requests>=2.31.0
supabase>=2.5.0
yfinance>=0.2.40
plotly>=5.18.0
```

### 7.2 `.streamlit/secrets.toml.example`
```toml
# Supabase 연결 설정 (Supabase 대시보드 > Project Settings > API)
SUPABASE_URL = "https://your-project-id.supabase.co"
SUPABASE_KEY = "your-anon-or-service-role-key"
```

---

## 8. 단계별 구축 로드맵

- **Phase 1: 기반 설정 및 의존성 구성 (Infrastructure)**
  - `requirements.txt` 작성 및 `uv venv .venv` 가상환경 설치
  - `.streamlit/config.toml` 및 `secrets.toml.example` 생성
  - 반응형 `assets/style.css` 작성
- **Phase 2: Supabase 데이터베이스 및 레포지토리 구축 (Database)**
  - `schema.sql` 정의
  - `db/supabase_client.py` 및 `db/portfolio_repo.py` 구현 (ID/PIN 해시 인증 + CRUD + 로컬 데모 폴백)
- **Phase 3: 시세 수집 및 퀀트 비즈니스 로직 구현 (Services)**
  - `services/market_service.py` (yfinance 지수 수집 & 15분 캐싱)
  - `services/npay_service.py` (Npay 국내/해외 API + 30분 캐싱 + 가치/수급 Top 3 랭킹)
  - `services/portfolio_service.py` (실시간 현재가 매핑, 손익 계산, 손절 경고 판정)
  - `services/news_service.py` (종목 뉴스 헤드라인 수집)
- **Phase 4: Streamlit UI 프레젠테이션 및 반응형 뷰 구현 (Presentation)**
  - `app.py` 메인 엔트리포인트 구성
  - `pages/1_시장_브리핑.py` 구현
  - `pages/2_포트폴리오.py` 구현
- **Phase 5: 통합 기능 검증 및 배포 준비 (Verification & Deployment)**
  - `uv run streamlit run app.py`를 통한 엔드투엔드 기능 및 모바일 반응형 뷰 테스트
  - GitHub 저장소 초기화 및 Streamlit Community Cloud 배포 가이드 문서화
