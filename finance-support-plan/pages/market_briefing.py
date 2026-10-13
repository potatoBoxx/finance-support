"""1페이지: 시장 브리핑 및 발굴 (Market Briefing & Discovery)
- 상단: 국장/미장 주요 지수 및 지표 요약 카드
- 중단: 오늘의 시장 3줄 브리핑 영역
- 하단: 오늘 눈여겨볼 Top 3 종목 (가치 50% + 수급 50% 혼합 기준)
"""

import streamlit as st
import plotly.graph_objects as go
from services.market_service import (
    get_market_indices,
    get_daily_market_briefing,
    get_top3_stock_picks,
)


def render_sparkline(data: list, color: str):
    """지수 카드용 미니 스파크라인 차트를 생성합니다."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=data,
        mode="lines",
        line=dict(color=color, width=2),
        hoverinfo="skip"
    ))
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=32,
        width=110,
        xaxis=dict(visible=False, showgrid=False),
        yaxis=dict(visible=False, showgrid=False),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def show_market_briefing_page():
    # ----------------------------------------------------
    # 페이지 헤더
    # ----------------------------------------------------
    st.markdown("""
        <div class="app-header">
            <h1>🌐 글로벌 시장 브리핑 & AI 유망 종목 발굴</h1>
            <p>국내외 핵심 지표 현황과 AI 기반 가치·수급 혼합 스코어링 Top 3 종목을 매일 업데이트합니다.</p>
        </div>
    """, unsafe_allow_html=True)

    # ----------------------------------------------------
    # 1. 상단: 국장/미장 주요 지수 및 지표 요약 카드
    # ----------------------------------------------------
    st.subheader("📊 주요 시장 지수 및 거시경제 지표", anchor=False)

    indices = get_market_indices()
    
    # PC에서는 3개씩 2줄(또는 6열), 모바일에서는 자동 리플로우
    cols_top = st.columns(3)
    cols_bottom = st.columns(3)
    cols = cols_top + cols_bottom

    for idx, item in enumerate(indices):
        col = cols[idx % len(cols)]
        is_up = item["change"] >= 0
        color_class = "text-up" if is_up else "text-down"
        arrow = "▲" if is_up else "▼"
        spark_color = "#ef4444" if is_up else "#3b82f6"

        with col:
            with st.container():
                st.markdown(f"""
                <div class="metric-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span class="category">{item['category']}</span>
                        <span class="{'badge-up' if is_up else 'badge-down'}">
                            {arrow} {abs(item['change_pct']):.2f}%
                        </span>
                    </div>
                    <div class="name">{item['name']}</div>
                    <div class="value">{item['value']:,.2f if isinstance(item['value'], float) and item['unit'] == 'pt' else (f"{item['value']:,.2f}" if isinstance(item['value'], float) else f"{item['value']:,}")} <span style="font-size: 0.8rem; font-weight: normal; color: #94a3b8;">{item['unit']}</span></div>
                    <div class="{color_class}" style="font-size: 0.82rem; font-weight: 600;">
                        전일대비 {arrow} {abs(item['change']):,.2f}
                    </div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # ----------------------------------------------------
    # 2. 중단: 오늘의 시장 3줄 브리핑 영역
    # ----------------------------------------------------
    briefing_data = get_daily_market_briefing()

    col_title, col_info = st.columns([2, 1])
    with col_title:
        st.subheader(f"📝 오늘의 시장 3줄 핵심 브리핑 ({briefing_data['date']})", anchor=False)
    with col_info:
        # 시장 심리 지수 표시
        st.markdown(f"""
        <div style="text-align: right; padding-top: 8px;">
            <span style="font-size: 0.85rem; color: #94a3b8;">시장 심리: </span>
            <span style="color: #38bdf8; font-weight: 700; font-size: 0.9rem;">
                🔥 {briefing_data['sentiment_label']} ({briefing_data['sentiment_score']}pt)
            </span>
        </div>
        """, unsafe_allow_html=True)

    # 태그 목록
    tags_html = " ".join([f"<span style='background: rgba(99, 102, 241, 0.15); color: #818cf8; padding: 2px 8px; border-radius: 4px; font-size: 0.78rem; margin-right: 6px;'>{t}</span>" for t in briefing_data["market_tags"]])
    st.markdown(f"<div style='margin-bottom: 12px;'>{tags_html}</div>", unsafe_allow_html=True)

    # 3줄 카드 렌더링
    for item in briefing_data["three_line_briefing"]:
        st.markdown(f"""
        <div class="briefing-card">
            <span class="badge">{item['num']}. {item['badge']}</span>
            <h4>{item['title']}</h4>
            <p>{item['desc']}</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)

    # ----------------------------------------------------
    # 3. 하단: 오늘 눈여겨볼 Top 3 종목 (가치 50% + 수급 50%)
    # ----------------------------------------------------
    st.subheader("🎯 오늘 눈여겨볼 Top 3 종목 (가치 50% + 수급 50% 퀀트 발굴)", anchor=False)
    st.caption("💡 밸류에이션 저평가 지표(50%)와 외국인·기관 수급 유입 강도(50%)를 정규화하여 선정한 당일 최우선 관심 종목입니다.")

    top_picks = get_top3_stock_picks()
    stock_cols = st.columns(3)

    for i, stock in enumerate(top_picks):
        with stock_cols[i]:
            with st.container():
                st.markdown(f"""
                <div class="stock-card">
                    <div>
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem;">
                            <span class="rank-badge">TOP {stock['rank']}</span>
                            <span class="score-badge">종합 {stock['total_score']}점</span>
                        </div>
                        <div style="font-size: 1.25rem; font-weight: 700; color: #f8fafc;">
                            {stock['name']} <span style="font-size: 0.85rem; color: #94a3b8; font-weight: normal;">({stock['ticker']})</span>
                        </div>
                        <div style="font-size: 0.8rem; color: #a5b4fc; margin-bottom: 0.6rem;">
                            {stock['market']} · {stock['sector']}
                        </div>
                        <div style="font-size: 1.3rem; font-weight: 800; color: #ffffff; margin-bottom: 0.8rem;">
                            {stock['current_price']:,}원
                            <span class="{'text-up' if stock['change_pct'] >= 0 else 'text-down'}" style="font-size: 0.9rem; margin-left: 6px;">
                                {'▲' if stock['change_pct'] >= 0 else '▼'} {abs(stock['change_pct']):.2f}%
                            </span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # 점수 상세 막대 (Streamlit 기본 프로그레스 바)
                st.markdown(f"**가치 점수 (50%)**: `{stock['value_score']}점`")
                st.progress(stock["value_score"] / 100.0)

                st.markdown(f"**수급 점수 (50%)**: `{stock['supply_score']}점`")
                st.progress(stock["supply_score"] / 100.0)

                # 핵심 세부 지표
                with st.expander("🔍 핵심 퀀트 지표 & 투자 포인트", expanded=True):
                    m = stock["key_metrics"]
                    st.markdown(f"""
                    - **PER / PBR**: `{m.get('PER')}` / `{m.get('PBR')}`
                    - **외인 5일**: `{m.get('외인 5일 순매수')}`
                    - **기관 5일**: `{m.get('기관 5일 순매수')}`
                    - **ROE**: `{m.get('ROE')}`
                    """)
                    st.info(stock["reason"], icon="📌")


if __name__ == "__main__":
    show_market_briefing_page()
