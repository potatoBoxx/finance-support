"""2페이지: 개인 포트폴리오 관리 (Personal Portfolio Management)
- 사용자 로그인/식별(ID/PIN) 세션 상태(st.session_state) 구조
- 보유 종목 등록/수정/삭제 (티커, 매수가, 수량, 목표가, 손절가)
- 종목별 수익률 및 평가손익 계산 테이블
- 보유 종목 관련 최신 뉴스/공시 헤드라인 표시 영역
"""

import streamlit as st
import pandas as pd
from data.portfolio_store import (
    authenticate_user,
    get_user_holdings,
    add_or_update_holding,
    delete_holding,
)
from services.portfolio_service import (
    calculate_portfolio_details,
    get_holdings_news_and_disclosures,
    get_current_stock_price,
)


def render_login_section():
    """사용자 식별 및 로그인 섹션을 렌더링합니다."""
    st.markdown("""
        <div class="app-header">
            <h1>🔒 개인 포트폴리오 관리</h1>
            <p>보안 식별(ID 및 PIN)을 통해 안전하게 개인 자산을 관리하고 손익 현황을 추적하세요.</p>
        </div>
    """, unsafe_allow_html=True)

    col_box, _ = st.columns([1.2, 1])
    with col_box:
        with st.container(border=True):
            st.subheader("🔑 사용자 로그인 / 계정 식별", anchor=False)
            st.caption("새로운 ID를 입력하면 입력하신 PIN으로 새 포트폴리오 계정이 자동 생성됩니다.")

            user_id = st.text_input("사용자 ID", placeholder="예: investor01 또는 demo", key="input_user_id")
            pin = st.text_input("보안 PIN (4자리 이상)", type="password", placeholder="PIN 번호 입력", key="input_pin")

            col_btn1, col_btn2 = st.columns([1, 1])
            with col_btn1:
                if st.button("🚀 로그인 / 시작하기", type="primary", use_container_width=True):
                    if not user_id.strip() or not pin.strip():
                        st.error("ID와 PIN을 모두 입력해 주세요.")
                    else:
                        success = authenticate_user(user_id, pin)
                        if success:
                            st.session_state.is_authenticated = True
                            st.session_state.user_id = user_id.strip()
                            st.success(f"'{user_id}'님 환영합니다!")
                            st.rerun()
                        else:
                            st.error("PIN 번호가 일치하지 않습니다.")

            with col_btn2:
                if st.button("✨ 데모 계정 체험 (demo)", use_container_width=True):
                    st.session_state.is_authenticated = True
                    st.session_state.user_id = "demo"
                    st.rerun()


def show_portfolio_page():
    # 세션 상태 확인
    if not st.session_state.get("is_authenticated", False):
        render_login_section()
        return

    current_user = st.session_state.get("user_id", "demo")

    # ----------------------------------------------------
    # 헤더 및 사용자 상태 관리
    # ----------------------------------------------------
    col_head, col_logout = st.columns([3, 1])
    with col_head:
        st.markdown(f"""
            <div class="app-header" style="margin-bottom: 0.8rem;">
                <h1>💼 {current_user}님의 자산 포트폴리오</h1>
                <p>실시간 평가손익 분석, 목표가/손절가 리스크 모니터링 및 관련 공시 헤드라인입니다.</p>
            </div>
        """, unsafe_allow_html=True)
    with col_logout:
        st.write("")
        st.write("")
        if st.button("🚪 로그아웃", use_container_width=True):
            st.session_state.is_authenticated = False
            st.session_state.user_id = None
            st.rerun()

    # 데이터 로드 및 계산
    holdings = get_user_holdings(current_user)
    calc_res = calculate_portfolio_details(holdings)
    summary = calc_res["summary"]
    rows = calc_res["rows"]

    # ----------------------------------------------------
    # 상단 KPI 요약 카드
    # ----------------------------------------------------
    kpi_cols = st.columns(4)

    is_profit = summary["total_profit"] >= 0
    profit_color = "text-up" if is_profit else "text-down"
    profit_sign = "+" if is_profit else ""

    with kpi_cols[0]:
        st.metric(
            label="총 매수금액 (원화 환산)",
            value=f"{summary['total_invested']:,} 원",
        )
    with kpi_cols[1]:
        st.metric(
            label="총 평가금액",
            value=f"{summary['total_eval']:,} 원",
            delta=f"{profit_sign}{summary['total_return_pct']:.2f}%",
        )
    with kpi_cols[2]:
        st.metric(
            label="총 평가손익",
            value=f"{profit_sign}{summary['total_profit']:,} 원",
        )
    with kpi_cols[3]:
        st.metric(
            label="보유 종목 / 손절 경고",
            value=f"{summary['holding_count']}개 종목",
            delta=f"🚨 {summary['warning_count']}건 경고" if summary["warning_count"] > 0 else "정상 안정",
            delta_color="inverse" if summary["warning_count"] > 0 else "normal",
        )

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # ----------------------------------------------------
    # 종목 등록 / 수정 폼 (Expander)
    # ----------------------------------------------------
    with st.expander("➕ 보유 종목 등록 및 수정하기", expanded=False):
        st.markdown("##### 📝 종목 정보 입력")
        st.caption("기존에 등록된 티커를 입력하시면 해당 종목의 정보가 업데이트됩니다.")

        form_col1, form_col2 = st.columns(2)
        with form_col1:
            in_ticker = st.text_input("종목 코드 (티커)", placeholder="예: 005930 또는 NVDA", key="in_ticker").strip().upper()
            
            # 실시간 이름 조회 힌트
            preview_info = get_current_stock_price(in_ticker) if in_ticker else None
            default_name = preview_info.get("name", "") if preview_info else ""
            in_name = st.text_input("종목명", value=default_name, placeholder="예: 삼성전자", key="in_name")
            
            in_currency = st.selectbox("통화 단위", options=["KRW", "USD"], index=0 if (preview_info and preview_info.get("currency") == "KRW") else 1)
            in_market = st.selectbox("시장 구분", options=["KRX", "US"], index=0 if in_currency == "KRW" else 1)

        with form_col2:
            in_buy_price = st.number_input("매수 단가", min_value=0.01, value=70000.0 if in_currency == "KRW" else 100.0, step=100.0 if in_currency == "KRW" else 0.5)
            in_qty = st.number_input("보유 수량", min_value=0.01, value=10.0, step=1.0)
            in_target = st.number_input("목표가 (선택)", min_value=0.0, value=0.0, step=100.0 if in_currency == "KRW" else 1.0)
            in_stop = st.number_input("손절가 (선택)", min_value=0.0, value=0.0, step=100.0 if in_currency == "KRW" else 1.0)

        in_memo = st.text_input("투자 메모", placeholder="예: 실적 개선 기대감, 분할 매수 진행 등")

        if st.button("💾 종목 저장하기", type="primary", use_container_width=True):
            if not in_ticker:
                st.error("종목 코드(티커)를 반드시 입력해야 합니다.")
            else:
                new_item = {
                    "ticker": in_ticker,
                    "name": in_name if in_name else in_ticker,
                    "market": in_market,
                    "currency": in_currency,
                    "buy_price": in_buy_price,
                    "quantity": in_qty,
                    "target_price": in_target if in_target > 0 else None,
                    "stop_loss_price": in_stop if in_stop > 0 else None,
                    "memo": in_memo,
                }
                add_or_update_holding(current_user, new_item)
                st.success(f"종목 [{in_ticker}] 저장 완료!")
                st.rerun()

    # ----------------------------------------------------
    # 보유 종목 상세 및 평가손익 계산 테이블
    # ----------------------------------------------------
    st.subheader("📋 보유 종목 현황 및 손익 테이블", anchor=False)

    if not rows:
        st.info("등록된 보유 종목이 없습니다. 위의 '보유 종목 등록 및 수정하기' 버튼을 눌러 첫 종목을 추가해보세요.")
    else:
        # 반응형 카드 및 표 형태로 제공
        tab_table, tab_cards = st.tabs(["📊 상세 테이블 뷰", "📱 카드형 요약 뷰 (모바일 최적화)"])

        with tab_table:
            # Pandas 테이블 가공
            display_rows = []
            for r in rows:
                p_sign = "+" if r["profit_loss"] >= 0 else ""
                curr_symbol = "₩" if r["currency"] == "KRW" else "$"
                
                # 손절가 경고 표시
                status_badge = "🚨 손절 경고" if r["is_stop_loss_triggered"] else ("🎯 목표 근접" if r["target_progress"] and r["target_progress"] >= 95 else "정상")

                display_rows.append({
                    "종목코드": r["ticker"],
                    "종목명": r["name"],
                    "보유수량": f"{r['quantity']:,.2f}".rstrip("0").rstrip("."),
                    "매수단가": f"{curr_symbol}{r['buy_price']:,.2f}",
                    "현재가": f"{curr_symbol}{r['current_price']:,.2f}",
                    "평가금액": f"{curr_symbol}{r['eval_amount']:,.0f}" if r["currency"] == "KRW" else f"{curr_symbol}{r['eval_amount']:,.2f}",
                    "평가손익": f"{curr_symbol}{p_sign}{r['profit_loss']:,.0f}" if r["currency"] == "KRW" else f"{curr_symbol}{p_sign}{r['profit_loss']:,.2f}",
                    "수익률(%)": f"{p_sign}{r['return_pct']:.2f}%",
                    "목표가": f"{curr_symbol}{r['target_price']:,.2f}" if r["target_price"] else "-",
                    "손절가": f"{curr_symbol}{r['stop_loss_price']:,.2f}" if r["stop_loss_price"] else "-",
                    "상태": status_badge,
                })

            df_display = pd.DataFrame(display_rows)
            st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True,
            )

        with tab_cards:
            for r in rows:
                with st.container(border=True):
                    card_col1, card_col2, card_col3 = st.columns([2, 2, 1])
                    curr_symbol = "₩" if r["currency"] == "KRW" else "$"
                    p_color = "text-up" if r["profit_loss"] >= 0 else "text-down"
                    p_sign = "+" if r["profit_loss"] >= 0 else ""

                    with card_col1:
                        st.markdown(f"**{r['name']}** (`{r['ticker']}`)")
                        st.caption(f"수량: {r['quantity']}주 | 매수가: {curr_symbol}{r['buy_price']:,}")
                        if r["memo"]:
                            st.caption(f"💬 {r['memo']}")

                    with card_col2:
                        st.markdown(f"현재가: **{curr_symbol}{r['current_price']:,}**")
                        st.markdown(f"<span class='{p_color}' style='font-weight:700;'>수익률: {p_sign}{r['return_pct']:.2f}% ({curr_symbol}{p_sign}{r['profit_loss']:,})</span>", unsafe_allow_html=True)
                        if r["is_stop_loss_triggered"]:
                            st.error(f"🚨 손절가({curr_symbol}{r['stop_loss_price']:,}) 도달 경고!", icon="⚠️")

                    with card_col3:
                        if st.button("🗑️ 삭제", key=f"del_{r['ticker']}", use_container_width=True):
                            delete_holding(current_user, r["ticker"])
                            st.warning(f"{r['ticker']} 종목이 삭제되었습니다.")
                            st.rerun()

        # 삭제 관리 섹션
        with st.expander("🗑️ 종목 개별 삭제"):
            ticker_list = [r["ticker"] for r in rows]
            del_target = st.selectbox("삭제할 종목 선택", options=ticker_list, key="sel_del_target")
            if st.button("선택 종목 삭제 실행", type="secondary"):
                if delete_holding(current_user, del_target):
                    st.success(f"{del_target} 종목이 성공적으로 삭제되었습니다.")
                    st.rerun()

    st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)

    # ----------------------------------------------------
    # 하단: 보유 종목 관련 최신 뉴스/공시 헤드라인 표시 영역
    # ----------------------------------------------------
    st.subheader("📰 보유 종목 관련 최신 뉴스 & DART 공시 헤드라인", anchor=False)
    st.caption("💡 포트폴리오에 등록된 종목들을 대상으로 금융감독원 전자공시(DART) 및 최신 주요 언론사 뉴스를 실시간 매칭합니다.")

    active_tickers = [r["ticker"] for r in rows]
    news_items = get_holdings_news_and_disclosures(active_tickers)

    if not news_items:
        st.info("현재 보유 종목과 관련된 최신 공시나 뉴스가 없습니다.")
    else:
        for news in news_items:
            is_dart = "DART" in news["type"]
            badge_class = "feed-badge-dart" if is_dart else "feed-badge-news"

            st.markdown(f"""
            <div class="feed-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                    <div>
                        <span class="{badge_class}">{news['type']}</span>
                        <span style="font-weight: 700; color: #f1f5f9; margin-left: 6px; font-size: 0.88rem;">{news['name']} ({news['ticker']})</span>
                        <span style="font-size: 0.78rem; color: #94a3b8; margin-left: 8px;">[{news['category']}]</span>
                    </div>
                    <div style="font-size: 0.78rem; color: #64748b;">
                        🕒 {news['date']} · {news['source']}
                    </div>
                </div>
                <div style="font-size: 0.95rem; font-weight: 600; color: #f8fafc; margin-bottom: 0.25rem;">
                    <a href="{news['url']}" target="_blank" style="text-decoration: none; color: #f8fafc;">{news['title']} ↗</a>
                </div>
            </div>
            """, unsafe_allow_html=True)


if __name__ == "__main__":
    show_portfolio_page()
