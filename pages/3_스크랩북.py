"""
3페이지: [📰 나의 투자 스크랩북]
- 투자 판단의 근거가 된 주요 뉴스와 공시를 모아보고 관리하는 전용 스크랩북 대시보드
- 종목별 필터링, 스크랩 통계 뱃지, 메모 인라인/모달 수정 및 2단계 확인 삭제 지원
"""
from pathlib import Path
from datetime import datetime
import streamlit as st

from db.portfolio_repo import PortfolioRepository
from db.supabase_client import is_supabase_configured
from services.scrap_service import (
    get_scraps,
    update_scrap_memo,
    delete_scrap,
)
from services.news_disclosure_service import render_collection_criteria_content

# ------------------------------------------------------------------------------
# 1. 멀티페이지 세션 상태 방어 코드 (Session Guard)
# ------------------------------------------------------------------------------
if "user" not in st.session_state:
    st.session_state.user = None
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "pending_toast" not in st.session_state:
    st.session_state.pending_toast = None


# ------------------------------------------------------------------------------
# 2. 전역 커스텀 CSS 주입
# ------------------------------------------------------------------------------
def inject_custom_css():
    css_path = Path(__file__).resolve().parent.parent / "assets" / "style.css"
    if css_path.exists():
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


inject_custom_css()

# 레포지토리 인스턴스 보장 (핫 리로드 방어)
import importlib
import db.portfolio_repo

if not hasattr(PortfolioRepository, "get_scraps"):
    importlib.reload(db.portfolio_repo)
    from db.portfolio_repo import PortfolioRepository

repo = PortfolioRepository()


# ------------------------------------------------------------------------------
# 3. 사이드바 상태 및 브랜딩
# ------------------------------------------------------------------------------
with st.sidebar:
    st.markdown("""
        <div style="padding: 0.5rem 0 1rem 0;">
            <h2 style="margin: 0; font-size: 1.45rem; color: #F8FAFC; display: flex; align-items: center; gap: 8px;">
                🥔 알감자 (AI Potato)
            </h2>
            <span style="font-size: 0.8rem; color: #94A3B8;">작지만 알찬 나만의 스마트 자산 관리 대시보드</span>
        </div>
    """, unsafe_allow_html=True)

    if is_supabase_configured():
        st.success("🔒 **Supabase 클라우드 동기화**\n\n(스크랩북 영구 보존 활성)", icon="✅")
    else:
        st.warning("⚠️ **로컬 데모 모드 (인메모리)**\n\n(세션 종료 시 초기화)", icon="ℹ️")

    st.markdown("---")

    if st.session_state.get("authenticated") and st.session_state.get("user"):
        u_name = st.session_state.user.get("username", "사용자")
        st.info(f"👤 접속자: **{u_name}**님", icon="✨")
        if st.button("로그아웃", use_container_width=True, key="scrap_sidebar_logout"):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.rerun()


# ------------------------------------------------------------------------------
# 4. 비로그인 사용자 가드 및 로그인 유도
# ------------------------------------------------------------------------------
if not st.session_state.get("authenticated") or not st.session_state.get("user"):
    st.markdown("""
        <div style="margin-bottom: 1.5rem;">
            <h2 class="page-hero-title" style="color: #F8FAFC; margin-bottom: 0.5rem;">
                📰 나의 투자 스크랩북
            </h2>
            <p style="color: #94A3B8; font-size: 1rem; line-height: 1.5;">
                투자 판단의 근거가 된 주요 뉴스와 공시를 모아보고 메모를 관리합니다.
            </p>
        </div>
    """, unsafe_allow_html=True)

    auth_col1, auth_col2 = st.columns(2, gap="large")
    with auth_col1:
        st.markdown('<div class="fin-card">', unsafe_allow_html=True)
        st.markdown("#### 🔐 로그인 / 간편 계정 생성")
        with st.form("scrap_login_form"):
            in_user = st.text_input("아이디 (영문/숫자)", placeholder="예: investor101")
            in_pin = st.text_input("PIN 번호 (숫자 4자리)", type="password", max_chars=4, placeholder="••••")
            submitted = st.form_submit_button("시작하기 / 로그인", use_container_width=True, type="primary")
            if submitted:
                if not in_user or not in_pin:
                    st.error("아이디와 PIN 4자리를 모두 입력해주세요.")
                else:
                    success, user_obj, msg = repo.authenticate_or_create_user(in_user, in_pin)
                    if success:
                        st.session_state.authenticated = True
                        st.session_state.user = user_obj
                        st.rerun()
                    else:
                        st.error(msg)
        st.markdown('</div>', unsafe_allow_html=True)

    with auth_col2:
        st.markdown('<div class="fin-card" style="border-top: 3px solid #10B981;">', unsafe_allow_html=True)
        st.markdown("#### 🚀 원클릭 데모 계정 체험")
        st.markdown("""
            입력 없이 바로 스크랩북 기능을 체험해보실 수 있도록 사전 구성 데모 계정을 제공합니다.
            - **테스트 ID**: `demo`
            - **테스트 PIN**: `1234`
        """)
        if st.button("🌟 데모 계정으로 즉시 체험하기", use_container_width=True, type="secondary", key="scrap_demo_btn"):
            success, user_obj, msg = repo.authenticate_or_create_user("demo", "1234")
            if success:
                st.session_state.authenticated = True
                st.session_state.user = user_obj
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.stop()


# ------------------------------------------------------------------------------
# 5. 로그인 사용자: 상단 타이틀 및 Toast 처리
# ------------------------------------------------------------------------------
current_user = st.session_state.user
user_id = current_user.get("id")
username = current_user.get("username", "사용자")

if st.session_state.get("pending_toast"):
    t_msg, t_icon = st.session_state.pending_toast
    st.toast(t_msg, icon=t_icon)
    st.session_state.pending_toast = None


# ------------------------------------------------------------------------------
# 6. 모달 다이얼로그 정의 (@st.dialog)
# ------------------------------------------------------------------------------
@st.dialog("✏️ 투자 메모 수정", width="medium")
def edit_scrap_memo_dialog(scrap_id: str, title: str, curr_memo: str):
    st.markdown(f"**📰 {title}**")
    new_memo = st.text_area(
        "투자 메모 수정",
        value=curr_memo or "",
        placeholder="투자 메모나 코멘트를 입력하세요.",
        height=130,
        key=f"edit_memo_ta_{scrap_id}"
    )

    ec1, ec2 = st.columns(2)
    with ec1:
        if st.button("취소", use_container_width=True, key=f"edit_cancel_{scrap_id}"):
            st.rerun()
    with ec2:
        if st.button("저장 완료", type="primary", use_container_width=True, key=f"edit_save_{scrap_id}"):
            ok, msg = update_scrap_memo(scrap_id=scrap_id, new_memo=new_memo, repo=repo)
            if ok:
                st.session_state.pending_toast = ("✅ 메모가 수정되었습니다!", "✏️")
                st.rerun()
            else:
                st.error(msg)


@st.dialog("🗑️ 스크랩 삭제 확인", width="small")
def confirm_delete_scrap_dialog(scrap_id: str, title: str):
    st.warning("⚠️ **정말 이 스크랩 기사를 삭제하시겠습니까?**")
    st.markdown(f"<div style='font-size: 0.92rem; color: #CBD5E1; margin: 8px 0 16px 0; word-break: keep-all;'>{title}</div>", unsafe_allow_html=True)
    st.caption("삭제된 스크랩북 항목은 복구할 수 없습니다.")

    dc1, dc2 = st.columns(2)
    with dc1:
        if st.button("취소", use_container_width=True, key=f"del_cancel_{scrap_id}"):
            st.rerun()
    with dc2:
        if st.button("삭제하기", type="primary", use_container_width=True, key=f"del_confirm_{scrap_id}"):
            ok, msg = delete_scrap(scrap_id=scrap_id, repo=repo)
            if ok:
                st.session_state.pending_toast = ("🗑️ 스크랩이 삭제되었습니다.", "✨")
                st.rerun()
            else:
                st.error(msg)


# ------------------------------------------------------------------------------
# 7. 페이지 헤더 & 소개
# ------------------------------------------------------------------------------
st.markdown("""
    <div style="margin-bottom: 1.2rem;">
        <h2 class="page-hero-title" style="color: #F8FAFC; margin-bottom: 0.35rem; display: flex; align-items: center; gap: 8px;">
            📰 나의 투자 스크랩북
        </h2>
        <p style="color: #94A3B8; font-size: 0.98rem; margin: 0; line-height: 1.5; word-break: keep-all;">
            투자 판단의 근거가 된 주요 뉴스와 공시를 모아봅니다.
        </p>
    </div>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# 8. 상단 필터 바 및 통계 뱃지
# ------------------------------------------------------------------------------
# 전체 스크랩 내역을 먼저 조회하여 고유 종목 목록 추출
all_scraps = get_scraps(user_id=user_id, ticker_filter="전체", repo=repo)
portfolio_items = repo.get_items(user_id)

# 보유 종목명 및 스크랩된 종목명 합산 옵션 구성
item_names_set = set()
for p in portfolio_items:
    if p.get("name"):
        item_names_set.add(p["name"].strip())
for s in all_scraps:
    if s.get("item_name"):
        item_names_set.add(s["item_name"].strip())

filter_options = ["전체 종목 보기"] + sorted(list(item_names_set))

filter_col1, filter_col2, filter_col3 = st.columns([2.6, 1.1, 1.3], vertical_alignment="center")
with filter_col1:
    selected_filter = st.selectbox(
        "종목별 필터",
        options=filter_options,
        index=0,
        label_visibility="collapsed",
        key="scrap_stock_filter_sel"
    )

with filter_col2:
    with st.popover("ℹ️ 수집 기준", use_container_width=True, help="뉴스 및 공시 수집 기준표를 확인합니다."):
        render_collection_criteria_content()

with filter_col3:
    total_count = len(all_scraps)
    st.markdown(
        f"""
        <div style="text-align: right; display: flex; justify-content: flex-end; align-items: center; gap: 8px;">
            <span style="background: rgba(59, 130, 246, 0.15); color: #60A5FA; border: 1px solid rgba(59, 130, 246, 0.35); font-size: 0.85rem; font-weight: 700; padding: 4px 12px; border-radius: 9999px;">
                ⭐ 총 {total_count}건
            </span>
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# 9. 필터 적용 및 스크랩 카드 목록 렌더링
# ------------------------------------------------------------------------------
active_filter_arg = "전체" if selected_filter == "전체 종목 보기" else selected_filter
filtered_scraps = get_scraps(user_id=user_id, ticker_filter=active_filter_arg, repo=repo)

if not filtered_scraps:
    st.markdown(
        """
        <div style="background: rgba(30, 41, 59, 0.4); border: 1px dashed rgba(148, 163, 184, 0.25); border-radius: 12px; padding: 2.5rem 1.5rem; text-align: center; margin-top: 1rem;">
            <div style="font-size: 2.2rem; margin-bottom: 0.6rem;">📂</div>
            <div style="font-weight: 700; font-size: 1.05rem; color: #F1F5F9; margin-bottom: 0.4rem;">
                아직 스크랩한 기사가 없습니다.
            </div>
            <div style="font-size: 0.88rem; color: #94A3B8; margin-bottom: 1.2rem;">
                포트폴리오 탭에서 보유 종목의 주요 분배금 소식이나 공시를 <b>[⭐ 스크랩]</b> 버튼으로 북마크해보세요!
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.page_link("pages/2_포트폴리오.py", label="💼 포트폴리오 주요 소식 보러가기", icon="👉", use_container_width=True)
else:
    for idx, scrap in enumerate(filtered_scraps):
        s_id = str(scrap.get("id"))
        s_ticker = scrap.get("ticker") or ""
        s_item = scrap.get("item_name") or s_ticker or "관심종목"
        s_title = scrap.get("title", "")
        s_url = scrap.get("origin_url", "#")
        s_source = scrap.get("source") or "뉴스/공시"
        s_memo = (scrap.get("memo") or "").strip()
        raw_created = scrap.get("created_at")

        date_display = ""
        if raw_created:
            try:
                dt_val = datetime.fromisoformat(str(raw_created).replace("Z", "+00:00"))
                date_display = dt_val.strftime("%Y-%m-%d %H:%M")
            except Exception:
                date_display = str(raw_created)[:16]

        memo_html = (
            f'<div class="scrap-memo-box">💬 <b>투자 메모:</b> {s_memo}</div>'
            if s_memo
            else '<div class="scrap-memo-box empty">💬 작성된 메모가 없습니다.</div>'
        )

        with st.container():
            st.markdown(
                f"""
                <div class="scrap-card">
                    <div class="scrap-header">
                        <span class="scrap-badge-stock">[{s_item}]</span>
                        <span class="scrap-meta-info">출처: <b>{s_source}</b></span>
                        <span class="scrap-meta-info">· 스크랩: {date_display}</span>
                    </div>
                    <a href="{s_url}" target="_blank" class="scrap-title-link">
                        {s_title} ↗
                    </a>
                    {memo_html}
                </div>
                """,
                unsafe_allow_html=True
            )

            # 모바일 최적화 액션 버튼 행
            btn_c1, btn_c2, btn_spacer = st.columns([1.2, 1.0, 3.8], vertical_alignment="center")
            with btn_c1:
                if st.button("✏️ 메모 수정", key=f"scrap_edit_btn_{s_id}", use_container_width=True, type="secondary"):
                    edit_scrap_memo_dialog(scrap_id=s_id, title=s_title, curr_memo=s_memo)
            with btn_c2:
                if st.button("🗑️ 삭제", key=f"scrap_del_btn_{s_id}", use_container_width=True, type="secondary"):
                    confirm_delete_scrap_dialog(scrap_id=s_id, title=s_title)

            st.markdown("<div style='height: 0.3rem;'></div>", unsafe_allow_html=True)
