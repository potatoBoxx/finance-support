"""FinScope - 금융 데이터 반응형 대시보드 메인 엔트리포인트 (app.py)

1. 반응형 와이드 레이아웃 (PC 및 모바일 완벽 대응)
2. 사이드바 멀티페이지 네비게이션:
   - 1페이지: 시장 브리핑 및 발굴 (pages/market_briefing.py)
   - 2페이지: 개인 포트폴리오 관리 (pages/portfolio.py)
3. 세션 상태 관리 (st.session_state)
"""

from pathlib import Path
import streamlit as st
from pages.market_briefing import show_market_briefing_page
from pages.portfolio import show_portfolio_page

# ----------------------------------------------------
# 1. 페이지 기본 설정 (반응형 와이드 레이아웃)
# ----------------------------------------------------
st.set_page_config(
    page_title="FinScope - 금융 데이터 대시보드",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ----------------------------------------------------
# 2. 반응형 커스텀 CSS 주입
# ----------------------------------------------------
def inject_custom_css():
    """assets/style.css 스타일시트를 로드하여 Streamlit 앱에 주입합니다."""
    css_path = Path(__file__).resolve().parent / "assets" / "style.css"
    if css_path.exists():
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()
            st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)


inject_custom_css()


# ----------------------------------------------------
# 3. 세션 상태 (Session State) 초기화
# ----------------------------------------------------
if "is_authenticated" not in st.session_state:
    st.session_state.is_authenticated = False

if "user_id" not in st.session_state:
    st.session_state.user_id = None


# ----------------------------------------------------
# 4. 멀티페이지 라우팅 (st.navigation 활용)
# ----------------------------------------------------
# Streamlit 1.36+ 공식 네비게이션 API 활용
page_market = st.Page(
    show_market_briefing_page,
    title="시장 브리핑 및 발굴",
    icon="🌐",
    default=True,
    url_path="market-briefing",
)

page_portfolio = st.Page(
    show_portfolio_page,
    title="개인 포트폴리오 관리",
    icon="💼",
    url_path="portfolio",
)

# 사이드바 상단 브랜딩 및 사용자 상태 위젯
with st.sidebar:
    st.markdown("""
        <div style="padding: 0.5rem 0 1rem 0;">
            <h2 style="margin: 0; font-size: 1.4rem; color: #f8fafc; display: flex; align-items: center; gap: 8px;">
                📈 FinScope
            </h2>
            <span style="font-size: 0.8rem; color: #94a3b8;">Financial Intelligence Dashboard</span>
        </div>
    """, unsafe_allow_html=True)

    # 사용자 로그인 상태 뱃지
    if st.session_state.is_authenticated:
        st.success(f"👤 접속 계정: **{st.session_state.user_id}**", icon="✅")
    else:
        st.info("🔒 비로그인 상태 (게스트)", icon="ℹ️")

    st.markdown("---")

# 네비게이션 실행
nav = st.navigation(
    {
        "대시보드 메뉴": [page_market, page_portfolio]
    }
)

nav.run()

# 사이드바 하단 정보
with st.sidebar:
    st.markdown("---")
    st.caption("📱 **모바일 최적화 안내**\n\n모바일 브라우저에서도 최적의 비율로 반응형 레이아웃이 적용됩니다.")
    st.caption("🔧 v1.0.0 (Mock Data Mode)")
