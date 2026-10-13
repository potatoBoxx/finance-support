"""
FinScope - 개인 투자 분석 대시보드 메인 엔트리포인트 (app.py)
"""
from pathlib import Path
import streamlit as st

# 1. 페이지 기본 설정 (와이드 레이아웃)
st.set_page_config(
    page_title="FinScope - 개인 투자 분석 대시보드",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# 2. 전역 커스텀 CSS 주입
def inject_custom_css():
    """assets/style.css 스타일시트를 로드하여 Streamlit 앱에 주입합니다."""
    css_path = Path(__file__).resolve().parent / "assets" / "style.css"
    if css_path.exists():
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


inject_custom_css()


# 3. 전역 세션 상태 (Session State) 초기화 가드
def ensure_session_state():
    """앱 전역에서 사용하는 세션 기본값을 안전하게 보장합니다."""
    if "user" not in st.session_state:
        st.session_state.user = None
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "portfolio_items" not in st.session_state:
        st.session_state.portfolio_items = []
    if "is_demo_mode" not in st.session_state:
        st.session_state.is_demo_mode = False


ensure_session_state()


# 4. 사이드바 상태 및 브랜딩 렌더링
def render_sidebar():
    """사이드바에 브랜딩 및 Supabase 동기화 상태, 로그인 정보 표시"""
    with st.sidebar:
        st.markdown("""
            <div style="padding: 0.5rem 0 1rem 0;">
                <h2 style="margin: 0; font-size: 1.45rem; color: #F8FAFC; display: flex; align-items: center; gap: 8px;">
                    📈 FinScope
                </h2>
                <span style="font-size: 0.8rem; color: #94A3B8;">Financial Intelligence Dashboard</span>
            </div>
        """, unsafe_allow_html=True)

        from db.supabase_client import is_supabase_configured
        if is_supabase_configured():
            st.success("🔒 **Supabase 클라우드 모드**\n\n(포트폴리오 영구 보존 및 동기화 활성)", icon="✅")
        else:
            st.warning("⚠️ **로컬 데모 모드 (인메모리)**\n\n(Supabase 키 미설정 상태, 세션 종료 시 초기화)", icon="ℹ️")

        st.markdown("---")

        if st.session_state.get("authenticated") and st.session_state.get("user"):
            username = st.session_state.user.get("username", "사용자")
            st.info(f"👤 접속자: **{username}**님", icon="✨")
            if st.button("로그아웃", use_container_width=True, key="app_logout_btn"):
                st.session_state.authenticated = False
                st.session_state.user = None
                st.rerun()
        else:
            st.caption("💡 [2_포트폴리오] 페이지에서 ID/PIN으로 로그인하거나 원클릭 데모 계정을 이용하실 수 있습니다.")

        st.markdown("---")
        st.caption("v1.0.0 | GitHub & Streamlit Cloud 배포 최적화")


render_sidebar()

# 5. 메인 홈 랜딩 뷰 렌더링
st.markdown("""
    <div style="margin-bottom: 1.5rem;">
        <h1 class="page-hero-title" style="color: #F8FAFC; margin-bottom: 0.5rem; word-break: keep-all; letter-spacing: -0.5px;">
            📈 FinScope 개인 투자 분석 대시보드
        </h1>
        <p style="font-size: 1.05rem; color: #94A3B8; margin: 0; line-height: 1.6; word-break: keep-all; letter-spacing: -0.3px;">
            실시간 글로벌 시장 지표와 퀀트 유망 종목 발굴, 다중 계좌 맞춤형 포트폴리오 분석을 원스톱으로 지원하는 프리미엄 투자 대시보드입니다.
        </p>
    </div>
""", unsafe_allow_html=True)

# 2열 반응형 카드 네비게이션
col1, col2 = st.columns(2, gap="large")

with col1:
    st.markdown("""
        <div class="fin-card">
            <h3 style="margin-top: 0; color: #60A5FA; display: flex; align-items: center; gap: 8px; word-break: keep-all;">
                🌐 1. 오늘의 시장 브리핑 & 추천 종목
            </h3>
            <p style="color: #CBD5E1; font-size: 0.95rem; line-height: 1.6; word-break: keep-all;">
                당일 글로벌 거시 지표와 시장 핵심 동향을 한눈에 파악하고, 퀀트 알고리즘으로 엄선한 유망 종목을 발굴합니다.
            </p>
            <ul style="color: #94A3B8; font-size: 0.9rem; padding-left: 1.2rem; line-height: 1.8; word-break: keep-all;">
                <li>6대 핵심 지표 및 장 개장/프리마켓 상태 실시간 안내</li>
                <li>오늘의 핵심 3줄 브리핑 및 공포/탐욕 심리 진단</li>
                <li>퀀트 기반 유망 종목 Top 3 발굴 및 원클릭 종목코드 복사</li>
            </ul>
        </div>
    """, unsafe_allow_html=True)
    st.page_link("pages/1_시장_브리핑.py", label="🌐 시장 브리핑 바로가기", icon="👉", use_container_width=True)

with col2:
    st.markdown("""
        <div class="fin-card">
            <h3 style="margin-top: 0; color: #34D399; display: flex; align-items: center; gap: 8px; word-break: keep-all;">
                💼 2. 스마트 포트폴리오 관리
            </h3>
            <p style="color: #CBD5E1; font-size: 0.95rem; line-height: 1.6; word-break: keep-all;">
                증권사별 다중 계좌 보유 종목을 안전하게 관리하고, 실시간 환율 반영 및 분할 매매 전략 가이드를 제공합니다.
            </p>
            <ul style="color: #94A3B8; font-size: 0.9rem; padding-left: 1.2rem; line-height: 1.8; word-break: keep-all;">
                <li>토스/키움/한투 등 다중 계좌(증권사)별 분리 모니터링</li>
                <li>미국 주식 실시간 환율 반영 원화 환산 동시 제공</li>
                <li>단기 지지선(-4%) 및 저항선(+8%) 기반 분할 매매 기준가 제시</li>
                <li>DART 공시/뉴스 연동 종목별 AI 진단 한줄평 제공</li>
            </ul>
        </div>
    """, unsafe_allow_html=True)
    st.page_link("pages/2_포트폴리오.py", label="💼 포트폴리오 관리 바로가기", icon="👉", use_container_width=True)

st.markdown("---")

# 서비스 핵심 특징 하이라이트
st.markdown("#### ⚡ 서비스 핵심 특징")
c1, c2, c3 = st.columns(3)
with c1:
    st.info("**🚀 초고속 인메모리 캐시**\n\n주요 시장 시세 및 퀀트 랭킹 데이터를 실시간 메모리 캐싱하여 딜레이 없는 초고속 로딩을 지원합니다.")
with c2:
    st.info("**☁️ Supabase 클라우드 영구 보존**\n\n안전한 클라우드 데이터베이스를 통해 재접속이나 기기 변경 시에도 보유 자산이 안전하게 보존됩니다.")
with c3:
    st.info("**📱 완벽한 모바일 반응형 뷰**\n\n스마트폰 화면에서도 가로 스크롤 없이 컴팩트한 카드 뷰와 터치 최적화 인터랙션을 제공합니다.")
