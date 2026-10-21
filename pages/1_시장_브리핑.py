"""
1페이지: [시장 브리핑 및 발굴]
- 상단: 국장/미장 주요 지수 6대 지표 요약 메트릭 카드
- 중단: 오늘의 시장 3줄 핵심 브리핑 (거시 / 심리 / 전략)
- 하단: 오늘 눈여겨볼 ETF/주식 Top 3 (가치 50% + 수급 50% 퀀트 기준 산출)
"""
from pathlib import Path
import streamlit as st
import pandas as pd

from services.market_service import (
    fetch_market_indices,
    generate_3line_briefing,
    get_mock_indices,
    get_market_operation_status,
)
from services.npay_service import fetch_npay_items, calculate_top3_quant
from db.supabase_client import is_supabase_configured

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


# ------------------------------------------------------------------------------
# 2. 전역 커스텀 스타일시트 주입
# ------------------------------------------------------------------------------
def inject_custom_css():
    css_path = Path(__file__).resolve().parent.parent / "assets" / "style.css"
    if css_path.exists():
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


inject_custom_css()


# ------------------------------------------------------------------------------
# 3. 사이드바 상태 표시
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
        st.success("🔒 **Supabase 동기화 모드**", icon="✅")
    else:
        st.warning("⚠️ **로컬 체험 모드**", icon="ℹ️")

    st.markdown("---")
    if st.button("🔄 시세 데이터 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ------------------------------------------------------------------------------
# 4. 헤더 타이틀 & 시장 개장 상태 종합 바
# ------------------------------------------------------------------------------
st.markdown("""
    <div style="margin-bottom: 0.85rem;">
        <h2 class="page-sub-title" style="color: #F8FAFC; margin-bottom: 0.25rem; word-break: keep-all; letter-spacing: -0.5px;">
            🌐 오늘의 시장 브리핑 & 추천 종목
        </h2>
        <p style="color: #94A3B8; font-size: 0.95rem; margin: 0; word-break: keep-all; letter-spacing: -0.3px;">
            주요 시장 지수 현황과 오늘의 핵심 요약, 그리고 가치·수급 기반 유망 종목 Top 3를 실시간 제공합니다.
        </p>
    </div>
""", unsafe_allow_html=True)

# 한국 시간(KST) 기준 현재 시각 및 시장 개장 상태 조회
op_status = get_market_operation_status()
krx_info = op_status.get("krx", {})
us_info = op_status.get("us", {})

current_time_kst = op_status.get("current_time_kst", "")
current_time_us = op_status.get("current_time_us")
if not current_time_us:
    try:
        from zoneinfo import ZoneInfo
        from datetime import datetime
        kst_tz = ZoneInfo("Asia/Seoul")
        ny_tz = ZoneInfo("America/New_York")
        now_kst = op_status.get("now_kst") or datetime.now(kst_tz)
        now_ny = now_kst.astimezone(ny_tz)
        weekday_us = ["월", "화", "수", "목", "금", "토", "일"][now_ny.weekday()]
        tz_us_name = now_ny.strftime("%Z")
        current_time_us = now_ny.strftime(f"%Y년 %m월 %d일 ({weekday_us}) %H:%M:%S") + f" {tz_us_name}"
    except Exception:
        current_time_us = "시간 확인 중"

# 상단 시장 운영 상태 & 현재 시간 종합 바 렌더링 (모바일 컴팩트 계층화)
status_bar_html = (
    f'<div class="market-status-bar">'
    f'<div class="status-bar-times">'
    f'<div class="time-chip">'
    f'<span class="time-label">🕒 <b>한국(KST):</b></span>'
    f'<strong class="time-val" style="color: #38BDF8;">{current_time_kst}</strong>'
    f'</div>'
    f'<div class="time-chip">'
    f'<span class="time-label">🗽 <b>미국(ET):</b></span>'
    f'<strong class="time-val" style="color: #F59E0B;">{current_time_us}</strong>'
    f'</div>'
    f'</div>'
    f'<div class="status-bar-markets">'
    f'<div class="status-chip" style="border: 1px solid {krx_info.get("badge_color", "#64748B")};">'
    f'<div class="status-chip-title">'
    f'<span>🇰🇷 <b>국내(KRX)</b>:</span> '
    f'<span style="color: {krx_info.get("badge_color", "#64748B")}; font-weight: 700;">{krx_info.get("status_text", "-")}</span>'
    f'</div>'
    f'<span class="status-chip-sub">({krx_info.get("target_label", "")} {krx_info.get("remaining_time", "")})</span>'
    f'</div>'
    f'<div class="status-chip" style="border: 1px solid {us_info.get("badge_color", "#64748B")};">'
    f'<div class="status-chip-title">'
    f'<span>🇺🇸 <b>미국(US)</b>:</span> '
    f'<span style="color: {us_info.get("badge_color", "#64748B")}; font-weight: 700;">{us_info.get("status_text", "-")}</span>'
    f'</div>'
    f'<span class="status-chip-sub">({us_info.get("target_label", "")} {us_info.get("remaining_time", "")})</span>'
    f'</div>'
    f'</div>'
    f'</div>'
)
st.markdown(status_bar_html, unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# 5. 상단: 6대 거시 지표 메트릭 카드 렌더링
# ------------------------------------------------------------------------------
indices = fetch_market_indices()
mock_fallback = get_mock_indices()

head_col1, head_col2 = st.columns([2.5, 1.5])
with head_col1:
    st.markdown("#### 📊 핵심 시장 지표 요약")
with head_col2:
    view_mode = st.selectbox(
        "지표 보기 방식",
        options=["자동 (기기 최적화)", "1줄 목록형", "3열 카드형"],
        index=0,
        label_visibility="collapsed",
        key="index_view_mode",
        help="📱 모바일 1줄 가로형 바 또는 🖥️ PC 3열 카드형을 선택할 수 있습니다."
    )

subgrid_class = "metric-subgrid"
if view_mode == "1줄 목록형":
    subgrid_class += " force-list-mode"
elif view_mode == "3열 카드형":
    subgrid_class += " force-card-mode"


def _render_metric_box(meta: dict) -> str:
    name = meta.get("name", "")
    val = meta.get("value", 0.0)
    chg = meta.get("change", 0.0)
    chg_rate = meta.get("change_rate", 0.0)
    unit = meta.get("unit", "")

    # 한국식 컬러링 (상승: 붉은색, 하락: 파란색)
    if chg > 0:
        color_class = "text-profit"
        icon_str = "▲"
        sign_str = "+"
    elif chg < 0:
        color_class = "text-loss"
        icon_str = "▼"
        sign_str = ""
    else:
        color_class = ""
        icon_str = "-"
        sign_str = ""

    val_str = f"{val:,.2f}" if isinstance(val, (int, float)) else str(val)

    # PC 3열 카드와 모바일 1줄 리스트 바를 모두 지원하는 유연한 flexbox 구조
    return (
        f'<div class="metric-box">'
        f'<div class="metric-left">'
        f'<span class="metric-title">{name}</span>'
        f'</div>'
        f'<div class="metric-right">'
        f'<div class="metric-value"><span style="display: inline-block; white-space: nowrap;">{val_str} <span class="metric-unit" style="font-size: 0.75rem; color: #94A3B8;">{unit}</span></span></div>'
        f'<div class="metric-change {color_class}" style="font-size: 0.82rem; font-weight: 600; white-space: nowrap;">'
        f'{icon_str} {sign_str}{chg:,.2f} ({sign_str}{chg_rate:.2f}%)'
        f'</div>'
        f'</div>'
        f'</div>'
    )


col_kr, col_us = st.columns(2, gap="large")

with col_kr:
    st.markdown(
        f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; flex-wrap: wrap; gap: 6px;">'
        f'<div style="display: flex; align-items: center; gap: 8px;">'
        f'<span style="font-size: 1.05rem; font-weight: 700; color: #F8FAFC;">🇰🇷 국내 시장 핵심 지표</span>'
        f'<span class="badge-tag" style="background: rgba(59, 130, 246, 0.2); color: #60A5FA; border: 1px solid rgba(59, 130, 246, 0.4);">KRX · FX</span>'
        f'</div>'
        f'<span style="font-size: 0.8rem; color: {krx_info["badge_color"]}; font-weight: 600;">'
        f'{krx_info["status_text"]} · {krx_info["target_label"]} {krx_info["remaining_time"]}'
        f'</span>'
        f'</div>',
        unsafe_allow_html=True
    )
    kr_boxes = []
    for k in ["KOSPI", "KOSDAQ", "USD/KRW"]:
        item = indices.get(k)
        if not item or not isinstance(item, dict) or not item.get("value"):
            item = mock_fallback.get(k)
        if item:
            kr_boxes.append(_render_metric_box(item))
    kr_html = f'<div class="{subgrid_class}">{"".join(kr_boxes)}</div>'
    st.markdown(kr_html, unsafe_allow_html=True)

with col_us:
    st.markdown(
        f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; flex-wrap: wrap; gap: 6px;">'
        f'<div style="display: flex; align-items: center; gap: 8px;">'
        f'<span style="font-size: 1.05rem; font-weight: 700; color: #F8FAFC;">🇺🇸 미국 & 글로벌 핵심 지표</span>'
        f'<span class="badge-tag" style="background: rgba(16, 185, 129, 0.2); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.4);">US · BOND</span>'
        f'</div>'
        f'<span style="font-size: 0.8rem; color: {us_info["badge_color"]}; font-weight: 600;">'
        f'{us_info["status_text"]} · {us_info["target_label"]} {us_info["remaining_time"]}'
        f'</span>'
        f'</div>',
        unsafe_allow_html=True
    )
    us_boxes = []
    for k in ["S&P 500", "NASDAQ", "US 10Y"]:
        item = indices.get(k)
        if not item or not isinstance(item, dict) or not item.get("value"):
            item = mock_fallback.get(k)
        if item:
            us_boxes.append(_render_metric_box(item))
    us_html = f'<div class="{subgrid_class}">{"".join(us_boxes)}</div>'
    st.markdown(us_html, unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# 6. 중단: 오늘의 시장 3줄 브리핑 영역
# ------------------------------------------------------------------------------
st.markdown("#### 📝 오늘의 시장 3줄 핵심 브리핑")

briefings = generate_3line_briefing(indices)

for item in briefings:
    badge_color = "#3B82F6" if item["category"] == "거시경제" else ("#10B981" if item["category"] == "시장심리" else "#F59E0B")
    st.markdown(
        f'<div class="briefing-box">'
        f'<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 0.4rem;">'
        f'<span class="badge-tag" style="background: {badge_color}33; color: {badge_color}; border: 1px solid {badge_color};">'
        f'{item["category"]}'
        f'</span>'
        f'<strong style="color: #F8FAFC; font-size: 1rem;">{item["title"]}</strong>'
        f'</div>'
        f'<div class="briefing-item">{item["summary"]}</div>'
        f'</div>',
        unsafe_allow_html=True
    )


# ------------------------------------------------------------------------------
# 7. 하단: 오늘 눈여겨볼 ETF/주식 Top 3 (가치 50% + 수급 50%)
# ------------------------------------------------------------------------------
st.markdown("---")
st.markdown("#### 🎯 오늘 눈여겨볼 종목 Top 3")
st.caption("네이버 증권 거래 상위 종목의 수급과 저평가 지표를 종합 분석해 추출합니다. 💡 **종목코드(📋)**를 터치/클릭하면 클립보드로 즉시 복사됩니다.")

tab_krx, tab_us = st.tabs(["🇰🇷 국내 시장 Top 3 (ETF/주식)", "🇺🇸 미국 시장 Top 3 (ETF/주식)"])


def inject_ticker_copy_script():
    script_html = """
    <script>
    (function() {
        try {
            var doc = (typeof window !== 'undefined' && window.parent && window.parent.document) || (typeof document !== 'undefined' ? document : null);
            if (!doc || doc._tickerCopyListenerAdded) return;
            doc._tickerCopyListenerAdded = true;

            doc.addEventListener('click', function(e) {
                try {
                    var badge = e.target.closest ? e.target.closest('.ticker-badge') : null;
                    if (!badge) return;
                    var ticker = badge.getAttribute('data-ticker') || badge.innerText.replace('📋', '').trim();
                    if (!ticker) return;

                    var done = function() {
                        var orig = badge.innerHTML;
                        badge.innerHTML = '✅ 복사됨!';
                        badge.style.borderColor = '#10b981';
                        setTimeout(function() {
                            badge.innerHTML = orig;
                            badge.style.borderColor = '';
                        }, 1200);
                    };

                    var nav = (typeof window !== 'undefined' && window.parent && window.parent.navigator) || navigator;
                    var cbObj = (nav && nav.clipboard) || (typeof navigator !== 'undefined' && navigator.clipboard);
                    if (cbObj && cbObj.writeText) {
                        navigator.clipboard.writeText(ticker).then(done).catch(function() {
                            fallback(ticker, done);
                        });
                    } else {
                        fallback(ticker, done);
                    }

                    function fallback(text, cb) {
                        try {
                            var ta = doc.createElement('textarea');
                            ta.value = text;
                            ta.style.position = 'fixed';
                            ta.style.opacity = '0';
                            var container = doc.body || doc.documentElement;
                            if (container) {
                                container.appendChild(ta);
                                ta.select();
                                doc.execCommand('copy');
                                container.removeChild(ta);
                            }
                            cb();
                        } catch(err) {
                            console.error('Copy failed:', err);
                        }
                    }
                } catch(err) {}
            });
        } catch(err) {}
    })();
    </script>
    """
    try:
        st.html(f"<div style='display:none;'>{script_html}</div>", unsafe_allow_javascript=True)
    except Exception:
        st.markdown(f"<div style='display:none;'>{script_html}</div>", unsafe_allow_html=True)



def render_top3_cards(df: pd.DataFrame, currency_symbol: str = "원"):
    if df.empty:
        st.warning("분석 가능한 시세 데이터가 없습니다.")
        return

    inject_ticker_copy_script()

    top3 = calculate_top3_quant(df)

    cols = st.columns(3, gap="medium")
    for idx, (_, row) in enumerate(top3.iterrows()):
        with cols[idx]:
            rank_emojis = ["🥇 1위", "🥈 2위", "🥉 3위"]
            rank_title = rank_emojis[idx] if idx < 3 else f"#{idx+1}"

            chg = float(row.get("change_rate", 0.0))
            chg_color = "#EF4444" if chg > 0 else ("#3B82F6" if chg < 0 else "#94A3B8")
            chg_sign = "+" if chg > 0 else ""

            # 가격 포맷팅 안전 처리 (숫자와 통화 단위 분리 방지)
            price_val = float(row.get("current_price", 0.0))
            if currency_symbol == "$":
                price_display_str = f"${price_val:,.2f}"
            else:
                price_display_str = f"{price_val:,.0f}원"

            total_sc = int(row.get("total_score", 50))
            val_sc = int(row.get("value_score", 50))
            sup_sc = int(row.get("supply_score", 50))
            reason_txt = str(row.get("reason", ""))
            ticker_str = str(row.get("ticker", "")).strip()

            card_html = (
                f'<div class="fin-card" style="border-top: 3px solid #3B82F6; word-break: keep-all;">'
                f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem;">'
                f'<span style="font-weight: 800; font-size: 1.15rem; color: #60A5FA; white-space: nowrap;">{rank_title}</span>'
                f'<span class="ticker-badge" data-ticker="{ticker_str}" style="cursor: pointer; user-select: all;">📋 {ticker_str}</span>'
                f'</div>'
                f'<div style="font-size: 1.15rem; font-weight: 700; color: #F8FAFC; margin-bottom: 0.25rem; word-break: keep-all; letter-spacing: -0.3px;">'
                f'{row["name"]}'
                f'</div>'
                f'<div style="display: flex; align-items: baseline; gap: 8px; margin-bottom: 0.75rem; flex-wrap: wrap;">'
                f'<span style="font-size: 1.25rem; font-weight: 800; color: #F8FAFC; display: inline-block; white-space: nowrap;">'
                f'{price_display_str}'
                f'</span>'
                f'<span style="color: {chg_color}; font-weight: 700; font-size: 0.92rem; display: inline-block; white-space: nowrap;">'
                f'({chg_sign}{chg:.2f}%)'
                f'</span>'
                f'</div>'
                f'<div style="margin-bottom: 0.5rem;">'
                f'<div style="display: flex; justify-content: space-between; font-size: 0.8rem; color: #94A3B8; margin-bottom: 0.2rem; white-space: nowrap;">'
                f'<span>종합 추천 점수</span>'
                f'<span style="font-weight: 700; color: #60A5FA;">{total_sc}점 / 100점</span>'
                f'</div>'
                f'</div>'
                f'<div style="background: rgba(51, 65, 85, 0.4); border-radius: 8px; padding: 0.6rem 0.8rem; font-size: 0.82rem; color: #CBD5E1; line-height: 1.5; margin-top: 0.5rem; word-break: keep-all;">'
                f'💡 <b>선정 사유</b><br>{reason_txt}'
                f'</div>'
                f'</div>'
            )
            st.markdown(card_html, unsafe_allow_html=True)

            # 프로그레스 바 렌더링
            score_val = max(0.0, min(1.0, float(total_sc) / 100.0))
            st.progress(score_val, text=f"가치 분석 {val_sc}점 (50%) + 수급 분석 {sup_sc}점 (50%)")


with tab_krx:
    with st.spinner("국내 Npay 증권 시세를 분석 중입니다..."):
        krx_raw = fetch_npay_items("KRX")
        render_top3_cards(krx_raw, currency_symbol="원")

with tab_us:
    with st.spinner("미국 Npay 글로벌 증시를 분석 중입니다..."):
        us_raw = fetch_npay_items("US")
        render_top3_cards(us_raw, currency_symbol="$")
