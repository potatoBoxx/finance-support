"""
2페이지: [개인 포트폴리오 관리]
- Session Guard: F5 새로고침 및 직접 진입 시 세션 기본값 보장
- 인증 영역: ID 및 4자리 PIN 로그인 / 자동 신규 계정 생성 및 1클릭 데모 체험
- 포트폴리오 요약: 총 투자원금, 평가금액, 평가손익, 수익률(%)
- 종목 관리: 국내(KRX)/미국(US) 종목 등록(CRUD) 및 삭제
- 실시간 평가손익 및 🚨 손절 경고 알림 실시간 판정
- 보유 종목 최신 뉴스/공시 헤드라인 타임라인
"""
from pathlib import Path
from datetime import date
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import re

from db.portfolio_repo import PortfolioRepository
from db.supabase_client import is_supabase_configured
from services.portfolio_service import (
    calculate_portfolio_performance,
    get_live_price_map,
    calculate_rebalanced_position,
    calculate_target_recommendations,
    generate_ai_comment,
    format_quantity,
    format_won_compact,
    is_valid_price,
    calculate_isa_default_maturity,
    calculate_isa_dday,
    evaluate_isa_tax_advice,
    generate_daily_portfolio_briefing,
)
from services.market_service import fetch_market_indices
from services.news_service import fetch_stock_news
from services.stock_search_service import search_stock_by_ticker_or_name


# ------------------------------------------------------------------------------
# 1. 멀티페이지 세션 상태 방어 코드 (Session Guard)
# ------------------------------------------------------------------------------
if "user" not in st.session_state:
    st.session_state.user = None
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "portfolio_items" not in st.session_state:
    st.session_state.portfolio_items = []
if "is_demo_mode" not in st.session_state:
    st.session_state.is_demo_mode = False
if "reg_ticker" not in st.session_state:
    st.session_state.reg_ticker = ""
if "reg_name" not in st.session_state:
    st.session_state.reg_name = ""
if "reg_buy_price" not in st.session_state:
    st.session_state.reg_buy_price = 0
if "reg_in_quantity" not in st.session_state:
    st.session_state.reg_in_quantity = 1.0
if "reg_in_memo" not in st.session_state:
    st.session_state.reg_in_memo = ""
if "reg_lookup_msg" not in st.session_state:
    st.session_state.reg_lookup_msg = None
if "pending_toast" not in st.session_state:
    st.session_state.pending_toast = None
if "scroll_to_top" not in st.session_state:
    st.session_state.scroll_to_top = False
if "add_expander_expanded" not in st.session_state:
    st.session_state.add_expander_expanded = None
if "pending_reg_stock" not in st.session_state:
    st.session_state.pending_reg_stock = None


# ------------------------------------------------------------------------------
# 2. 전역 커스텀 스타일시트 주입
# ------------------------------------------------------------------------------
def inject_custom_css():
    css_path = Path(__file__).resolve().parent.parent / "assets" / "style.css"
    if css_path.exists():
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


inject_custom_css()

# 레포지토리 인스턴스 생성
repo = PortfolioRepository()


# ------------------------------------------------------------------------------
# 3. 사이드바 상태 및 브랜딩
# ------------------------------------------------------------------------------
with st.sidebar:
    st.markdown("""
        <div style="padding: 0.5rem 0 1rem 0;">
            <h2 style="margin: 0; font-size: 1.45rem; color: #F8FAFC; display: flex; align-items: center; gap: 8px;">
                📈 FinScope
            </h2>
            <span style="font-size: 0.8rem; color: #94A3B8;">2. 개인 포트폴리오 관리</span>
        </div>
    """, unsafe_allow_html=True)

    if is_supabase_configured():
        st.success("🔒 **Supabase 클라우드 모드**\n\n(영구 저장 및 자동 백업)", icon="✅")
    else:
        st.warning("⚠️ **로컬 데모 모드 (인메모리)**\n\n(세션 종료 시 초기화)", icon="ℹ️")

    st.markdown("---")

    if st.session_state.authenticated and st.session_state.user:
        uname = st.session_state.user.get("username", "사용자")
        st.info(f"👤 접속: **{uname}**님", icon="✨")
        if st.button("로그아웃", use_container_width=True, key="p2_sidebar_logout"):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.rerun()


# ------------------------------------------------------------------------------
# 4. 인증 영역 (로그인 / 자동 회원가입 / 데모 체험)
# ------------------------------------------------------------------------------
if not st.session_state.authenticated or not st.session_state.user:
    st.markdown("""
        <div style="margin-bottom: 1.5rem;">
            <h2 class="page-sub-title" style="color: #F8FAFC; margin-bottom: 0.25rem; word-break: keep-all; letter-spacing: -0.5px;">
                💼 개인 포트폴리오 로그인
            </h2>
            <p style="color: #94A3B8; font-size: 0.95rem; margin: 0; word-break: keep-all; letter-spacing: -0.3px;">
                사용자 식별(ID)과 보안 PIN을 통해 개인 보유 종목을 안전하게 분리 관리합니다.
            </p>
        </div>
    """, unsafe_allow_html=True)

    auth_col1, auth_col2 = st.columns([1.2, 1], gap="large")

    with auth_col1:
        st.markdown('<div class="fin-card">', unsafe_allow_html=True)
        st.markdown("#### 🔐 ID / PIN 간편 로그인 & 자동 가입")
        st.caption("처음 입력하는 ID는 새 계정으로 자동 생성되며, 기존 ID는 설정한 4자리 PIN으로 인증됩니다.")

        with st.form("login_form"):
            input_username = st.text_input("사용자 ID", placeholder="예: myinvestor, john", max_chars=30)
            input_pin = st.text_input("보안 PIN 번호 (4자리 이상 숫자)", type="password", placeholder="예: 1234", max_chars=10)
            submit_login = st.form_submit_button("로그인 / 시작하기", use_container_width=True, type="primary")

            if submit_login:
                if not input_username or not input_pin:
                    st.error("사용자 ID와 PIN 번호를 모두 입력해주세요.")
                else:
                    success, user_obj, msg = repo.authenticate_or_create_user(input_username, input_pin)
                    if success:
                        st.session_state.authenticated = True
                        st.session_state.user = user_obj
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
        st.markdown('</div>', unsafe_allow_html=True)

    with auth_col2:
        st.markdown('<div class="fin-card" style="border-top: 3px solid #10B981;">', unsafe_allow_html=True)
        st.markdown("#### 🚀 원클릭 데모 계정 체험")
        st.markdown("""
            입력 없이 바로 대시보드 기능을 체험해보실 수 있도록 삼성전자, 애플, 엔비디아가 포함된 사전 구성 데모 계정을 제공합니다.
            - **테스트 ID**: `demo`
            - **테스트 PIN**: `1234`
        """)
        if st.button("🌟 데모 계정으로 즉시 체험하기", use_container_width=True, type="secondary"):
            success, user_obj, msg = repo.authenticate_or_create_user("demo", "1234")
            if success:
                st.session_state.authenticated = True
                st.session_state.user = user_obj
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.stop()


# ------------------------------------------------------------------------------
# 5. 로그인 완료 시: 상단 환영 바 및 계정 정보
# ------------------------------------------------------------------------------
current_user = st.session_state.user
user_id = current_user.get("id")
username = current_user.get("username", "사용자")

# 상단 뷰 포커스 & 스크롤 복귀 앵커 및 알림(Toast) 처리
st.markdown('<div id="portfolio-top"></div>', unsafe_allow_html=True)

if st.session_state.get("pending_toast"):
    t_msg, t_icon = st.session_state.pending_toast
    st.toast(t_msg, icon=t_icon)
    st.session_state.pending_toast = None

if st.session_state.get("scroll_to_top"):
    st.session_state.scroll_to_top = False
    components.html("""
        <script>
            (function() {
                try {
                    const parentDoc = window.parent.document;
                    const topTarget = parentDoc.getElementById('portfolio-top');
                    if (topTarget) {
                        topTarget.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                    const mainContainer = parentDoc.querySelector('section.main') || parentDoc.querySelector('[data-testid="stMain"]');
                    if (mainContainer) {
                        mainContainer.scrollTo({ top: 0, behavior: 'smooth' });
                    }
                    window.parent.scrollTo({ top: 0, behavior: 'smooth' });
                } catch(e) {
                    console.log('Scroll to top executed', e);
                }
            })();
        </script>
    """, height=0, width=0)

with st.container(key="portfolio_user_header_container"):
    top_col1, top_col2 = st.columns([3.5, 0.9], vertical_alignment="center")
    with top_col1:
        st.markdown(f"""
            <div class="portfolio-header-box" style="margin-bottom: 0.15rem;">
                <h2 class="portfolio-header-title" style="font-size: 1.35rem; font-weight: 700; color: #F8FAFC; margin: 0 0 0.15rem 0; letter-spacing: -0.5px;">
                    👤 {username}님의 투자 포트폴리오
                </h2>
                <span class="portfolio-header-sub" style="font-size: 0.78rem; color: #94A3B8;">
                    식별 ID: <code>{user_id[:8]}...</code> | {'🔒 Supabase 클라우드 저장' if is_supabase_configured() else '⚠️ 로컬 데모 저장소'}
                </span>
            </div>
        """, unsafe_allow_html=True)
    with top_col2:
        if st.button("로그아웃", key="top_logout_btn", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.rerun()



# ------------------------------------------------------------------------------
# 5-1. 계좌 관리 모달 다이얼로그 (@st.dialog)
# ------------------------------------------------------------------------------
@st.dialog("🏦 계좌 관리 및 신규 등록", width="medium")
def manage_accounts_dialog(user_id: str, repo: PortfolioRepository):
    st.markdown("""
        <div style="margin-bottom: 0.8rem;">
            <p style="margin: 0; color: #94A3B8; font-size: 0.9rem; word-break: keep-all;">
                증권사별 계좌(일반, ISA, 연금저축, IRP)를 등록하고 만기일 및 절세 혜택을 통합 관리합니다.
            </p>
        </div>
    """, unsafe_allow_html=True)

    acc_tab_new, acc_tab_list = st.tabs(["➕ 새 계좌 등록", "📋 보유 계좌 목록"])

    with acc_tab_new:
        broker_presets = ["토스증권", "키움증권", "미래에셋", "한국투자증권", "KB증권", "신한투자증권", "NH투자증권", "삼성증권", "직접 입력"]
        ac_c1, ac_c2 = st.columns(2)
        with ac_c1:
            sel_broker = st.selectbox("증권사 선택*", options=broker_presets, key="dlg_acc_broker_sel")
            if sel_broker == "직접 입력":
                broker_name = st.text_input("증권사명 직접 입력*", placeholder="예: 유안타증권", key="dlg_acc_broker_custom")
            else:
                broker_name = sel_broker
        with ac_c2:
            acc_type = st.selectbox("계좌 유형*", options=["일반", "ISA", "연금저축", "IRP"], key="dlg_acc_type_sel")

        alias_val = st.text_input("계좌 별칭 (선택)", placeholder="예: 중개형ISA, 해외직투용, 미국배당주", key="dlg_acc_alias_input")

        dt_c1, dt_c2 = st.columns(2)
        with dt_c1:
            opened_date = st.date_input("개설일 (선택)", value=date.today(), key="dlg_acc_opened_dt")
        with dt_c2:
            default_mat = calculate_isa_default_maturity(opened_date) if acc_type == "ISA" else None
            maturity_date = st.date_input(
                "만기일 (선택)" + (" (💡 3년 의무보유 자동 계산)" if acc_type == "ISA" else ""),
                value=default_mat,
                key="dlg_acc_maturity_dt"
            )

        if st.button("💾 계좌 등록 완료", type="primary", use_container_width=True, key="dlg_btn_create_acc"):
            if not broker_name.strip():
                st.error("증권사명을 입력해주세요.")
            else:
                acc_payload = {
                    "broker_name": broker_name.strip(),
                    "account_type": acc_type,
                    "account_alias": alias_val.strip() or None,
                    "opened_at": opened_date.isoformat() if opened_date else None,
                    "maturity_at": maturity_date.isoformat() if maturity_date else None,
                }
                ok, new_acc, msg = repo.create_account(user_id, acc_payload)
                if ok:
                    st.success(f"✅ '{broker_name}' 계좌가 성공적으로 등록되었습니다!")
                    st.rerun()
                else:
                    st.error(msg)

    with acc_tab_list:
        cur_accs = repo.get_accounts(user_id)
        if not cur_accs:
            st.info("등록된 계좌가 없습니다.")
        else:
            badge_color_map = {
                "일반": ("#94A3B8", "rgba(148, 163, 184, 0.15)"),
                "ISA": ("#60A5FA", "rgba(59, 130, 246, 0.18)"),
                "연금저축": ("#34D399", "rgba(16, 185, 129, 0.18)"),
                "IRP": ("#A78BFA", "rgba(139, 92, 246, 0.18)"),
            }
            for acc in cur_accs:
                alias_str = f" ({acc['account_alias']})" if acc.get("account_alias") else ""
                atype = str(acc.get("account_type", "일반")).strip()
                text_c, bg_c = badge_color_map.get(atype, ("#94A3B8", "rgba(148, 163, 184, 0.15)"))
                badge_type_html = f'<span style="background: {bg_c}; color: {text_c}; font-size: 0.78rem; font-weight: 600; padding: 2px 7px; border-radius: 4px; border: 1px solid {text_c}44;">🏷️ {atype}</span>'

                dday_html = ""
                if atype == "ISA" and acc.get("maturity_at"):
                    dday_res = calculate_isa_dday(acc["maturity_at"])
                    if dday_res:
                        dday_html = f'<span style="background: {dday_res["badge_color"]}22; color: {dday_res["badge_color"]}; font-size: 0.78rem; font-weight: 700; padding: 2px 7px; border-radius: 4px; border: 1px solid {dday_res["badge_color"]};">⏳ {dday_res["label"]}</span>'

                # 삭제 버튼을 계좌 영역(Card Container) 안으로 포함하고, 모바일에서도 계좌유형을 줄바꿈하여 표시
                with st.container(border=True):
                    card_col_info, card_col_del = st.columns([3.5, 1.2], vertical_alignment="center")
                    with card_col_info:
                        st.markdown(
                            f"""
                            <div style="font-weight: 700; font-size: 1.02rem; color: #F8FAFC; word-break: keep-all; margin-bottom: 4px;">
                                {acc.get('broker_name', '기본')}{alias_str}
                            </div>
                            <div style="display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin-bottom: 5px;">
                                {badge_type_html}
                                {dday_html}
                            </div>
                            <div style="font-size: 0.78rem; color: #94A3B8;">
                                개설: {acc.get('opened_at') or '-'} &nbsp;|&nbsp; 만기: {acc.get('maturity_at') or '-'}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    with card_col_del:
                        if st.button("🗑️ 삭제", key=f"dlg_del_acc_{acc['id']}", use_container_width=True, type="secondary"):
                            del_ok, del_msg = repo.delete_account(acc["id"])
                            if del_ok:
                                st.rerun()
                            else:
                                st.error(del_msg)


# ------------------------------------------------------------------------------
# 6. 포트폴리오 데이터 조회 및 계좌 필터링 (환율 원화 환산 연동)
# ------------------------------------------------------------------------------
indices = fetch_market_indices()
usd_rate = float(indices.get("USD/KRW", {}).get("value", 1345.5))

items = repo.get_items(user_id)
user_accounts = repo.get_accounts(user_id)
price_map = get_live_price_map(items)

if st.session_state.add_expander_expanded is None:
    st.session_state.add_expander_expanded = (len(items) == 0)


# ------------------------------------------------------------------------------
# 6.1 오늘의 포트폴리오 종합 AI 진단 (최상단 배치: 1일 1회 온디맨드 캐싱 & 접이식 Expander)
# ------------------------------------------------------------------------------
today_str = date.today().isoformat()
if "portfolio_ai_expanded" not in st.session_state:
    st.session_state.portfolio_ai_expanded = False

force_refresh_briefing = st.session_state.pop("force_refresh_daily_briefing", False)

daily_briefing = None
if not force_refresh_briefing:
    daily_briefing = repo.get_daily_briefing(user_id, today_str)

if not daily_briefing:
    daily_briefing = generate_daily_portfolio_briefing(
        user_id=user_id,
        portfolio_items=items,
        accounts=user_accounts,
        market_indices=indices,
        price_map=price_map,
        briefing_date=today_str,
    )
    repo.save_daily_briefing(user_id, today_str, daily_briefing)

with st.expander(
    "🤖 오늘의 포트폴리오 AI 진단",
    expanded=st.session_state.portfolio_ai_expanded
):
    # 헤더: 진단 일시 및 [종합 리스크 + 새로고침 버튼] 1줄 수평 정렬
    r_info = daily_briefing.get("risk_analysis", {})
    r_color = r_info.get("badge_color", "#10B981")
    r_emoji = r_info.get("badge_emoji", "🟢")
    r_level = r_info.get("level", "안정")
    gen_time = daily_briefing.get("generated_at", today_str)

    st.markdown(
        f'<div style="font-size: 0.8rem; color: #94A3B8; margin-bottom: 0.35rem;">📅 진단 기준: <b>{gen_time}</b></div>',
        unsafe_allow_html=True
    )

    with st.container(key="briefing_status_header_container"):
        exp_c1, exp_c2 = st.columns([2.5, 1.2], vertical_alignment="center")
        with exp_c1:
            st.markdown(
                f'<span class="badge-tag" style="background: {r_color}22; color: {r_color}; font-weight: 700; border: 1px solid {r_color}; padding: 4px 10px; border-radius: 6px; font-size: 0.85rem; display: inline-flex; align-items: center; gap: 4px;">'
                f'{r_emoji} 종합 리스크: {r_level}'
                f'</span>',
                unsafe_allow_html=True
            )
        with exp_c2:
            if st.button("🔄 새로고침", key="refresh_daily_briefing_btn", use_container_width=True, help="오늘의 시세 및 포트폴리오 변경사항을 즉시 재분석합니다."):
                st.session_state.force_refresh_daily_briefing = True
                st.session_state.portfolio_ai_expanded = True
                st.rerun()

    # 3대 핵심 브리핑 카드
    m_info = daily_briefing.get("market_benchmark", {})
    t_info = daily_briefing.get("tax_accounts", {})
    s_metrics = daily_briefing.get("summary_metrics", {})
    tot_profit = s_metrics.get("total_profit", 0.0)
    profit_rate = s_metrics.get("total_profit_rate", 0.0)
    profit_color = "#34D399" if tot_profit > 0 else ("#F87171" if tot_profit < 0 else "#94A3B8")

    kospi_val = m_info.get("kospi_rate", 0.0)
    sp500_val = m_info.get("sp500_rate", 0.0)
    kospi_color = "#34D399" if kospi_val > 0 else ("#F87171" if kospi_val < 0 else "#94A3B8")
    sp500_color = "#34D399" if sp500_val > 0 else ("#F87171" if sp500_val < 0 else "#94A3B8")

    risk_card_cls = "card-danger" if r_info.get("level") == "경고" else ("card-warning" if r_info.get("level") == "주의" else "card-green")
    tax_status_badge = (
        '<span class="badge-tag" style="background: rgba(239, 68, 68, 0.15); color: #FCA5A5; font-size: 0.8rem; padding: 2px 8px; border-radius: 4px; border: 1px solid rgba(239, 68, 68, 0.3);">⚠️ 긴급 절세 체크</span>'
        if t_info.get("has_issue") else
        '<span class="badge-tag" style="background: rgba(16, 185, 129, 0.15); color: #6EE7B7; font-size: 0.8rem; padding: 2px 8px; border-radius: 4px; border: 1px solid rgba(16, 185, 129, 0.3);">정상 관리 중</span>'
    )

    actions = daily_briefing.get("action_items", [])
    actions_html = ""
    if actions:
        action_items_str = "".join([f'<div class="briefing-action-item">{act}</div>' for act in actions])
        actions_html = f'''
        <div class="briefing-action-box">
            <div class="briefing-action-title">🎯 오늘의 행동 가이드</div>
            {action_items_str}
        </div>
        '''

    briefing_html = f'''
    <div class="briefing-box">
        <div class="briefing-card card-blue">
            <div class="briefing-header-row">
                <span class="briefing-title" style="color: #60A5FA;">📊 1. 전체 자산 수익률 & 시장 대비 흐름</span>
                <span class="badge-tag" style="background: rgba(59, 130, 246, 0.15); color: #93C5FD; font-size: 0.8rem; padding: 2px 8px; border-radius: 4px; border: 1px solid rgba(59, 130, 246, 0.3);">
                    {m_info.get("status_tag", "시장 동행")}
                </span>
            </div>
            <p class="briefing-desc">{m_info.get("comment", "")}</p>
            <div class="briefing-meta-strip">
                <span class="briefing-meta-item">전체 누적 수익률: <b style="color: {profit_color}; font-size: 0.95rem;">{profit_rate:+.2f}%</b> ({tot_profit:+,.0f}원)</span>
                <span class="briefing-meta-item">KOSPI: <b style="color: {kospi_color};">{kospi_val:+.2f}%</b></span>
                <span class="briefing-meta-item">S&P 500: <b style="color: {sp500_color};">{sp500_val:+.2f}%</b></span>
            </div>
        </div>

        <div class="briefing-card card-green">
            <div class="briefing-header-row">
                <span class="briefing-title" style="color: #34D399;">💡 2. 계좌 및 절세 현황</span>
                {tax_status_badge}
            </div>
            <p class="briefing-desc">{t_info.get("comment", "")}</p>
            <div class="briefing-meta-strip">
                <span class="briefing-meta-item">등록 계좌: ISA <b>{t_info.get("isa_count", 0)}개</b> · 연금/IRP <b>{t_info.get("pension_count", 0)}개</b></span>
                <span class="briefing-meta-item">연금 전환 시 최대 세액공제: <b style="color: #34D399;">{int(t_info.get("max_deduction_estimate", 0)):,}원</b></span>
            </div>
        </div>

        <div class="briefing-card {risk_card_cls}">
            <div class="briefing-header-row">
                <span class="briefing-title" style="color: {r_color};">🛡️ 3. 포트폴리오 리스크 & 자산 분산</span>
                <span class="badge-tag" style="background: {r_color}18; color: {r_color}; font-size: 0.8rem; padding: 2px 8px; border-radius: 4px; border: 1px solid {r_color}44;">
                    손절 경고: {r_info.get("stop_loss_count", 0)}건
                </span>
            </div>
            <p class="briefing-desc">{r_info.get("comment", "")}</p>
            <div class="briefing-meta-strip">
                <span class="briefing-meta-item" style="white-space: nowrap;">자산 배분: 국내(KRX) <b>{r_info.get("krx_ratio", 50.0)}%</b> · 해외(US) <b>{r_info.get("us_ratio", 50.0)}%</b></span>
            </div>
        </div>

        {actions_html}
    </div>
    '''

    try:
        st.html(briefing_html)
    except Exception:
        st.markdown(briefing_html, unsafe_allow_html=True)

    st.markdown('<div class="briefing-pref-container">', unsafe_allow_html=True)
    keep_open = st.checkbox(
        "다음 방문 시 기본으로 펼쳐보기",
        value=st.session_state.portfolio_ai_expanded,
        key="portfolio_ai_keep_open_pref",
        help="체크하면 다음 페이지 방문 시 이 진단 영역이 자동으로 펼쳐진 상태로 시작됩니다."
    )
    st.session_state.portfolio_ai_expanded = keep_open
    st.markdown('</div>', unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# 6.2 계좌 필터링 및 관리 (콤보박스 + [+] 버튼 + ISA 만기 뱃지)
# ------------------------------------------------------------------------------
def format_acc_label(acc: dict) -> str:
    bname = acc.get("broker_name", "기본")
    alias = acc.get("account_alias")
    atype = acc.get("account_type", "일반")
    tag = alias if alias else atype
    return f"{bname} - {tag}"


account_label_map = {format_acc_label(a): a for a in user_accounts}
registered_brokers = {a.get("broker_name") for a in user_accounts}

# 하위 호환성: 등록된 계좌(accounts)에 전혀 속하지 않는 고아(Orphan) 레거시 계좌만 추가
legacy_accounts = [str(it.get("account") or "").strip() for it in items if it.get("account")]
orphan_legacy_accounts = [
    leg for leg in legacy_accounts
    if leg and leg not in registered_brokers and leg not in account_label_map
]

account_filter_options = ["전체 계좌 보기"] + list(account_label_map.keys())
for orphan in orphan_legacy_accounts:
    if orphan not in account_filter_options:
        account_filter_options.append(orphan)

if "selected_account_filter" not in st.session_state or st.session_state.selected_account_filter not in account_filter_options:
    st.session_state.selected_account_filter = "전체 계좌 보기"

with st.container(key="account_filter_container"):
    st.markdown("""
        <div class="account-filter-label-row">
            <span class="account-filter-label-text">📁 계좌 / 금융앱 선택</span>
            <span class="account-inline-tooltip" tabindex="0" role="button" aria-label="계좌 필터 도움말">
                <span class="tooltip-icon">ℹ️</span>
                <span class="tooltip-bubble">특정 계좌를 선택하면 해당 계좌에 속한 자산 총액, 손익, 종목만 필터링됩니다.</span>
            </span>
        </div>
    """, unsafe_allow_html=True)
    filt_c1, filt_c2 = st.columns([4.2, 0.8], vertical_alignment="center")
    with filt_c1:
        sel_account = st.selectbox(
            "📁 계좌 / 금융앱 선택",
            options=account_filter_options,
            index=account_filter_options.index(st.session_state.selected_account_filter),
            key="portfolio_account_filter_sel",
            label_visibility="collapsed"
        )
        st.session_state.selected_account_filter = sel_account

    with filt_c2:
        if st.button("➕", key="top_manage_acc_btn", use_container_width=True, help="➕ 계좌 관리: 계좌 추가/수정/삭제 및 ISA 만기 관리"):
            manage_accounts_dialog(user_id, repo)

# 계좌 필터 적용: account_id 매핑 우선, 없는 경우 레거시 텍스트 fallback
selected_acc_obj = account_label_map.get(sel_account)
if sel_account != "전체 계좌 보기":
    if selected_acc_obj:
        target_acc_id = selected_acc_obj.get("id")
        target_broker = selected_acc_obj.get("broker_name")
        filtered_items = [
            it for it in items
            if (it.get("account_id") and it.get("account_id") == target_acc_id)
            or (not it.get("account_id") and str(it.get("account") or "").strip() == target_broker)
        ]
    else:
        filtered_items = [it for it in items if str(it.get("account") or "기본").strip() == sel_account]
else:
    filtered_items = items

# 계좌 상태 뱃지 (ISA 만기 안내가 있는 경우만 표시, 일반 조회계좌 텍스트는 완전 삭제)
if selected_acc_obj and selected_acc_obj.get("account_type") == "ISA" and selected_acc_obj.get("maturity_at"):
    dday_res = calculate_isa_dday(selected_acc_obj.get("maturity_at"))
    if dday_res:
        st.html(
            f'<div class="account-status-bar" style="margin-top: -0.25rem; margin-bottom: 0.25rem; display: flex; align-items: center; gap: 8px;">'
            f'<span class="badge-tag" style="background: {dday_res["badge_color"]}22; color: {dday_res["badge_color"]}; font-weight: 700; border: 1px solid {dday_res["badge_color"]}; padding: 2px 8px; border-radius: 6px; font-size: 0.8rem;">'
            f'⏳ ISA 만기: {dday_res["label"]} ({selected_acc_obj.get("maturity_at")})'
            f'</span>'
            f'</div>'
        )

perf_df, summary = calculate_portfolio_performance(filtered_items, price_map, usd_krw_rate=usd_rate)



# ------------------------------------------------------------------------------
# 7. 상단 요약 영역 2개 탭 분리: [자산 종합 현황] vs [핵심 요약 및 추천가 분석] (1클릭 즉각 전환 및 최신 탭 무결성 보장)
# ------------------------------------------------------------------------------
def inject_tab_lock_and_loading_script():
    js_code = """
    <script>
    (function() {
        try {
            var doc = (typeof window !== 'undefined' && window.parent && window.parent.document) || (typeof document !== 'undefined' ? document : null);
            if (!doc) return;

            function initTabSync() {
                try {
                    if (doc.body && doc.body.classList) {
                        doc.body.classList.remove('tab-switching');
                    }
                    var existingToast = doc.getElementById('fin-tab-loading-toast');
                    if (existingToast && existingToast.classList) {
                        existingToast.classList.remove('visible');
                    }

                    if (doc._finscopeTabClickSyncAttached) return;
                    doc._finscopeTabClickSyncAttached = true;

                    doc.addEventListener('click', function(e) {
                        try {
                            var tabBtn = e.target.closest ? e.target.closest('[role="tab"], [data-baseweb="tab"]') : null;
                            if (!tabBtn) return;

                            var tabText = tabBtn.innerText || tabBtn.textContent || '';
                            var isRecom = tabText.indexOf('추천가') !== -1 || tabText.indexOf('핵심 요약') !== -1;
                            var tabName = isRecom ? '🎯 핵심 요약 및 추천가 분석' : '💼 자산 종합 현황';
                            var tabParam = isRecom ? 'recom' : 'summary';

                            var win = (typeof window !== 'undefined' && window.parent) || window;
                            win._finscopeLatestTab = tabName;
                            sessionStorage.setItem('finscope_portfolio_active_tab', tabName);
                            var url = new URL(win.location.href);
                            url.searchParams.set('tab', tabParam);
                            win.history.replaceState(null, '', url.toString());
                        } catch(err) {}
                    });
                } catch(e) {}
            }

            if (doc.readyState === 'loading') {
                doc.addEventListener('DOMContentLoaded', initTabSync);
            } else {
                initTabSync();
            }
        } catch(err) {}
    })();
    </script>
    """
    st.html(f"<div style='display:none;'>{js_code}</div>", unsafe_allow_javascript=True)
    try:
        import streamlit.components.v1 as components
        components.html(js_code, height=0, width=0)
    except Exception:
        pass


def inject_number_input_enhancer_script():
    """
    모든 st.number_input에 대해:
    1. 포커스 시: 0 또는 숫자 전체 선택(select-all)으로 0 뒤에 붙는 오입력(예: 015000) 방지
    2. 블러 시: 공란이면 기본값 0 자동 복구
    3. 인풋 필드 자체 천 단위 콤마(,) 표시 오버레이 실시간 연동
    """
    js_code = """
    <script>
    (function() {
        try {
            var doc = (typeof window !== 'undefined' && window.parent && window.parent.document) || (typeof document !== 'undefined' ? document : null);
            if (!doc) return;

            function formatWithComma(numStr) {
                if (numStr === null || numStr === undefined) return '';
                var str = String(numStr).trim();
                if (str === '') return '';
                var isNegative = str.charAt(0) === '-';
                if (isNegative) str = str.substring(1);
                var parts = str.split('.');
                parts[0] = parts[0].replace(/\\B(?=(\\d{3})+(?!\\d))/g, ',');
                return (isNegative ? '-' : '') + parts.join('.');
            }

            function setupInput(input) {
                if (input._finscopeEnhanced) {
                    if (input._updateOverlay) input._updateOverlay();
                    return;
                }
                input._finscopeEnhanced = true;

                var wrapper = input.closest('[data-baseweb="base-input"]') || input.parentElement;
                if (!wrapper) return;

                wrapper.style.position = 'relative';

                var overlay = doc.createElement('div');
                overlay.className = 'finscope-number-overlay';
                overlay.style.position = 'absolute';
                overlay.style.left = '0';
                overlay.style.top = '0';
                overlay.style.width = '100%';
                overlay.style.height = '100%';
                overlay.style.display = 'flex';
                overlay.style.alignItems = 'center';

                var cs = window.getComputedStyle(input);
                overlay.style.paddingLeft = cs.paddingLeft || '14px';
                overlay.style.paddingRight = cs.paddingRight || '36px';
                overlay.style.fontSize = cs.fontSize || '15px';
                overlay.style.fontFamily = cs.fontFamily;
                overlay.style.fontWeight = cs.fontWeight || '400';
                overlay.style.color = '#F8FAFC';
                overlay.style.pointerEvents = 'auto';
                overlay.style.cursor = 'text';
                overlay.style.background = 'transparent';
                overlay.style.zIndex = '2';
                overlay.style.boxSizing = 'border-box';
                overlay.style.userSelect = 'none';

                wrapper.appendChild(overlay);
                input._overlayElem = overlay;

                function updateOverlay() {
                    if (!input._overlayElem) return;
                    if (doc.activeElement === input) {
                        input._overlayElem.style.display = 'none';
                        input.style.color = '#F8FAFC';
                    } else {
                        var val = input.value;
                        if (val === '' || val === null || val === undefined) {
                            input._overlayElem.textContent = '';
                            input._overlayElem.style.display = 'none';
                            input.style.color = '#F8FAFC';
                        } else {
                            input._overlayElem.textContent = formatWithComma(val);
                            input._overlayElem.style.display = 'flex';
                            input.style.color = 'transparent';
                        }
                    }
                }
                input._updateOverlay = updateOverlay;
                updateOverlay();

                // 오버레이 클릭 시 input으로 포커스 넘기고 전체 선택
                overlay.addEventListener('click', function(e) {
                    e.preventDefault();
                    input.focus();
                    setTimeout(function() {
                        try { input.select(); } catch(err) {}
                    }, 20);
                });

                // 1. 포커스 시: 0 또는 숫자 전체 선택 (0 뒤로 붙는 현상 방지)
                input.addEventListener('focus', function() {
                    overlay.style.display = 'none';
                    input.style.color = '#F8FAFC';
                    setTimeout(function() {
                        try { input.select(); } catch(err) {}
                    }, 20);
                });

                input.addEventListener('mouseup', function(e) {
                    if (this.value === '0' || this.value === '0.0') {
                        e.preventDefault();
                        this.select();
                    }
                });

                // 2. 블러 시: 공란이면 0 자동 복원, 콤마 오버레이 갱신
                input.addEventListener('blur', function() {
                    if (!input.value || input.value.trim() === '') {
                        input.value = '0';
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                    updateOverlay();
                });
            }

            function scanInputs() {
                var inputs = doc.querySelectorAll('input[data-testid="stNumberInput-Input"]');
                for (var i = 0; i < inputs.length; i++) {
                    setupInput(inputs[i]);
                }
            }

            if (doc._finscopeNumberObserver) {
                doc._finscopeNumberObserver.disconnect();
            }
            doc._finscopeNumberObserver = new MutationObserver(function() {
                try { scanInputs(); } catch(err) {}
            });
            if (doc.body) {
                doc._finscopeNumberObserver.observe(doc.body, { childList: true, subtree: true });
            }

            scanInputs();
        } catch(err) {}
    })();
    </script>
    """
    st.html(f"<div style='display:none;'>{js_code}</div>", unsafe_allow_javascript=True)
    try:
        import streamlit.components.v1 as components
        components.html(js_code, height=0, width=0)
    except Exception:
        pass


def inject_currency_input_script():
    """
    브라우저 네이티브에서 100% 실행되는 실시간 통화 입력 제어 스크립트:
    1. 입력 중(onInput): 사용자가 타이핑하는 즉시 실시간 천 단위 콤마(,) 서식화 및 스마트 커서 위치 유지
    2. 백스페이스/Delete: 콤마(,) 바로 앞에서 삭제 시 콤마에 막히지 않고 앞뒤 숫자를 매끄럽게 삭제
    3. 포커스 인: 0원인 경우 공란 처리(placeholder='0원' 노출), 기존 금액은 '원' 접미사 임시 제거 후 전체 선택
    4. 포커스 아웃: 유효 금액은 '원' 접미사 및 콤마 서식 유지, 미입력/0원은 공란 유지(placeholder '0원' 노출)
    """
    js_raw = """
(function() {
    try {
        function setupInDoc(doc) {
            if (!doc) return;
            var win = (doc.defaultView) || (typeof window !== 'undefined' ? window : null);
            if (!win) return;

            function setNativeValue(el, val) {
                var valSetter = null;
                try {
                    valSetter = Object.getOwnPropertyDescriptor(win.HTMLInputElement.prototype, 'value').set;
                } catch(e) {}
                var proto = Object.getPrototypeOf(el);
                var protoSetter = null;
                try {
                    protoSetter = Object.getOwnPropertyDescriptor(proto, 'value') ? Object.getOwnPropertyDescriptor(proto, 'value').set : null;
                } catch(e) {}

                if (protoSetter && protoSetter !== valSetter) {
                    protoSetter.call(el, val);
                } else if (valSetter) {
                    valSetter.call(el, val);
                } else {
                    el.value = val;
                }
            }

            function attachInput(input) {
                if (input._finscopeCurLiveActive) return;

                var widget = input.closest('[data-testid="stWidget"]') || 
                             input.closest('[data-testid="stTextInput"]') || 
                             input.closest('.stTextInput');
                var labelText = input.getAttribute('aria-label') || '';
                if (!labelText && widget) {
                    var lbl = widget.querySelector('label');
                    if (lbl) labelText = lbl.innerText || lbl.textContent || '';
                }
                if (!labelText) {
                    var parent = input.parentElement;
                    while (parent && parent !== doc.body) {
                        var l = parent.querySelector('label');
                        if (l) { labelText = l.innerText || l.textContent || ''; break; }
                        parent = parent.parentElement;
                    }
                }

                var isCur = (labelText.indexOf('매수가') !== -1 ||
                             labelText.indexOf('목표가') !== -1 ||
                             labelText.indexOf('손절가') !== -1 ||
                             labelText.indexOf('평단가') !== -1 ||
                             labelText.indexOf('거래 단가') !== -1 ||
                             labelText.indexOf('거래단가') !== -1 ||
                             labelText.indexOf('(원)') !== -1 ||
                             labelText.indexOf('(USD)') !== -1);
                if (!isCur) return;

                input._finscopeCurLiveActive = true;

                // 1. 실시간 입력 중 천 단위 콤마(,) 서식화 (onInput)
                input.addEventListener('input', function(e) {
                    if (this._finscopeFormatting) return;

                    var val = this.value;
                    var isWon = labelText.indexOf('원') !== -1 || labelText.indexOf('$') === -1;

                    // 커서 위치 및 커서 앞 유효 문자(비콤마) 개수 추적
                    var cursorPos = this.selectionStart || 0;
                    var nonCommasBeforeCursor = 0;
                    for (var i = 0; i < cursorPos; i++) {
                        if (val[i] !== ',' && val[i] !== '원' && val[i] !== '$') {
                            nonCommasBeforeCursor++;
                        }
                    }

                    var clean = isWon ? val.replace(/[^\\d]/g, '') : val.replace(/[^\\d.]/g, '');
                    if (!clean) {
                        if (this.value !== '') {
                            this._finscopeFormatting = true;
                            setNativeValue(this, '');
                            this.dispatchEvent(new Event('input', { bubbles: true }));
                            this._finscopeFormatting = false;
                        }
                        return;
                    }

                    var formatted = '';
                    if (isWon) {
                        clean = clean.replace(/^0+/, '') || '0';
                        formatted = clean.replace(/\\B(?=(\\d{3})+(?!\\d))/g, ',');
                    } else {
                        var parts = clean.split('.');
                        parts[0] = parts[0].replace(/^0+/, '') || '0';
                        parts[0] = parts[0].replace(/\\B(?=(\\d{3})+(?!\\d))/g, ',');
                        if (parts.length > 2) parts = [parts[0], parts.slice(1).join('')];
                        formatted = '$' + parts.join('.');
                    }

                    if (this.value === formatted) return;

                    this._finscopeFormatting = true;
                    setNativeValue(this, formatted);
                    this.dispatchEvent(new Event('input', { bubbles: true }));
                    this._finscopeFormatting = false;

                    // 비콤마 문자 개수 기준으로 커서 위치 복원
                    var newPos = 0;
                    var count = 0;
                    for (var j = 0; j < formatted.length; j++) {
                        if (formatted[j] !== ',') count++;
                        if (count === nonCommasBeforeCursor) {
                            newPos = j + 1;
                            break;
                        }
                    }
                    if (count < nonCommasBeforeCursor) {
                        newPos = formatted.length;
                    }
                    try {
                        this.setSelectionRange(newPos, newPos);
                    } catch(err) {}
                });

                // 2. 키다운 시 콤마 바로 앞뒤 백스페이스/Delete 스킵 처리
                input.addEventListener('keydown', function(e) {
                    if (e.key === 'Backspace') {
                        var pos = this.selectionStart;
                        if (pos === this.selectionEnd && pos > 0 && this.value[pos - 1] === ',') {
                            e.preventDefault();
                            var before = this.value.slice(0, pos - 2);
                            var after = this.value.slice(pos);
                            this.value = before + after;
                            this.setSelectionRange(pos - 2, pos - 2);
                            this.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                    } else if (e.key === 'Delete') {
                        var pos = this.selectionStart;
                        if (pos === this.selectionEnd && pos < this.value.length && this.value[pos] === ',') {
                            e.preventDefault();
                            var before = this.value.slice(0, pos);
                            var after = this.value.slice(pos + 2);
                            this.value = before + after;
                            this.setSelectionRange(pos, pos);
                            this.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                    }
                });

                // 3. 포커스 시: 0원이면 공란으로 클리어, 기존 값이면 '원' 접미사 제거 및 전체 선택
                input.addEventListener('focus', function() {
                    var val = this.value.trim();
                    if (val === '0원' || val === '0' || val === '$0' || val === '$0.00' || val === '0.0' || val === '0.00') {
                        this._finscopeFormatting = true;
                        setNativeValue(this, '');
                        this.dispatchEvent(new Event('input', { bubbles: true }));
                        this._finscopeFormatting = false;
                    } else {
                        var stripped = val.replace(/원$/, '').replace(/^\\$/, '').trim();
                        if (stripped !== val) {
                            this._finscopeFormatting = true;
                            setNativeValue(this, stripped);
                            this.dispatchEvent(new Event('input', { bubbles: true }));
                            this._finscopeFormatting = false;
                        }
                        var self = this;
                        setTimeout(function() {
                            try { self.select(); } catch(e){}
                        }, 20);
                    }
                });

                // 4. 클릭 시: 0원이면 공란으로 클리어
                input.addEventListener('click', function() {
                    var val = this.value.trim();
                    if (val === '0원' || val === '0' || val === '$0' || val === '$0.00' || val === '0.0' || val === '0.00') {
                        this._finscopeFormatting = true;
                        setNativeValue(this, '');
                        this.dispatchEvent(new Event('input', { bubbles: true }));
                        this._finscopeFormatting = false;
                    }
                });

                // 5. 블러 시: 유효 금액이면 '원' 접미사 부여, 미입력/0원이면 공란 유지 (placeholder '0원' 노출)
                input.addEventListener('blur', function() {
                    var val = this.value.trim();
                    var isWon = labelText.indexOf('원') !== -1 || labelText.indexOf('$') === -1;
                    var clean = isWon ? val.replace(/[^\\d]/g, '') : val.replace(/[^\\d.]/g, '');

                    if (!clean || clean === '' || parseFloat(clean) === 0) {
                        if (this.value !== '') {
                            this._finscopeFormatting = true;
                            setNativeValue(this, '');
                            this.dispatchEvent(new Event('input', { bubbles: true }));
                            this.dispatchEvent(new Event('change', { bubbles: true }));
                            this._finscopeFormatting = false;
                        }
                    } else {
                        var formatted = '';
                        if (isWon) {
                            clean = clean.replace(/^0+/, '') || '0';
                            formatted = clean.replace(/\\B(?=(\\d{3})+(?!\\d))/g, ',') + '원';
                        } else {
                            var parts = clean.split('.');
                            parts[0] = parts[0].replace(/^0+/, '') || '0';
                            parts[0] = parts[0].replace(/\\B(?=(\\d{3})+(?!\\d))/g, ',');
                            if (parts.length > 2) parts = [parts[0], parts.slice(1).join('')];
                            formatted = '$' + parts.join('.');
                        }
                        if (this.value !== formatted) {
                            this._finscopeFormatting = true;
                            setNativeValue(this, formatted);
                            this.dispatchEvent(new Event('input', { bubbles: true }));
                            this.dispatchEvent(new Event('change', { bubbles: true }));
                            this._finscopeFormatting = false;
                        }
                    }
                });
            }

            function scan() {
                var inputs = doc.querySelectorAll('input');
                for (var i = 0; i < inputs.length; i++) {
                    attachInput(inputs[i]);
                }
            }

            scan();
            if (!doc._finscopeCurLiveObs) {
                doc._finscopeCurLiveObs = new MutationObserver(scan);
                if (doc.body) {
                    doc._finscopeCurLiveObs.observe(doc.body, { childList: true, subtree: true });
                }
            }
        }

        function runAll() {
            try { setupInDoc(document); } catch(e) {}
            try {
                if (typeof window !== 'undefined' && window.parent && window.parent.document && window.parent.document !== document) {
                    setupInDoc(window.parent.document);
                }
            } catch(e) {}
        }

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', runAll);
        } else {
            runAll();
        }
    } catch(err) {}
})();
"""
    js_code = f"<script>{js_raw}</script>"
    st.html(f"<div style='display:none;'>{js_code}</div>", unsafe_allow_javascript=True)
    try:
        import streamlit.components.v1 as components
        components.html(js_code, height=0, width=0)
    except Exception:
        pass


def inject_mobile_landscape_table_script():
    """
    초슬림 퀵 에디터 가로 전체화면 모드(Landscape View) 스크립트:
    1. '가로 넓게 보기' 버튼 클릭 즉시:
       - User Gesture 내에서 document.documentElement.requestFullscreen() 및 screen.orientation.lock('landscape') 시도
    2. '닫기' 버튼 또는 다이얼로그 닫기 클릭 시:
       - document.exitFullscreen() 및 screen.orientation.unlock() 복귀
    """
    js_raw = """
(function() {
    try {
        var doc = (typeof window !== 'undefined' && window.parent && window.parent.document) || (typeof document !== 'undefined' ? document : null);
        var win = (typeof window !== 'undefined' && window.parent) || window;
        if (!doc) return;

        function exitLandscape() {
            try {
                if (doc.fullscreenElement || doc.webkitFullscreenElement) {
                    if (doc.exitFullscreen) {
                        doc.exitFullscreen().catch(function(){});
                    } else if (doc.webkitExitFullscreen) {
                        doc.webkitExitFullscreen().catch(function(){});
                    }
                }
                if (win.screen && win.screen.orientation && win.screen.orientation.unlock) {
                    win.screen.orientation.unlock();
                }
            } catch(e) {}
        }

        function attachLandscapeHandlers() {
            try {
                var buttons = doc.querySelectorAll('button');
                buttons.forEach(function(btn) {
                    var txt = (btn.innerText || btn.textContent || '').trim();
                    var aria = (btn.getAttribute('aria-label') || '').toLowerCase();

                    if (txt.indexOf('가로 넓게 보기') !== -1 && !btn._landscapeEnterAttached) {
                        btn._landscapeEnterAttached = true;
                        btn.addEventListener('click', function() {
                            try {
                                if (doc.documentElement.requestFullscreen) {
                                    doc.documentElement.requestFullscreen().catch(function(){});
                                } else if (doc.documentElement.webkitRequestFullscreen) {
                                    doc.documentElement.webkitRequestFullscreen().catch(function(){});
                                }
                                if (win.screen && win.screen.orientation && win.screen.orientation.lock) {
                                    win.screen.orientation.lock('landscape').catch(function(){});
                                }
                            } catch(e) {}
                        });
                    }

                    if ((txt.indexOf('닫기') !== -1 || aria === 'close' || aria.indexOf('닫기') !== -1) && !btn._landscapeExitAttached) {
                        btn._landscapeExitAttached = true;
                        btn.addEventListener('click', function() {
                            exitLandscape();
                        });
                    }
                });
            } catch(e) {}
        }

        if (!doc._finscopeLandscapeObs) {
            doc._finscopeLandscapeObs = new MutationObserver(attachLandscapeHandlers);
            if (doc.body) {
                doc._finscopeLandscapeObs.observe(doc.body, { childList: true, subtree: true });
            }
            doc.addEventListener('fullscreenchange', function() {
                if (!doc.fullscreenElement) {
                    exitLandscape();
                }
            });
        }
        attachLandscapeHandlers();
    } catch(err) {}
})();
"""
    js_code = f"<script>{js_raw}</script>"
    st.html(f"<div style='display:none;'>{js_code}</div>", unsafe_allow_javascript=True)
    try:
        import streamlit.components.v1 as components
        components.html(js_code, height=0, width=0)
    except Exception:
        pass


def _format_currency_cb(widget_key: str, market: str):
    raw_text = st.session_state.get(widget_key, "")
    cleaned = re.sub(r"[^\d.]", "", str(raw_text).strip())
    if cleaned:
        try:
            num = float(cleaned)
            if num > 0:
                if market == "KRX":
                    st.session_state[widget_key] = f"{int(num):,}원"
                else:
                    st.session_state[widget_key] = f"${num:,.2f}"
            else:
                st.session_state[widget_key] = ""
        except ValueError:
            st.session_state[widget_key] = ""
    else:
        st.session_state[widget_key] = ""


def render_currency_input(
    label: str,
    value: float | int,
    market: str = "KRX",
    key: str = None,
    help: str = None,
    placeholder: str = None,
) -> float:
    """
    통화(원화/달러) 전용 입력 컴포넌트:
    - 0원인 경우 빈 문자열 + placeholder('0원')로 처리하여 클릭 시 0이 안 보이고 입력 금액만 표시 (0원123123 오입력 원천 차단)
    - 금액 입력 후 엔터/포커스 아웃 시 콤마 서식 유지 ('123,123원')
    - 미입력 시 다시 0원 placeholder 표기
    """
    widget_key = key or f"cur_input_{label}"
    is_krw = (market == "KRX")
    ph = placeholder or ("0원" if is_krw else "$0")

    # 세션 상태가 없으면 초기값 세팅 (0보다 클 때만 서식화된 문자열, 0이면 빈 문자열)
    if widget_key not in st.session_state:
        raw_val = float(value or 0)
        if raw_val > 0:
            st.session_state[widget_key] = f"{int(raw_val):,}원" if is_krw else f"${raw_val:,.2f}"
        else:
            st.session_state[widget_key] = ""

    user_text = st.text_input(
        label,
        key=widget_key,
        help=help,
        placeholder=ph,
        on_change=_format_currency_cb,
        args=(widget_key, market)
    )

    cleaned = re.sub(r"[^\d.]", "", str(user_text).strip())
    try:
        parsed_num = float(cleaned) if cleaned else 0.0
    except ValueError:
        parsed_num = 0.0

    return parsed_num


SUMMARY_TABS = ["💼 자산 종합 현황", "🎯 핵심 요약 및 추천가 분석"]
# URL 파라미터 및 세션 상태를 연계하여 최신 탭 선택 결정 (지연 덮어쓰기 방어)
qp_tab = str(st.query_params.get("tab", "")).strip().lower()
if qp_tab == "recom":
    active_tab_default = SUMMARY_TABS[1]
elif qp_tab == "summary":
    active_tab_default = SUMMARY_TABS[0]
elif "portfolio_summary_tabs" in st.session_state and st.session_state.portfolio_summary_tabs in SUMMARY_TABS:
    active_tab_default = st.session_state.portfolio_summary_tabs
elif "portfolio_active_tab" in st.session_state and st.session_state.portfolio_active_tab in SUMMARY_TABS:
    active_tab_default = st.session_state.portfolio_active_tab
else:
    active_tab_default = SUMMARY_TABS[0]

st.session_state.portfolio_active_tab = active_tab_default
st.session_state.portfolio_summary_tabs = active_tab_default

tab_summary, tab_recom = st.tabs(
    SUMMARY_TABS,
    default=active_tab_default,
    key="portfolio_summary_tabs"
)

with tab_summary:
    profit_val = summary["total_profit"]
    profit_rate = summary["total_profit_rate"]
    color_class = "text-profit" if profit_val > 0 else ("text-loss" if profit_val < 0 else "")
    sign_str = "+" if profit_val > 0 else ""

    p_head1, p_head2 = st.columns([2.5, 1.5])
    with p_head1:
        st.markdown('<h4 style="word-break: keep-all; letter-spacing: -0.5px; margin-bottom: 0.25rem;">💼 자산 종합 현황 (실시간 환율 반영)</h4>', unsafe_allow_html=True)
    with p_head2:
        p_view_mode = st.selectbox(
            "포트폴리오 요약 스타일",
            options=["자동 (기기 최적화)", "1줄 목록형", "4열 카드형"],
            index=0,
            label_visibility="collapsed",
            key="portfolio_summary_view_mode",
            help="📱 모바일 1줄 가로형 바 또는 🖥️ PC 4열 카드형을 수동으로 선택할 수 있습니다."
        )

    p_container_class = "metric-container"
    if p_view_mode == "1줄 목록형":
        p_container_class += " force-list-mode"
    elif p_view_mode == "4열 카드형":
        p_container_class += " force-card-mode"

    # 1. 상단 3개 핵심 자산 평가 메트릭 (투자원금, 평가금액, 평가손익)
    st.markdown(
        f'<div class="{p_container_class}" style="margin-bottom: 0.5rem;">'
        f'<div class="metric-box">'
        f'<div class="metric-left">'
        f'<div class="metric-title">💰 총 투자원금 (원화 환산)</div>'
        f'<div class="metric-subtitle">보유 {summary["item_count"]}건 (환율: {usd_rate:,.1f}원/$)</div>'
        f'</div>'
        f'<div class="metric-right">'
        f'<div class="metric-value">{summary["total_invested"]:,.0f} <span style="font-size: 0.75rem; color: #94A3B8;">원</span></div>'
        f'</div>'
        f'</div>'
        f'<div class="metric-box">'
        f'<div class="metric-left">'
        f'<div class="metric-title">📈 총 평가금액 (원화 환산)</div>'
        f'<div class="metric-subtitle">실시간 환산</div>'
        f'</div>'
        f'<div class="metric-right">'
        f'<div class="metric-value">{summary["total_eval"]:,.0f} <span style="font-size: 0.75rem; color: #94A3B8;">원</span></div>'
        f'</div>'
        f'</div>'
        f'<div class="metric-box">'
        f'<div class="metric-left">'
        f'<div class="metric-title">📊 총 평가손익 (원화 환산)</div>'
        f'<div class="metric-subtitle {color_class}" style="font-weight: 600;">수익률 {sign_str}{profit_rate:.2f}%</div>'
        f'</div>'
        f'<div class="metric-right">'
        f'<div class="metric-value {color_class}">{sign_str}{profit_val:,.0f} <span style="font-size: 0.75rem;">원</span></div>'
        f'<div class="metric-change {color_class}" style="font-weight: 600;">{sign_str}{profit_rate:.2f}%</div>'
        f'</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    # 2. 손절 경고 알림: 따로 1줄로 아래쪽에 넓고 시원하게 표시
    sl_count = summary["stop_loss_count"]
    is_danger = sl_count > 0
    bar_class = "danger" if is_danger else "safe"
    badge_html = (
        '<span class="badge-stop-loss">🚨 즉시 확인 요망</span>'
        if is_danger else
        '<span class="badge-tag" style="background: rgba(16, 185, 129, 0.2); color: #34D399; border: 1px solid #10B981;">안전 구간</span>'
    )
    status_val_html = (
        f'<b style="font-size: 1.1rem; color: #EF4444;">{sl_count}건</b> <span style="font-size: 0.8rem; color: #FCA5A5;">도달</span>'
        if is_danger else
        f'<b style="font-size: 1.1rem; color: #10B981;">0건</b> <span style="font-size: 0.8rem; color: #94A3B8;">(정상)</span>'
    )

    st.markdown(
        f'<div class="stop-loss-bar {bar_class}">'
        f'<div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">'
        f'<span style="font-size: 1.15rem;">{"🚨" if is_danger else "🛡️"}</span>'
        f'<b style="color: #F8FAFC; font-size: 0.95rem;">손절 경고 알림</b>'
        f'{badge_html}'
        f'</div>'
        f'<div style="display: flex; align-items: baseline; gap: 4px;">'
        f'{status_val_html}'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    # 🚨 손절가 도달 경고 배너
    if summary["stop_loss_count"] > 0:
        st.error(f"🚨 **손절 경고 알림**: 설정한 손절가 이하로 하락한 종목이 **{summary['stop_loss_count']}건** 존재합니다. 아래 테이블에서 강조된 종목을 확인하세요!", icon="⚠️")

with tab_recom:
    st.markdown('<h4 style="word-break: keep-all; letter-spacing: -0.5px; margin-bottom: 0.25rem;">🎯 보유 종목 핵심 요약 및 매수/매도 추천가 분석</h4>', unsafe_allow_html=True)
    st.caption("현재 시장가 기준 단기 지지선(눌림목 -4%) 및 목표가/저항선(+8%)을 분석하여 분할 매매 기준가를 실시간 제안합니다.")

    if perf_df.empty:
        st.info("💡 등록된 보유 종목이 없습니다. 아래의 **[신규 보유 종목 등록]** 메뉴를 열어 종목을 추가해보세요!")
    else:
        # 보유 종목 관련 최신 뉴스/공시 수집 (10분 캐시)
        recom_tickers = [str(r["ticker"]).strip().upper() for _, r in perf_df.iterrows() if r.get("ticker")]
        recom_news = fetch_stock_news(recom_tickers) if recom_tickers else []

        def _format_compact_amount(val: float, market: str) -> str:
            """모바일용 축약 금액 표기 (예: 414만원, 1.2억원, $1.2k)"""
            abs_v = abs(val)
            if market == "KRX":
                if abs_v >= 100_000_000:
                    return f"{val / 100_000_000:,.1f}억원"
                elif abs_v >= 10_000:
                    if abs_v % 10_000 == 0 or abs_v >= 1_000_000:
                        return f"{val / 10_000:,.0f}만원"
                    else:
                        return f"{val / 10_000:,.1f}만원"
                else:
                    return f"{val:,.0f}원"
            else:
                if abs_v >= 1_000_000:
                    return f"${val / 1_000_000:,.1f}M"
                elif abs_v >= 1_000:
                    return f"${val / 1_000:,.1f}k"
                else:
                    return f"${val:,.2f}"

        recom_rows = []
        for _, r in perf_df.iterrows():
            rec = calculate_target_recommendations(r)
            ai_info = generate_ai_comment(r, recom_news)
            m_sign = "+" if r["eval_profit"] > 0 else ""
            p_color = "#EF4444" if r["eval_profit"] > 0 else ("#3B82F6" if r["eval_profit"] < 0 else "#94A3B8")

            is_us = (r["market"] == "US")
            curr_p = float(r["current_price"])
            buy_p = float(r["buy_price"])
            eval_p = float(r["eval_amount"])
            profit_p = float(r["eval_profit"])

            if not is_us:
                # 🇰🇷 국내 주식 (KRX): 순수 원화 표기 유지
                curr_str = f"{curr_p:,.0f}원"
                curr_krw_html = ""
                buy_str = f"{buy_p:,.0f}원"
                eval_str = f"{eval_p:,.0f}원"
                eval_sub_pc = f"평단 {buy_str} · {r['quantity_display']} ({eval_str})"
                eval_sub_mobile = f"평단: {buy_str} ({r['quantity_display']} · {_format_compact_amount(eval_p, 'KRX')})"
                profit_str = f"{m_sign}{profit_p:,.0f}원"
                profit_krw_html = ""
                target_str = f"{float(r['target_price']):,.0f}원" if is_valid_price(r.get("target_price")) else ""
                stop_str = f"{float(r['stop_loss_price']):,.0f}원" if is_valid_price(r.get("stop_loss_price")) else ""
                buy_krw_html = ""
                sell_krw_html = ""
            else:
                # 🇺🇸 미국 주식 (US): 달러($) + 실시간 환율 기준 원화(₩) 환산 병기
                curr_str = f"${curr_p:,.2f}"
                curr_krw_disp = format_won_compact(curr_p * usd_rate, prefix_approx=True)
                curr_krw_html = f'<span class="price-curr-krw" style="font-size: 0.85rem; color: #94A3B8; font-weight: 500; margin-left: 6px; white-space: nowrap !important; display: inline-block;">({curr_krw_disp})</span>'
                buy_str = f"${buy_p:,.2f}"
                eval_str = f"${eval_p:,.2f}"
                eval_won_val = float(r.get("eval_amount_won", eval_p * usd_rate))
                eval_won_disp = format_won_compact(eval_won_val, prefix_approx=True)
                eval_sub_pc = f"평단 {buy_str} · {r['quantity_display']} ({eval_str} · <span style=\"color: #94A3B8; white-space: nowrap !important;\">{eval_won_disp}</span>)"
                eval_sub_mobile = f"평단: {buy_str} ({r['quantity_display']} · {_format_compact_amount(eval_p, 'US')} · <span style=\"color: #94A3B8; white-space: nowrap !important;\">{eval_won_disp}</span>)"

                profit_str = f"{m_sign}${profit_p:,.2f}"
                profit_won_val = float(r.get("eval_profit_won", profit_p * usd_rate))
                sign_won = "+" if profit_won_val > 0 else ("-" if profit_won_val < 0 else "")
                profit_won_str = f"(약 {sign_won}{abs(profit_won_val):,.0f}원)"
                profit_krw_html = f'<span class="profit-won-val" style="color: #94A3B8; font-size: 0.76rem; margin-top: 1px; white-space: nowrap !important; display: inline-block;">{profit_won_str}</span>'

                if is_valid_price(r.get("target_price")):
                    t_val = float(r["target_price"])
                    t_disp = f"${t_val:,.0f}" if t_val == int(t_val) else f"${t_val:,.2f}"
                    t_krw = format_won_compact(t_val * usd_rate)
                    target_str = f"{t_disp} ({t_krw})"
                else:
                    target_str = ""

                if is_valid_price(r.get("stop_loss_price")):
                    s_val = float(r["stop_loss_price"])
                    s_disp = f"${s_val:,.0f}" if s_val == int(s_val) else f"${s_val:,.2f}"
                    s_krw = format_won_compact(s_val * usd_rate)
                    stop_str = f"{s_disp} ({s_krw})"
                else:
                    stop_str = ""

                recom_buy_krw = format_won_compact(rec["recom_buy_price"] * usd_rate, prefix_approx=True)
                recom_sell_krw = format_won_compact(rec["recom_sell_price"] * usd_rate, prefix_approx=True)
                buy_krw_html = f'<span class="recom-krw" style="font-size: 0.78rem; color: #94A3B8; font-weight: normal; margin-left: 3px; white-space: nowrap !important; display: inline-block;">({recom_buy_krw})</span>'
                sell_krw_html = f'<span class="recom-krw" style="font-size: 0.78rem; color: #94A3B8; font-weight: normal; margin-left: 3px; white-space: nowrap !important; display: inline-block;">({recom_sell_krw})</span>'

            rate_str = f"▲ +{r['profit_rate']:.2f}%" if r["eval_profit"] > 0 else (f"▼ {r['profit_rate']:.2f}%" if r["eval_profit"] < 0 else "0.00%")

            # 사용자 설정 기준가 (목표가/손절가) 태그 구성
            criteria_tags = []
            if target_str:
                criteria_tags.append(f'<span class="mini-tag target" title="설정 목표가">🎯 <span class="tag-label-pc pc-only">목표 </span>{target_str}</span>')
            if stop_str:
                criteria_tags.append(f'<span class="mini-tag stop" title="설정 손절가">🚨 <span class="tag-label-pc pc-only">손절 </span>{stop_str}</span>')

            if criteria_tags:
                divider_html = '<span class="criteria-divider">|</span>'
                criteria_html = f'<div class="price-criteria-line">{divider_html.join(criteria_tags)}</div>'
            else:
                criteria_html = ''

            row_html = (
                f'<tr class="recom-row">'
                f'<td class="td-stock">'
                f'<div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">'
                f'<span class="market-account-chip">{r["market"]} · {r.get("account", "기본")}</span>'
                f'<b style="font-size: 1rem; color: #F8FAFC; word-break: keep-all;">{r["name"]}</b>'
                f'</div>'
                f'<div style="font-size: 0.8rem; color: #94A3B8; margin-top: 3px;">{r["ticker"]}</div>'
                f'</td>'
                f'<td class="td-price">'
                f'<div class="price-container">'
                f'<div class="price-curr-line">'
                f'<span class="price-curr-label pc-only">현재가: </span>'
                f'<b class="price-curr-val" style="white-space: nowrap;">{curr_str}</b>'
                f'{curr_krw_html}'
                f'</div>'
                f'<div class="price-sub-line">'
                f'<span class="price-sub-text pc-only">{eval_sub_pc}</span>'
                f'<span class="price-sub-text mobile-only">{eval_sub_mobile}</span>'
                f'</div>'
                f'{criteria_html}'
                f'</div>'
                f'</td>'
                f'<td class="td-profit">'
                f'<div class="profit-badge">'
                f'<span class="profit-rate-val" style="color: {p_color};">{rate_str}</span>'
                f'<span class="profit-amount-val" style="color: {p_color};">{profit_str}</span>'
                f'{profit_krw_html}'
                f'</div>'
                f'</td>'
                f'<td class="td-guide">'
                f'<div class="recom-guide-box">'
                f'<div class="recom-buy-row">'
                f'<span class="recom-badge buy">🟢 추가 매수</span>'
                f'<b class="recom-price buy">{rec["recom_buy_display"]}</b>'
                f'{buy_krw_html}'
                f'<span class="recom-desc">({rec["buy_reason"]})</span>'
                f'</div>'
                f'<div class="recom-sell-row">'
                f'<span class="recom-badge sell">🔴 분할 매도</span>'
                f'<b class="recom-price sell">{rec["recom_sell_display"]}</b>'
                f'{sell_krw_html}'
                f'<span class="recom-desc">({rec["sell_reason"]})</span>'
                f'</div>'
                f'</div>'
                f'<div class="ai-comment-box">'
                f'<div class="ai-comment-header">'
                f'<span class="ai-badge {ai_info["badge_type"]}">{ai_info["badge"]}</span>'
                f'<span style="font-size: 0.75rem; color: #94A3B8; font-weight: 600;">🤖 AI 진단 한줄평</span>'
                f'</div>'
                f'<div class="ai-comment-text">{ai_info["comment"]}</div>'
                f'</div>'
                f'</td>'
                f'</tr>'
            )
            recom_rows.append(row_html)

        table_html = (
            f'<div class="recom-table-container">'
            f'<table class="recom-table">'
            f'<thead>'
            f'<tr>'
            f'<th style="width: 20%;">종목 정보</th>'
            f'<th style="width: 26%;">가격 현황</th>'
            f'<th style="width: 16%;">손익 상태</th>'
            f'<th style="width: 38%;">전략 추천 가이드 & AI 한줄평</th>'
            f'</tr>'
            f'</thead>'
            f'<tbody>'
            f'{"".join(recom_rows)}'
            f'</tbody>'
            f'</table>'
            f'</div>'
        )
        st.markdown(table_html, unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# 8. 보유 종목 등록 (종목명 자동 불러오기 & 미저장 초기화 알림창 지원)
# ------------------------------------------------------------------------------
def has_unsaved_registration_inputs(new_ticker: str = "") -> bool:
    """
    신규 등록 폼에 사용자가 작성 중인 미저장 데이터가 존재하는지 검사:
    - 목표가(reg_in_target_price)에 0이 아닌 유효 금액이 입력되어 있는 경우
    - 손절가(reg_in_stop_loss)에 0이 아닌 유효 금액이 입력되어 있는 경우
    - 수량(reg_in_quantity)이 기본값 1.0과 다른 경우 (사용자가 수량을 수정한 경우)
    - 투자 메모(reg_in_memo)가 작성되어 있는 경우
    - 이전에 다른 종목이 이미 로드되어 있거나 매수가가 입력되어 있는 상태에서 다른 종목을 불러오는 경우
    """
    target_clean = re.sub(r"[^\d.]", "", str(st.session_state.get("reg_in_target_price", "")))
    if target_clean and float(target_clean) > 0:
        return True

    stop_clean = re.sub(r"[^\d.]", "", str(st.session_state.get("reg_in_stop_loss", "")))
    if stop_clean and float(stop_clean) > 0:
        return True

    qty_val = float(st.session_state.get("reg_in_quantity", 1.0) or 1.0)
    if abs(qty_val - 1.0) > 1e-4:
        return True

    memo_val = str(st.session_state.get("reg_in_memo", "")).strip()
    if memo_val:
        return True

    curr_ticker = str(st.session_state.get("reg_ticker", "")).strip().upper()
    new_t = str(new_ticker).strip().upper()
    if curr_ticker and new_t and curr_ticker != new_t:
        return True

    buy_clean = re.sub(r"[^\d.]", "", str(st.session_state.get("reg_in_buy_price", "")))
    if buy_clean and float(buy_clean) > 0 and curr_ticker and new_t and curr_ticker != new_t:
        return True

    return False


def _do_apply_new_stock_and_reset_form(found: dict, market: str, reset_msg: bool = True):
    """새 종목 정보를 반영하고 이전 미저장 입력 항목(수량, 목표가, 손절가, 메모 등)을 깨끗하게 초기화하며 현재가를 매수가에 자동 세팅"""
    st.session_state.reg_ticker = found.get("ticker", "")
    st.session_state.reg_name = found.get("name", "")

    actual_market = found.get("market") or market
    if actual_market in ["KRX", "US"]:
        try:
            st.session_state["reg_market_select"] = actual_market
        except Exception:
            pass

    cp = float(found.get("current_price") or found.get("price") or 0.0)
    st.session_state.reg_buy_price = cp
    if cp > 0:
        st.session_state["reg_in_buy_price"] = f"{int(cp):,}원" if actual_market == "KRX" else f"${cp:,.2f}"
    else:
        st.session_state["reg_in_buy_price"] = ""

    # 미저장 필드 초기화
    st.session_state["reg_in_target_price"] = ""
    st.session_state["reg_in_stop_loss"] = ""
    st.session_state["reg_in_quantity"] = 1.0
    st.session_state["reg_in_memo"] = ""
    st.session_state["reg_account_choice"] = "토스증권"
    st.session_state["reg_custom_account"] = ""

    if found.get("ticker"):
        price_disp = f"{int(cp):,}원" if actual_market == "KRX" else f"${cp:,.2f}" if cp > 0 else ""
        price_tag = f" (현재가 {price_disp} 매수가 자동 세팅)" if price_disp else ""
        if reset_msg:
            st.session_state.reg_lookup_msg = (
                "success",
                f"✅ '{found['name']} ({found['ticker']})' 정보를 성공적으로 불러왔습니다.{price_tag} (이전 입력 정보 초기화 완료)"
            )
        else:
            st.session_state.reg_lookup_msg = (
                "success",
                f"✅ '{found['name']} ({found['ticker']})' 정보를 성공적으로 불러왔습니다.{price_tag}"
            )
    st.session_state.add_expander_expanded = True


def apply_new_stock_and_reset_form(found: dict, market: str, reset_msg: bool = True):
    """
    새 종목 정보 반영 및 폼 초기화 (지연 주입을 통해 StreamlitWidgetAlreadyInstantiatedError 완벽 방지)
    """
    actual_market = found.get("market") or market
    st.session_state.pending_reg_stock = {
        "found": found,
        "market": actual_market,
        "reset_msg": reset_msg,
    }
    # 위젯 렌더링 전인 안전한 컨텍스트(테스트 환경 등)에서는 즉시 반영도 시도
    try:
        _do_apply_new_stock_and_reset_form(found, actual_market, reset_msg)
    except Exception:
        # 이미 위젯이 인스턴스화된 경우(버튼 클릭 처리부 등)에는 rerun 시 위젯 생성 전 최상단에서 안전하게 적용됨
        pass


@st.dialog("⚠️ 기존 입력 정보 초기화 확인", width="small")
def confirm_stock_reload_dialog(found_stock: dict, market: str):
    st.markdown(
        f"""
        <div style="background: rgba(239, 68, 68, 0.08); border-left: 4px solid #EF4444; padding: 12px 14px; border-radius: 6px; margin-bottom: 14px;">
            <p style="margin: 0 0 6px 0; font-weight: 700; color: #F87171; font-size: 0.95rem;">
                ⚠️ 저장하지 않은 입력 정보가 있습니다.
            </p>
            <p style="margin: 0; font-size: 0.9rem; color: #CBD5E1; line-height: 1.5;">
                현재 작성 중인 매수가, 보유 수량, 목표가, 손절가, 메모 등의 정보가 아직 등록되지 않았습니다.<br>
                새 종목 <b>[{found_stock['name']} ({found_stock['ticker']})]</b>을(를) 불러오면 <b>기존 입력 정보는 모두 초기화</b>됩니다.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.write("새 종목을 불러오고 기존 입력값을 초기화하시겠습니까?")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔄 초기화하고 불러오기", type="primary", use_container_width=True, key="dlg_btn_confirm_reload"):
            actual_m = found_stock.get("market") or market
            apply_new_stock_and_reset_form(found_stock, actual_m, reset_msg=True)
            st.rerun()
    with c2:
        if st.button("❌ 취소 (기존 입력 유지)", type="secondary", use_container_width=True, key="dlg_btn_cancel_reload"):
            st.rerun()


# 지연 주입된 신규 종목 정보 또는 폼 초기화 데이터가 있으면 위젯 인스턴스화 전에 안전하게 반영
if st.session_state.get("pending_reg_stock"):
    p_data = st.session_state.pop("pending_reg_stock")
    _do_apply_new_stock_and_reset_form(p_data["found"], p_data["market"], p_data.get("reset_msg", False))


with st.expander("➕ 신규 보유 종목 등록", expanded=bool(st.session_state.add_expander_expanded)):

    st.caption("💡 **종목코드 또는 종목명**을 입력하고 **[🔍 종목명 자동 불러오기]**를 누르면 종목명과 현재가(장종료 시 종가)가 매수가에 자동으로 입력됩니다.")

    # A. 종목 자동 검색 & 불러오기 바
    srch_c1, srch_c2, srch_c3 = st.columns([1, 2, 1.2])
    with srch_c1:
        in_market = st.selectbox(
            "시장 구분",
            options=["KRX", "US"],
            format_func=lambda x: "🇰🇷 국내(KRX)" if x == "KRX" else "🇺🇸 미국(US)",
            key="reg_market_select"
        )
    with srch_c2:
        query_input = st.text_input(
            "종목코드 또는 종목명 검색*",
            value=st.session_state.reg_ticker,
            placeholder="예: 005930, 삼성전자, AAPL, 테슬라 등",
            help="종목코드(티커)나 종목명을 입력하고 우측 버튼을 누르세요."
        )
    with srch_c3:
        st.write("")
        st.write("")
        if st.button("🔍 종목명 자동 불러오기", use_container_width=True, type="secondary"):
            if query_input.strip():
                st.session_state.add_expander_expanded = True
                found = search_stock_by_ticker_or_name(query_input.strip(), market=in_market)
                if found:
                    actual_market = found.get("market") or in_market
                    if has_unsaved_registration_inputs(found["ticker"]):
                        confirm_stock_reload_dialog(found, actual_market)
                    else:
                        apply_new_stock_and_reset_form(found, actual_market, reset_msg=False)
                        st.rerun()
                else:
                    st.session_state.reg_lookup_msg = ("warning", f"⚠️ '{query_input}'에 대한 정보를 찾지 못했습니다. 종목명을 직접 입력해주세요.")
                    st.rerun()

    # 검색 결과 알림 배너
    if st.session_state.reg_lookup_msg:
        msg_type, msg_text = st.session_state.reg_lookup_msg
        if msg_type == "success":
            st.success(msg_text)
        elif msg_type == "info":
            st.info(msg_text)
        else:
            st.warning(msg_text)
        st.session_state.reg_lookup_msg = None

    st.markdown("---")

    # B. 상세 종목 정보 입력 (통화별 서식 및 정수/실수 타입 일치)
    if in_market == "KRX":
        cur_unit = "원"
        price_step = 1000
        price_fmt = "%d"
        p_min = 0
        reg_buy_val = int(st.session_state.reg_buy_price)
    else:
        cur_unit = "$"
        price_step = 1.0
        price_fmt = "%.2f"
        p_min = 0.0
        reg_buy_val = float(st.session_state.reg_buy_price)

    # 사용자 등록 계좌 목록 연동
    form_accounts = repo.get_accounts(user_id)
    form_acc_options = {format_acc_label(a): a for a in form_accounts}
    acc_choice_list = list(form_acc_options.keys()) + ["직접 입력"]

    f_c1, f_c2, f_c3 = st.columns([1, 1, 1.4])
    with f_c1:
        final_ticker = st.text_input("티커 / 종목코드*", value=st.session_state.reg_ticker, placeholder="예: 005930 또는 AAPL")
    with f_c2:
        final_name = st.text_input("종목명*", value=st.session_state.reg_name, placeholder="예: 삼성전자 또는 Apple")
    with f_c3:
        with st.container(key="reg_account_field_container"):
            st.markdown("""
                <div class="account-filter-label-row">
                    <span class="account-filter-label-text">📁 계좌 / 금융앱 구분*</span>
                    <span class="account-inline-tooltip" tabindex="0" role="button" aria-label="계좌 구분 도움말">
                        <span class="tooltip-icon">ℹ️</span>
                        <span class="tooltip-bubble">등록된 증권사/금융앱 계좌를 지정하거나 ➕ 버튼을 눌러 계좌를 관리할 수 있습니다.</span>
                    </span>
                </div>
            """, unsafe_allow_html=True)
            acc_s_c1, acc_s_c2 = st.columns([4.2, 0.8], vertical_alignment="center")
            with acc_s_c1:
                reg_acc_choice = st.selectbox(
                    "📁 계좌 / 금융앱 구분*",
                    options=acc_choice_list,
                    index=0,
                    key="reg_account_choice",
                    label_visibility="collapsed"
                )
            with acc_s_c2:
                if st.button("➕", key="reg_btn_manage_acc", use_container_width=True, help="➕ 계좌 관리: 계좌 추가/수정/삭제 및 ISA 만기 관리"):
                    manage_accounts_dialog(user_id, repo)

    if reg_acc_choice == "직접 입력":
        final_account = st.text_input("계좌명 직접 입력*", value="", placeholder="예: NH투자증권, 퇴직연금DC 등", key="reg_custom_account")
        final_account_id = None
    else:
        chosen_acc_obj = form_acc_options.get(reg_acc_choice)
        if chosen_acc_obj:
            final_account = chosen_acc_obj.get("broker_name", "기본")
            final_account_id = chosen_acc_obj.get("id")
        else:
            final_account = reg_acc_choice
            final_account_id = None

    f_c4, f_c5, f_c6 = st.columns(3)
    with f_c4:
        in_buy_price = render_currency_input(
            f"매수가 ({cur_unit})*",
            value=reg_buy_val,
            market=in_market,
            key="reg_in_buy_price",
            help=f"{cur_unit} 단위로 입력합니다."
        )
    with f_c5:
        in_quantity = st.number_input(
            "보유 수량*",
            min_value=0.0001,
            step=1.0,
            value=float(st.session_state.get("reg_in_quantity", 1.0)),
            format="%g",
            placeholder="1",
            key="reg_in_quantity"
        )
    with f_c6:
        in_target_price = render_currency_input(
            f"목표가 ({cur_unit})",
            value=0 if in_market == "KRX" else 0.0,
            market=in_market,
            key="reg_in_target_price",
            help=f"{cur_unit} 단위 (0이면 미설정)"
        )

    f_c7, f_c8 = st.columns([1, 2])
    with f_c7:
        in_stop_loss = render_currency_input(
            f"손절가 ({cur_unit})",
            value=0 if in_market == "KRX" else 0.0,
            market=in_market,
            key="reg_in_stop_loss",
            help="현재가가 이 금액 이하로 하락 시 경고 배지가 표시됩니다. (0이면 미설정 🚨)"
        )
    with f_c8:
        in_memo = st.text_input(
            "투자 메모 (선택)",
            value=st.session_state.get("reg_in_memo", ""),
            placeholder="예: 장기 적립식, 배당 포트폴리오",
            key="reg_in_memo"
        )

    btn_add_c1, btn_add_c2 = st.columns([3, 1])
    with btn_add_c1:
        submit_add = st.button("💾 포트폴리오에 종목 추가", type="primary", use_container_width=True)
    with btn_add_c2:
        if st.button("🔄 입력 초기화", type="secondary", use_container_width=True, help="작성 중인 모든 입력 항목을 비웁니다."):
            apply_new_stock_and_reset_form({"ticker": "", "name": "", "current_price": 0}, in_market, reset_msg=False)
            st.session_state.reg_lookup_msg = ("info", "ℹ️ 작성 중인 입력 정보가 초기화되었습니다.")
            st.rerun()

    if submit_add:
        if not final_ticker or not final_name:
            st.error("티커와 종목명은 필수 입력 항목입니다.")
        elif in_buy_price <= 0 or in_quantity <= 0:
            st.error("매수가와 수량은 0보다 커야 합니다.")
        else:
            new_item_data = {
                "market": in_market,
                "ticker": final_ticker.strip().upper(),
                "name": final_name.strip(),
                "account": final_account.strip() or "기본",
                "account_id": final_account_id,
                "buy_price": float(in_buy_price),
                "quantity": float(in_quantity),
                "target_price": float(in_target_price) if in_target_price > 0 else None,
                "stop_loss_price": float(in_stop_loss) if in_stop_loss > 0 else None,
                "memo": in_memo.strip() or None
            }

            add_ok, add_msg = repo.add_item(user_id, new_item_data)
            if add_ok:
                apply_new_stock_and_reset_form({"ticker": "", "name": "", "current_price": 0}, in_market, reset_msg=False)
                st.session_state.reg_lookup_msg = None
                st.session_state.selected_account_filter = "전체 계좌 보기"
                st.session_state.add_expander_expanded = False
                st.session_state.pending_toast = (f"✅ [{final_name}] 종목이 성공적으로 등록되었습니다!", "🎉")
                st.session_state.scroll_to_top = True
                st.rerun()
            else:
                st.session_state.add_expander_expanded = True
                st.error(add_msg)


# ------------------------------------------------------------------------------
# 8-1. 초슬림 퀵 에디터 가로 넓게 보기 모달 (@st.dialog)
# ------------------------------------------------------------------------------
@st.dialog("📱 초슬림 퀵 에디터 (가로 전체화면 모드)", width="large")
def landscape_quick_editor_dialog(items, perf_df, repo, user_id):
    st.caption("💡 가로로 넓게 보며 **계좌, 매수가, 수량, 목표가, 손절가, 메모**를 일괄 수정 후 저장합니다.")

    dlg_rows = []
    for _, r in perf_df.iterrows():
        dlg_rows.append({
            "_id": r["id"],
            "계좌": str(r.get("account") or "기본"),
            "시장": "🇰🇷 KRX" if r["market"] == "KRX" else "🇺🇸 US",
            "종목명": r["name"],
            "매수가": float(r["buy_price"]),
            "보유 수량": float(r["quantity"]),
            "목표가": float(r["target_price"]) if is_valid_price(r.get("target_price")) else 0.0,
            "손절가": float(r["stop_loss_price"]) if is_valid_price(r.get("stop_loss_price")) else 0.0,
            "메모": str(r.get("memo") or "")
        })

    dlg_df = pd.DataFrame(dlg_rows)
    dlg_col_config = {
        "_id": None,
        "계좌": st.column_config.TextColumn("계좌 / 앱", width="small", max_chars=30),
        "시장": st.column_config.TextColumn("시장", width="small", disabled=True),
        "종목명": st.column_config.TextColumn("종목명", width="medium", disabled=True),
        "매수가": st.column_config.NumberColumn("매수가", min_value=0.0, step=1.0, required=True),
        "보유 수량": st.column_config.NumberColumn("보유 수량", min_value=0.0001, step=1.0, format="%g", required=True),
        "목표가": st.column_config.NumberColumn("목표가 (0이면 해제)", min_value=0.0, step=1.0),
        "손절가": st.column_config.NumberColumn("손절가 (0이면 해제)", min_value=0.0, step=1.0),
        "메모": st.column_config.TextColumn("메모", width="large", max_chars=100)
    }

    edited_dlg = st.data_editor(
        dlg_df,
        column_config=dlg_col_config,
        disabled=["시장", "종목명"],
        use_container_width=True,
        hide_index=True,
        height=min(450, max(280, len(dlg_rows) * 38 + 60)),
        key="dlg_slim_portfolio_editor"
    )

    d_col1, d_col2 = st.columns([2.5, 1.2], vertical_alignment="center")
    with d_col1:
        save_dlg_btn = st.button("💾 테이블 변경사항 일괄 저장", type="primary", use_container_width=True, key="dlg_save_slim_editor_btn")
    with d_col2:
        close_dlg_btn = st.button("❌ 닫기", type="secondary", use_container_width=True, key="dlg_close_landscape_btn")
        if close_dlg_btn:
            st.rerun()

    if save_dlg_btn:
        updated_count = 0
        for _, row in edited_dlg.iterrows():
            item_id = row["_id"]
            orig_item = next((it for it in items if it.get("id") == item_id), None)
            if not orig_item:
                continue

            new_acc = str(row.get("계좌") or "기본").strip() or "기본"
            new_buy = float(row["매수가"])
            new_qty = float(row["보유 수량"])
            new_target = float(row["목표가"]) if float(row["목표가"]) > 0 else None
            new_stop = float(row["손절가"]) if float(row["손절가"]) > 0 else None
            new_memo = str(row["메모"]).strip() or None

            orig_acc = str(orig_item.get("account") or "기본").strip() or "기본"
            orig_buy = float(orig_item.get("buy_price", 0))
            orig_qty = float(orig_item.get("quantity", 0))
            orig_target = float(orig_item["target_price"]) if is_valid_price(orig_item.get("target_price")) else None
            orig_stop = float(orig_item["stop_loss_price"]) if is_valid_price(orig_item.get("stop_loss_price")) else None
            orig_memo = str(orig_item.get("memo") or "").strip() or None

            if (
                new_acc != orig_acc or
                abs(new_buy - orig_buy) > 1e-4 or
                abs(new_qty - orig_qty) > 1e-4 or
                new_target != orig_target or
                new_stop != orig_stop or
                new_memo != orig_memo
            ):
                up_data = {
                    "account": new_acc,
                    "buy_price": new_buy,
                    "quantity": new_qty,
                    "target_price": new_target,
                    "stop_loss_price": new_stop,
                    "memo": new_memo
                }
                ok, _ = repo.update_item(item_id, up_data)
                if ok:
                    updated_count += 1

        if updated_count > 0:
            st.session_state.pending_toast = (f"💾 {updated_count}건의 종목 정보가 수정되었습니다.", "✨")
            st.session_state.scroll_to_top = True
            st.rerun()
        else:
            st.info("수정된 변경사항이 없습니다.")


# ------------------------------------------------------------------------------
# 9. 접이식 포트폴리오 종목 편집 및 관리 (간편 폼 & 초슬림 퀵 에디터)
# ------------------------------------------------------------------------------
with st.expander("⚙️ 포트폴리오 종목 편집 및 관리", expanded=False):
    st.caption("💡 보유 종목의 매수가, 수량, 목표가, 손절가를 직접 수정하거나 추가 매수·매도 거래를 시뮬레이션하여 반영할 수 있습니다.")

    if perf_df.empty:
        st.info("💡 등록된 보유 종목이 없습니다. 상단의 **[➕ 신규 보유 종목 등록]** 메뉴를 열어 종목을 추가해보세요!")
    else:
        tab_form_edit, tab_table_edit = st.tabs(["📱 간편 종목 수정 & 거래 폼", "📑 초슬림 퀵 에디터"])

        # ----------------------------------------------------------------------
        # 탭 1: 모바일 및 터치 친화적 [간편 종목 수정 & 거래 폼]
        # ----------------------------------------------------------------------
        with tab_form_edit:
            stock_options = {}
            for _, r in perf_df.iterrows():
                m_sign = "+" if r["eval_profit"] > 0 else ""
                cur_p_str = f"{r['current_price']:,.0f}원" if r["market"] == "KRX" else f"${r['current_price']:,.2f}"
                buy_p_str = f"{r['buy_price']:,.0f}" if r["market"] == "KRX" else f"{r['buy_price']:,.2f}"
                cur_krw_extra = f" (약 {format_won_compact(r['current_price'] * usd_rate)})" if r["market"] == "US" else ""
                stock_label = (
                    f"[{r['market']} · {r.get('account', '기본')}] {r['name']} ({r['ticker']}) · "
                    f"보유 {r['quantity_display']} @ {buy_p_str}{r['currency']} "
                    f"(현재 {cur_p_str}{cur_krw_extra}, {m_sign}{r['profit_rate']:.2f}%)"
                )
                stock_options[stock_label] = r["id"]

            sel_label = st.selectbox("수정 또는 거래할 종목 선택*", options=list(stock_options.keys()), key="mobile_target_stock")
            sel_stock_id = stock_options.get(sel_label)
            target_row = perf_df[perf_df["id"] == sel_stock_id].iloc[0]

            curr_qty = float(target_row["quantity"])
            curr_buy = float(target_row["buy_price"])
            curr_target = float(target_row["target_price"]) if is_valid_price(target_row.get("target_price")) else 0.0
            curr_stop = float(target_row["stop_loss_price"]) if is_valid_price(target_row.get("stop_loss_price")) else 0.0
            raw_memo = target_row.get("memo")
            if pd.isna(raw_memo) or raw_memo is None or str(raw_memo).strip() in ("None", "nan", "NaN", "null", ""):
                curr_memo = ""
            else:
                curr_memo = str(raw_memo).strip()
            curr_market = str(target_row["market"])
            curr_cur = str(target_row["currency"])
            curr_account = str(target_row.get("account") or "기본")
            live_p = float(target_row["current_price"])

            # 선택 종목 요약 상태 카드
            p_chg = target_row["eval_profit"]
            p_rate = target_row["profit_rate"]
            p_color = "#EF4444" if p_chg > 0 else ("#3B82F6" if p_chg < 0 else "#94A3B8")
            p_sign = "+" if p_chg > 0 else ""
            if curr_market == "KRX":
                cur_fmt = f"{curr_buy:,.0f}원"
                cur_live_fmt = f"{live_p:,.0f}원"
                cur_profit_fmt = f"{p_sign}{p_chg:,.0f}원"
            else:
                cur_fmt = f"${curr_buy:,.2f}"
                live_won_str = format_won_compact(live_p * usd_rate, prefix_approx=True)
                cur_live_fmt = f"${live_p:,.2f} <span style=\"font-size: 0.85rem; color: #94A3B8;\">({live_won_str})</span>"
                profit_won_val = float(target_row.get("eval_profit_won", p_chg * usd_rate))
                p_won_sign = "+" if profit_won_val > 0 else ("-" if profit_won_val < 0 else "")
                cur_profit_fmt = f"{p_sign}${p_chg:,.2f} <span style=\"font-size: 0.8rem; color: #94A3B8;\">(약 {p_won_sign}{abs(profit_won_val):,.0f}원)</span>"

            badge_sl = '<span class="badge-stop-loss" style="margin-left: 8px;">🚨 손절 경고</span>' if target_row['is_stop_loss'] else ''
            st.markdown(
                f'<div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 0.85rem 1.1rem; margin-top: 0.5rem; margin-bottom: 1rem;">'
                f'<div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">'
                f'<div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">'
                f'<span class="market-account-chip">{target_row["market"]} · {curr_account}</span>'
                f'<b style="font-size: 1.1rem; color: #F8FAFC; word-break: keep-all;">{target_row["name"]}</b>'
                f'<span style="color: #94A3B8; font-size: 0.85rem; margin-left: 4px;">({target_row["ticker"]})</span>'
                f'{badge_sl}'
                f'</div>'
                f'<div style="text-align: right;">'
                f'<span style="font-size: 0.85rem; color: #94A3B8;">현재가: </span><b style="color: #F8FAFC;">{cur_live_fmt}</b>'
                f'<span style="font-size: 0.9rem; font-weight: 700; color: {p_color}; margin-left: 8px;">{p_sign}{p_rate:.2f}% ({cur_profit_fmt})</span>'
                f'</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True
            )

            # 2개 서브탭: [✏️ 직접 수정] vs [⚖️ 거래 계산기]
            tab_edit, tab_rebalance = st.tabs(["✏️ 직접 수정", "⚖️ 거래 계산기"])

            with tab_edit:
                st.caption("계좌, 보유 수량, 매수가, 목표가, 손절가, 메모를 큰 입력창에서 손쉽게 수정합니다.")

                edit_accounts = repo.get_accounts(user_id)
                edit_acc_options = {format_acc_label(a): a for a in edit_accounts}
                edit_acc_choices = list(edit_acc_options.keys()) + ["직접 입력"]

                # 현재 종목의 계좌 기본 인덱스 매칭
                curr_acc_id = target_row.get("account_id")
                default_edit_idx = 0
                for idx, (lbl, a_obj) in enumerate(edit_acc_options.items()):
                    if (curr_acc_id and a_obj.get("id") == curr_acc_id) or (a_obj.get("broker_name") == curr_account):
                        default_edit_idx = idx
                        break

                with st.container(key="edit_account_field_container"):
                    st.markdown("""
                        <div class="account-filter-label-row">
                            <span class="account-filter-label-text">📁 계좌 / 금융앱 구분</span>
                            <span class="account-inline-tooltip" tabindex="0" role="button" aria-label="계좌 구분 도움말">
                                <span class="tooltip-icon">ℹ️</span>
                                <span class="tooltip-bubble">등록된 증권사/금융앱 계좌를 지정하거나 ➕ 버튼을 눌러 계좌를 관리할 수 있습니다.</span>
                            </span>
                        </div>
                    """, unsafe_allow_html=True)
                    m_acc_c1, m_acc_c2 = st.columns([4.2, 0.8], vertical_alignment="center")
                    with m_acc_c1:
                        edit_acc_choice = st.selectbox(
                            "📁 계좌 / 금융앱 구분",
                            options=edit_acc_choices,
                            index=default_edit_idx if default_edit_idx < len(edit_acc_choices) else 0,
                            key=f"m_acc_sel_{sel_stock_id}",
                            label_visibility="collapsed"
                        )
                    with m_acc_c2:
                        if st.button("➕", key=f"m_acc_btn_manage_{sel_stock_id}", use_container_width=True, help="➕ 계좌 관리: 계좌 추가/수정/삭제 및 ISA 만기 관리"):
                            manage_accounts_dialog(user_id, repo)

                if edit_acc_choice == "직접 입력":
                    new_m_account = st.text_input("새 계좌명 직접 입력*", value="", placeholder="계좌명 입력", key=f"m_acc_custom_{sel_stock_id}")
                    new_m_account_id = None
                else:
                    matched_acc = edit_acc_options.get(edit_acc_choice)
                    if matched_acc:
                        new_m_account = matched_acc.get("broker_name", "기본")
                        new_m_account_id = matched_acc.get("id")
                    else:
                        new_m_account = edit_acc_choice
                        new_m_account_id = None

                if curr_market == "KRX":
                    p_step = 1000
                    p_format = "%d"
                    p_min = 0
                    m_buy_val = int(curr_buy)
                    m_target_val = int(curr_target)
                    m_stop_val = int(curr_stop)
                else:
                    p_step = 1.0
                    p_format = "%.2f"
                    p_min = 0.0
                    m_buy_val = float(curr_buy)
                    m_target_val = float(curr_target)
                    m_stop_val = float(curr_stop)

                m_col1, m_col2 = st.columns(2)
                with m_col1:
                    new_m_buy = render_currency_input(
                        f"매수 평단가 ({curr_cur})*",
                        value=m_buy_val,
                        market=curr_market,
                        key=f"m_buy_{sel_stock_id}"
                    )
                with m_col2:
                    new_m_qty = st.number_input(
                        "보유 수량 (주)*",
                        min_value=0.0001,
                        step=1.0,
                        value=float(curr_qty),
                        format="%g",
                        placeholder="1",
                        key=f"m_qty_{sel_stock_id}"
                    )

                m_col3, m_col4 = st.columns(2)
                with m_col3:
                    new_m_target = render_currency_input(
                        f"목표가 ({curr_cur}, 0이면 미설정)",
                        value=m_target_val,
                        market=curr_market,
                        key=f"m_target_{sel_stock_id}"
                    )
                with m_col4:
                    new_m_stop = render_currency_input(
                        f"손절가 ({curr_cur}, 0이면 미설정 🚨)",
                        value=m_stop_val,
                        market=curr_market,
                        key=f"m_stop_{sel_stock_id}"
                    )

                new_m_memo = st.text_input(
                    "투자 메모",
                    value=curr_memo,
                    placeholder="예: 장기 적립식, 배당 투자 등",
                    key=f"m_memo_{sel_stock_id}"
                )

                btn_col1, btn_col2 = st.columns([2, 1])
                with btn_col1:
                    if st.button("💾 이 종목 수정사항 저장", type="primary", use_container_width=True, key=f"m_save_btn_{sel_stock_id}"):
                        if new_m_buy <= 0 or new_m_qty <= 0:
                            st.error("매수가와 보유 수량은 0보다 커야 합니다.")
                        else:
                            clean_save_memo = new_m_memo.strip() if new_m_memo else ""
                            if not clean_save_memo or clean_save_memo in ("None", "nan", "NaN", "null"):
                                final_save_memo = None
                            else:
                                final_save_memo = clean_save_memo

                            up_dict = {
                                "account": new_m_account.strip() or "기본",
                                "account_id": new_m_account_id,
                                "buy_price": float(new_m_buy),
                                "quantity": float(new_m_qty),
                                "target_price": float(new_m_target) if new_m_target > 0 else None,
                                "stop_loss_price": float(new_m_stop) if new_m_stop > 0 else None,
                                "memo": final_save_memo
                            }
                            ok, msg = repo.update_item(sel_stock_id, up_dict)
                            if ok:
                                st.session_state.pending_toast = (f"💾 [{target_row['name']}] 보유 정보가 수정되었습니다.", "✨")
                                st.session_state.scroll_to_top = True
                                st.rerun()
                            else:
                                st.error(msg)
                with btn_col2:
                    if st.button("🗑️ 이 종목 삭제", type="secondary", use_container_width=True, key=f"m_del_btn_{sel_stock_id}"):
                        d_ok, d_msg = repo.delete_item(sel_stock_id)
                        if d_ok:
                            st.session_state.pending_toast = (f"🗑️ [{target_row['name']}] 종목이 삭제되었습니다.", "ℹ️")
                            st.session_state.scroll_to_top = True
                            st.rerun()
                        else:
                            st.error(d_msg)

            with tab_rebalance:
                st.caption("추가 매수(물타기/불타기) 또는 부분 매도 시 예상 평단가와 잔여 수량을 실시간 계산하여 원클릭으로 반영합니다.")

                r_col1, r_col2, r_col3 = st.columns([1.2, 1, 1])
                with r_col1:
                    trade_action = st.radio(
                        "거래 유형",
                        options=["BUY", "SELL"],
                        format_func=lambda x: "➕ 추가 매수" if x == "BUY" else "➖ 부분 매도",
                        horizontal=True,
                        key=f"reb_action_{sel_stock_id}"
                    )
                with r_col2:
                    trade_qty = st.number_input(
                        "거래 수량 (주)",
                        min_value=0.0001,
                        max_value=1000000.0 if trade_action == "BUY" else curr_qty,
                        value=1.0 if trade_action == "BUY" else min(curr_qty, 1.0),
                        step=1.0,
                        format="%g",
                        placeholder="1",
                        key=f"reb_qty_{sel_stock_id}"
                    )
                with r_col3:
                    init_trade_price = (
                        int(live_p if live_p > 0 else curr_buy)
                        if curr_market == "KRX"
                        else float(live_p if live_p > 0 else curr_buy)
                    )
                    trade_price = render_currency_input(
                        f"거래 단가 ({curr_cur})",
                        value=init_trade_price,
                        market=curr_market,
                        key=f"reb_price_{sel_stock_id}",
                        help="기본값으로 현재 시장가를 제안합니다."
                    )

                # 실시간 평단가 산출
                new_qty, new_buy, calc_msg = calculate_rebalanced_position(
                    trade_action, curr_qty, curr_buy, trade_qty, trade_price
                )

                new_fmt = f"{new_buy:,.0f}원" if curr_market == "KRX" else f"${new_buy:,.2f}"
                diff_val = new_buy - curr_buy
                diff_fmt = f"{diff_val:+,.0f}원" if curr_market == "KRX" else f"{diff_val:+,.2f}"

                st.markdown(
                    f'<div class="simulation-box">'
                    f'<div class="simulation-title">📊 <b>시뮬레이션 결과</b></div>'
                    f'<div class="simulation-flow">'
                    f'<div class="simulation-item"><span class="sim-label">현재 상태:</span> <b class="sim-val">{format_quantity(curr_qty)}</b> @ <b class="sim-val">{cur_fmt}</b></div>'
                    f'<div class="simulation-arrow">➔</div>'
                    f'<div class="simulation-item"><span class="sim-label">거래 후 예상:</span> <b class="sim-val highlight">{format_quantity(new_qty)}</b> @ <b class="sim-val highlight">{new_fmt}</b> <span class="sim-diff">({diff_fmt})</span></div>'
                    f'</div>'
                    f'<div class="simulation-msg">{calc_msg}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

                if st.button("⚡ 계산된 평단가/수량을 포트폴리오에 즉시 반영", type="primary", use_container_width=True, key=f"reb_apply_btn_{sel_stock_id}"):
                    up_dict = {
                        "account": target_row.get("account", "기본"),
                        "buy_price": new_buy,
                        "quantity": new_qty,
                        "target_price": target_row.get("target_price"),
                        "stop_loss_price": target_row.get("stop_loss_price"),
                        "memo": target_row.get("memo")
                    }
                    ok, msg = repo.update_item(sel_stock_id, up_dict)
                    if ok:
                        st.session_state.pending_toast = (f"💾 [{target_row['name']}] 보유 정보가 수정되었습니다.", "✨")
                        st.session_state.scroll_to_top = True
                        st.rerun()
                    else:
                        st.error(msg)

        # ----------------------------------------------------------------------
        # 탭 2: 5개 필수 편집 열만 남긴 [초슬림 퀵 에디터]
        # ----------------------------------------------------------------------
        with tab_table_edit:
            with st.container(key="slim_editor_header_container"):
                norm_c1, norm_c2 = st.columns([3.2, 1.2], vertical_alignment="center")
                with norm_c1:
                    st.caption("💡 엑셀처럼 표에서 **계좌, 매수가, 수량, 목표가, 손절가, 메모**를 일괄 수정합니다.")
                with norm_c2:
                    if st.button("📱 가로 넓게 보기", key="btn_enter_table_landscape", use_container_width=True, help="모바일 환경에서 표를 가로 전체화면으로 넓게 편집합니다."):
                        landscape_quick_editor_dialog(items, perf_df, repo, user_id)

            slim_rows = []
            for _, r in perf_df.iterrows():
                slim_rows.append({
                    "_id": r["id"],
                    "계좌": str(r.get("account") or "기본"),
                    "시장": "🇰🇷 KRX" if r["market"] == "KRX" else "🇺🇸 US",
                    "종목명": r["name"],
                    "매수가": float(r["buy_price"]),
                    "보유 수량": float(r["quantity"]),
                    "목표가": float(r["target_price"]) if is_valid_price(r.get("target_price")) else 0.0,
                    "손절가": float(r["stop_loss_price"]) if is_valid_price(r.get("stop_loss_price")) else 0.0,
                    "메모": str(r.get("memo") or "")
                })

            slim_df = pd.DataFrame(slim_rows)
            slim_col_config = {
                "_id": None,
                "계좌": st.column_config.TextColumn("계좌 / 앱", width="small", max_chars=30),
                "시장": st.column_config.TextColumn("시장", width="small", disabled=True),
                "종목명": st.column_config.TextColumn("종목명", width="medium", disabled=True),
                "매수가": st.column_config.NumberColumn("매수가", min_value=0.0, step=1.0, required=True),
                "보유 수량": st.column_config.NumberColumn("보유 수량", min_value=0.0001, step=1.0, format="%g", required=True),
                "목표가": st.column_config.NumberColumn("목표가 (0이면 해제)", min_value=0.0, step=1.0),
                "손절가": st.column_config.NumberColumn("손절가 (0이면 해제)", min_value=0.0, step=1.0),
                "메모": st.column_config.TextColumn("메모", width="large", max_chars=100)
            }

            edited_slim = st.data_editor(
                slim_df,
                column_config=slim_col_config,
                disabled=["시장", "종목명"],
                use_container_width=True,
                hide_index=True,
                key="slim_portfolio_editor"
            )

            if st.button("💾 테이블 변경사항 일괄 저장", type="primary", use_container_width=True, key="save_slim_editor_btn"):
                updated_count = 0
                for _, row in edited_slim.iterrows():
                    item_id = row["_id"]
                    orig_item = next((it for it in items if it.get("id") == item_id), None)
                    if not orig_item:
                        continue

                    new_acc = str(row.get("계좌") or "기본").strip() or "기본"
                    new_buy = float(row["매수가"])
                    new_qty = float(row["보유 수량"])
                    new_target = float(row["목표가"]) if float(row["목표가"]) > 0 else None
                    new_stop = float(row["손절가"]) if float(row["손절가"]) > 0 else None
                    new_memo = str(row["메모"]).strip() or None

                    orig_acc = str(orig_item.get("account") or "기본").strip() or "기본"
                    orig_buy = float(orig_item.get("buy_price", 0))
                    orig_qty = float(orig_item.get("quantity", 0))
                    orig_target = float(orig_item["target_price"]) if is_valid_price(orig_item.get("target_price")) else None
                    orig_stop = float(orig_item["stop_loss_price"]) if is_valid_price(orig_item.get("stop_loss_price")) else None
                    orig_memo = str(orig_item.get("memo") or "").strip() or None

                    if (
                        new_acc != orig_acc or
                        abs(new_buy - orig_buy) > 1e-4 or
                        abs(new_qty - orig_qty) > 1e-4 or
                        new_target != orig_target or
                        new_stop != orig_stop or
                        new_memo != orig_memo
                    ):
                        up_data = {
                            "account": new_acc,
                            "buy_price": new_buy,
                            "quantity": new_qty,
                            "target_price": new_target,
                            "stop_loss_price": new_stop,
                            "memo": new_memo
                        }
                        ok, _ = repo.update_item(item_id, up_data)
                        if ok:
                            updated_count += 1

                if updated_count > 0:
                    st.session_state.pending_toast = (f"💾 {updated_count}건의 종목 정보가 수정되었습니다.", "✨")
                    st.session_state.scroll_to_top = True
                    st.rerun()
                else:
                    st.info("수정된 변경사항이 없습니다.")



# ------------------------------------------------------------------------------
# 10. 보유 종목 관련 최신 뉴스/공시 헤드라인
# ------------------------------------------------------------------------------
st.markdown("---")
st.markdown('<h4 style="word-break: keep-all; letter-spacing: -0.5px; margin-bottom: 0.5rem;">📰 보유 종목 최신 뉴스 및 DART 주요 공시 헤드라인</h4>', unsafe_allow_html=True)

holding_tickers = [str(r["ticker"]).strip() for _, r in perf_df.iterrows()] if not perf_df.empty else []
news_items = fetch_stock_news(holding_tickers)

if not news_items:
    st.caption("관련 뉴스가 없습니다.")
else:
    for n in news_items:
        st.markdown(
            f'<div class="portfolio-news-item">'
            f'<div class="portfolio-news-main">'
            f'<span class="badge-tag">{n.get("ticker", "시장")}</span>'
            f'<a href="{n.get("link", "#")}" target="_blank" class="portfolio-news-link">'
            f'{n.get("title")}'
            f'</a>'
            f'</div>'
            f'<div class="portfolio-news-meta">'
            f'{n.get("publisher")} · {n.get("time")}'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True
        )

# ------------------------------------------------------------------------------
# 전역 클라이언트 상호작용 강화 스크립트 주입 (문서 최하단 배치로 상단 레이아웃 여백 무결성 보장)
# ------------------------------------------------------------------------------
with st.container(key="global_script_injector_container"):
    inject_tab_lock_and_loading_script()
    inject_number_input_enhancer_script()
    inject_currency_input_script()
    inject_mobile_landscape_table_script()


