# 📈 FinScope - 금융 데이터 반응형 Streamlit 대시보드

Python **Streamlit** 기반의 금융 데이터 웹 대시보드 기본 골격 프로젝트입니다.  
PC 및 모바일 브라우저 환경에 완벽 대응하는 반응형 레이아웃과 2페이지 멀티페이지 구조로 설계되었습니다.

---

## 🗂️ 프로젝트 폴더 구조

```text
finance-support-plan/
├── app.py                      # 메인 엔트리포인트 (페이지 라우팅, 반응형 CSS 주입, 세션 상태 관리)
├── pages/
│   ├── market_briefing.py      # 1페이지: 시장 브리핑 및 AI 유망 종목 발굴
│   └── portfolio.py            # 2페이지: 개인 포트폴리오 관리 (CRUD, 손익 계산, DART/뉴스)
├── services/
│   ├── market_service.py       # 시장 지수, 3줄 브리핑, Top 3 발굴 종목 모의 데이터 및 API 인터페이스
│   └── portfolio_service.py    # 포트폴리오 수익률/손익 계산 및 최신 공시/뉴스 연동 로직
├── data/
│   ├── portfolio_store.py      # 사용자 인증 및 포트폴리오 로컬 JSON 저장소 관리자
│   └── portfolios.json         # 사용자 계정 및 포트폴리오 영구 저장 JSON 파일
├── assets/
│   └── style.css               # PC/모바일 반응형 최적화 커스텀 스타일시트
├── requirements.txt            # 필요 패키지 의존성 목록
└── README.md                   # 프로젝트 문서
```

---

## 🌟 주요 기능 및 페이지 구성

### 1. 1페이지: [시장 브리핑 및 발굴] (`pages/market_briefing.py`)
- **국장/미장 주요 지수 및 지표 요약 카드**:
  - 코스피(KOSPI), 코스닥(KOSDAQ), S&P 500, 나스닥(NASDAQ), 원/달러 환율, 미국 10년물 국채 금리
  - 반응형 그리드 카드, 등락률/등락폭 시각화, 미니 추세 스파크라인
- **오늘의 시장 3줄 핵심 브리핑**:
  - 거시경제, 수급동향, 외환/환율 카테고리별 당일 시장 핵심 요약
  - 시장 심리 지표(공포/탐욕) 및 테마 키워드 태그 제공
- **오늘 눈여겨볼 Top 3 종목 (가치 50% + 수급 50% 혼합 기준)**:
  - 밸류에이션(PER/PBR/ROE 등) 50% + 외인/기관 수급 강도 50% 혼합 퀀트 스코어링
  - 순위별 종합 점수, 프로그레스 게이지, 핵심 퀀트 지표 및 선정 근거 브리핑

### 2. 2페이지: [개인 포트폴리오 관리] (`pages/portfolio.py`)
- **사용자 로그인/식별 (`st.session_state`) 구조**:
  - 사용자 ID와 보안 PIN 기반 계정 분리
  - 처음 입력하는 ID는 신규 프로필로 자동 생성
  - 빠른 확인을 위한 원클릭 **데모 계정 체험 (`demo` / PIN `1234`)** 버튼 제공
- **보유 종목 CRUD (등록 / 수정 / 삭제)**:
  - 티커, 종목명, 시장(KRX/US), 매수가, 수량, 목표가, 손절가, 투자 메모
- **종목별 수익률 및 평가손익 계산 테이블**:
  - 투자원금, 평가금액, 평가손익, 수익률(%), 목표가 달성률 자동 계산
  - **손절가 경고 알림 (🚨)**: 현재가가 설정한 손절가 이하로 하락 시 즉시 경고 배지 노출
  - PC 환경용 상세 데이터프레임 뷰 및 모바일 최적화 카드형 뷰 제공
- **보유 종목 관련 최신 뉴스/공시 헤드라인**:
  - 포트폴리오 등록 종목과 연계된 금융감독원 전자공시(DART) 및 최신 언론사 뉴스 헤드라인 타임라인

---

## 🚀 빠른 시작 가이드 (uv 가상환경 기반)

본 프로젝트는 고속 패키지 관리자 **`uv`**를 기준으로 작성되었습니다.

### 1. 가상환경 생성 및 활성화
```bash
# 가상환경 생성
uv venv .venv

# 가상환경 활성화 (Windows PowerShell)
.venv\Scripts\Activate.ps1

# (또는 Bash)
# source .venv/bin/activate
```

### 2. 필수 패키지 설치
```bash
uv pip install -r requirements.txt
```

### 3. Streamlit 대시보드 실행
```bash
uv run streamlit run app.py
```
실행 후 브라우저에서 `http://localhost:8501`로 접속합니다.

---

## 🔌 향후 실제 금융 데이터 API 연동 가이드

현재는 서비스 레이어(`services/`)에서 표준화된 모의 데이터(Mock Data)를 반환하도록 설계되어 있어, 기존 UI 코드 수정 없이 서비스 내부 함수만 실제 API로 교체하면 됩니다.

### 1. 한국거래소(KRX) 주가 및 밸류에이션 API (`pykrx`)
- 설치: `uv pip install pykrx`
- 연동 위치: `services/market_service.py`, `services/portfolio_service.py`
```python
from pykrx import stock

# 코스피/코스닥 지수 OHLCV 조회
df = stock.get_index_ohlcv_by_date("20261001", "20261004", "1001")

# 특정 종목 기본정보 및 펀더멘털(PER, PBR 등)
df_fund = stock.get_market_fundamental_by_ticker("20261004", market="ALL")
```

### 2. 미국 주식 및 환율 API (`yfinance`)
- 설치: `uv pip install yfinance`
- 연동 위치: `services/market_service.py`, `services/portfolio_service.py`
```python
import yfinance as yf

# 미장 지수 및 주가 조회
ticker = yf.Ticker("NVDA")
current_price = ticker.fast_info['lastPrice']
```

### 3. 전자공시시스템 API (`OpenDartReader`)
- 설치: `uv pip install opendartreader`
- 연동 위치: `services/portfolio_service.py`
```python
import OpenDartReader

dart = OpenDartReader("YOUR_DART_API_KEY")
# 보유 종목 공시 목록 조회
disclosures = dart.list("삼성전자", start="2026-10-01")
```
