# 📈 FinScope - 개인 투자 분석 & 포트폴리오 대시보드

**FinScope**는 Streamlit과 Supabase(PostgreSQL)를 기반으로 구축된 반응형 개인 투자 분석 대시보드 웹 애플리케이션입니다.  
Npay 증권 API의 초고속 인메모리 퀀트 발굴과 Supabase 클라우드 데이터베이스를 결합하여, Streamlit Community Cloud 무료 티어 환경에서도 컨테이너 재부팅에 구애받지 않는 안전한 영구 포트폴리오 관리를 제공합니다.

---

## 🗂️ 프로젝트 폴더 구조

```text
finance-support/
├── .streamlit/
│   ├── config.toml                 # Streamlit 테마(다크 모드) 및 서버 옵션
│   └── secrets.toml.example        # Supabase 접속 키 템플릿 (.gitignore 대상)
├── assets/
│   └── style.css                   # 반응형 메트릭 카드 및 모바일 가로스크롤 방지 CSS
├── db/                             # Supabase PostgreSQL 영속성 계층 (Repository 패턴)
│   ├── supabase_client.py          # Supabase 클라이언트 연결 관리자 (Graceful Fallback 지원)
│   └── portfolio_repo.py           # 사용자 인증(SHA-256 PIN 검증) 및 종목 CRUD 전담
├── services/                       # 데이터 수집, 퀀트 스코어링 및 비즈니스 로직
│   ├── npay_service.py             # Npay 증권 API(국내/미국 Top 100) 수집 (TTL 30분) & Top 3 퀀트 발굴
│   ├── market_service.py           # 주요 지수(코스피/S&P500 등) 수집 (yfinance, TTL 15분) & 3줄 브리핑
│   ├── portfolio_service.py        # 실시간 평가손익, 수익률 계산 및 🚨 손절 경고 판정
│   └── news_service.py             # 보유 종목 관련 최신 뉴스/공시 헤드라인 수집 (TTL 10분)
├── pages/                          # Streamlit 멀티페이지 프레젠테이션 계층
│   ├── 1_시장_브리핑.py             # 1페이지: 6대 지수 카드, 오늘의 3줄 브리핑, 발굴 Top 3
│   └── 2_포트폴리오.py             # 2페이지: ID/PIN 로그인, 종목 CRUD, 손익 테이블, 뉴스 타임라인
├── tests/                          # pytest 단위 및 스모크 테스트 (19개 테스트)
├── app.py                          # 메인 엔트리포인트 (페이지 라우터, 글로벌 테마/CSS, 세션 초기화)
├── schema.sql                      # Supabase DDL 스크립트
├── requirements.txt                # 클라우드 배포용 필수 패키지 목록
└── README.md                       # 실행 및 배포 가이드
```

---

## 🚀 빠른 시작 가이드 (uv 기반)

본 프로젝트는 고속 패키지 관리자 **`uv`**를 기반으로 개발되었습니다.

### 1. 가상환경 생성 및 패키지 설치
```bash
# 가상환경 생성
uv venv .venv

# 가상환경 활성화 (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# (또는 Bash)
# source .venv/bin/activate

# 필수 패키지 설치
uv pip install -r requirements.txt
```

### 2. Streamlit 대시보드 로컬 실행
```bash
uv run streamlit run app.py
```
실행 후 웹 브라우저에서 `http://localhost:8501`로 접속합니다.

---

## ☁️ Supabase 클라우드 데이터베이스 연동 가이드

> **참고**: Supabase 키를 설정하지 않아도 앱은 자동으로 **로컬 데모 모드 (인메모리)**로 동작하며, 사전 구성된 데모 계정(`demo` / PIN `1234`)과 CRUD 기능을 자유롭게 테스트하실 수 있습니다.

### 1. Supabase에서 테이블 생성
1. [Supabase](https://supabase.com)에 로그인하여 새 프로젝트를 생성합니다.
2. 좌측 메뉴 **SQL Editor**로 이동하여 `New query`를 클릭합니다.
3. 프로젝트 내 `schema.sql` 파일의 내용을 복사하여 붙여넣고 `Run`을 실행합니다.

### 2. 로컬 개발 환경 키 설정
`.streamlit/secrets.toml.example` 파일을 복사하여 `.streamlit/secrets.toml`을 생성하고 키를 입력합니다:
```toml
SUPABASE_URL = "https://your-project-id.supabase.co"
SUPABASE_KEY = "your-anon-or-service-role-key"
```

### 3. Streamlit Community Cloud 무료 배포 시 Secrets 설정
1. GitHub에 본 저장소를 푸시합니다.
2. [Streamlit Community Cloud](https://share.streamlit.io)에 로그인하여 저장소를 배포합니다.
   - **Main file path**: `app.py`
3. 앱 설정의 **Advanced settings > Secrets** 영역에 아래 내용을 입력하고 저장합니다:
   ```toml
   SUPABASE_URL = "https://your-project-id.supabase.co"
   SUPABASE_KEY = "your-anon-or-service-role-key"
   ```

---

## 🧪 테스트 실행
```bash
uv run pytest -v
```
현재 19개의 전체 단위 테스트 및 스모크 테스트가 100% 통과합니다.
