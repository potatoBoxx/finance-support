import os
import pytest
from app import ensure_session_state

class MockSessionState(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value

def test_ensure_session_state_sets_defaults(monkeypatch):
    mock_state = MockSessionState()
    import streamlit as st
    monkeypatch.setattr(st, "session_state", mock_state)

    ensure_session_state()
    assert "user" in mock_state
    assert mock_state["user"] is None
    assert mock_state["authenticated"] is False
    assert mock_state["portfolio_items"] == []
    assert mock_state["is_demo_mode"] is False

def test_pages_files_exist():
    assert os.path.exists("pages/1_시장_브리핑.py")
    assert os.path.exists("pages/2_포트폴리오.py")
    assert os.path.exists("app.py")
    assert os.path.exists("assets/style.css")


def test_ai_comment_styles_exist():
    with open("assets/style.css", "r", encoding="utf-8") as f:
        content = f.read()
    assert ".ai-comment-box" in content
    assert ".ai-badge" in content
    assert ".ai-badge.buy" in content
    assert ".ai-badge.hold" in content
    assert ".ai-badge.sell" in content
    assert "#portfolio-top" in content
    assert "scroll-behavior: smooth;" in content


def test_portfolio_feedback_ux_elements():
    with open("pages/2_포트폴리오.py", "r", encoding="utf-8") as f:
        code = f.read()
    assert 'portfolio-top' in code
    assert 'pending_toast' in code
    assert 'portfolio_active_tab' in code
    assert 'portfolio_summary_tabs' in code
    assert 'add_expander_expanded' in code
    assert 'scroll_to_top' in code
    assert 'portfolio-news-item' in code
    assert 'portfolio-news-main' in code
    assert 'portfolio-news-link' in code
    assert 'portfolio-news-meta' in code
    assert 'inject_tab_lock_and_loading_script' in code
    assert 'tab-switching' in code
    assert 'fin-tab-loading-toast' in code


def test_landing_page_and_copy_ux():
    with open("app.py", "r", encoding="utf-8") as f:
        app_code = f.read()
    assert "@st.cache_data" not in app_code
    assert "오늘의 시장 브리핑 & 추천 종목" in app_code
    assert "스마트 포트폴리오 관리" in app_code
    assert "초고속 인메모리 캐시" in app_code
    assert "Supabase 클라우드 영구 보존" in app_code
    assert "완벽한 모바일 반응형 뷰" in app_code

    with open("assets/style.css", "r", encoding="utf-8") as f:
        css = f.read()
    assert "padding-top: 3.8rem !important;" in css
    assert "word-break: keep-all !important;" in css
    assert "letter-spacing: -0.5px !important;" in css
    assert ".portfolio-news-item" in css
    assert "flex-direction: column !important;" in css
    assert ".badge-copy-tag" in css
    assert ".ticker-badge" in css
    assert "body.tab-switching" in css
    assert ".fin-tab-loading-toast" in css

    with open("pages/1_시장_브리핑.py", "r", encoding="utf-8") as f:
        briefing_code = f.read()
    assert "ticker-badge" in briefing_code
    assert "navigator.clipboard.writeText" in briefing_code
    assert "✅ 복사됨!" in briefing_code
    assert "user-select: all" in briefing_code
    assert "btn_copy_top3" not in briefing_code
    assert 'title="' not in briefing_code
    assert "onclick=" not in briefing_code
    assert ";c.appendChild" not in briefing_code

    with open("pages/2_포트폴리오.py", "r", encoding="utf-8") as f:
        port_code = f.read()
    # 확인 마커 완전 제거 및 통화 실시간 입력 검증
    assert "입력 확인:" not in port_code
    assert "평단가 확인:" not in port_code
    assert "목표가 확인:" not in port_code
    assert "손절가 확인:" not in port_code
    assert "render_currency_input" in port_code


def test_number_input_and_memo_improvements():
    with open("pages/2_포트폴리오.py", "r", encoding="utf-8") as f:
        port_code = f.read()
    assert "inject_number_input_enhancer_script" in port_code
    assert "finscope-number-overlay" in port_code
    assert "formatWithComma" in port_code
    assert "curr_memo" in port_code
    assert 'in ("None", "nan", "NaN", "null", "")' in port_code
    assert "inject_currency_input_script" in port_code

    with open("assets/style.css", "r", encoding="utf-8") as f:
        css = f.read()
    assert ".finscope-number-overlay" in css


def test_stock_reload_dialog_and_reset_logic():
    with open("pages/2_포트폴리오.py", "r", encoding="utf-8") as f:
        port_code = f.read()
    assert "confirm_stock_reload_dialog" in port_code
    assert "has_unsaved_registration_inputs" in port_code
    assert "apply_new_stock_and_reset_form" in port_code
    assert "@st.dialog" in port_code
    assert "reg_in_buy_price" in port_code
    assert "reg_buy_price" in port_code
    assert "current_price" in port_code
    assert "reg_in_quantity" in port_code
    assert "reg_in_memo" in port_code
    assert "dlg_btn_confirm_reload" in port_code
    assert "dlg_btn_cancel_reload" in port_code
    assert "입력 초기화" in port_code


def test_account_management_dialog_elements():
    with open("pages/2_포트폴리오.py", "r", encoding="utf-8") as f:
        code = f.read()
    assert "manage_accounts_dialog" in code
    assert "repo.get_accounts" in code
    assert "repo.create_account" in code
    assert "calculate_isa_default_maturity" in code
    assert "➕ 계좌 관리" in code

def test_isa_dday_and_tax_advice_ui():
    with open("pages/2_포트폴리오.py", "r", encoding="utf-8") as f:
        code = f.read()
    assert "calculate_isa_dday" in code
    assert "evaluate_isa_tax_advice" in code
    assert "ISA 만기" in code
    assert "badge-tag" in code


def test_morning_briefing_expander_ui():
    with open("pages/2_포트폴리오.py", "r", encoding="utf-8") as f:
        code = f.read()
    assert "오늘의 포트폴리오 종합 AI 진단" in code
    assert "portfolio_ai_expanded" in code
    assert "generate_daily_portfolio_briefing" in code
    assert "refresh_daily_briefing_btn" in code
    assert "get_daily_briefing" in code
    assert "save_daily_briefing" in code


def test_mobile_landscape_table_optimization():
    with open("pages/2_포트폴리오.py", "r", encoding="utf-8") as f:
        port_code = f.read()
    assert "btn_enter_table_landscape" in port_code
    assert "editor_landscape_mode" in port_code
    assert "render_landscape_editor_view" in port_code
    assert "landscape_portfolio_data_editor" in port_code
    assert "btn_exit_landscape_mode" in port_code
    assert "btn_save_landscape_editor" in port_code
    assert "requestFullscreen" in port_code
    assert "orientation.lock" in port_code
    assert "landscape_quick_editor_dialog" not in port_code
    assert "0이면 해제" not in port_code

    idx_def = port_code.index("def render_landscape_editor_view")
    call_str = 'if st.session_state.get("editor_landscape_mode", False):\n    render_landscape_editor_view('
    idx_call = port_code.index(call_str)
    assert idx_def < idx_call, "render_landscape_editor_view must be defined before it is called"

    with open("assets/style.css", "r", encoding="utf-8") as f:
        css = f.read()
    assert ".st-key-btn_enter_table_landscape" in css
    assert "st-key-landscape_editor_sticky_header" in css
    assert "st-key-landscape_portfolio_data_editor" in css
    assert "rotate(90deg)" not in css



def test_confirm_delete_stock_dialog_ui():
    with open("pages/2_포트폴리오.py", "r", encoding="utf-8") as f:
        port_code = f.read()
    assert "confirm_delete_stock_dialog" in port_code
    assert "⚠️ 종목 삭제 확인" in port_code
    assert "dlg_cancel_del_" in port_code
    assert "dlg_confirm_del_" in port_code
    assert "삭제된 종목과 거래 기록은 복구되지 않습니다" in port_code

    with open("assets/style.css", "r", encoding="utf-8") as f:
        css = f.read()
    assert "st-key-dlg_confirm_del_" in css
    assert "st-key-dlg_cancel_del_" in css


def test_mobile_portfolio_edit_form_and_font_optimization():
    with open("pages/2_포트폴리오.py", "r", encoding="utf-8") as f:
        port_code = f.read()
    assert "portfolio_edit_expander" in port_code
    assert 'on_change="rerun"' in port_code
    assert "on_mobile_stock_change" in port_code
    assert "selected-stock-name" in port_code

    with open("assets/style.css", "r", encoding="utf-8") as f:
        css = f.read()
    assert ".st-key-mobile_target_stock" in css
    assert "selected-stock-name" in css
    assert "data-baseweb=\"popover\"" in css






