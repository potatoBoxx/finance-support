"""
포트폴리오 평가손익, 수익률 계산 및 손절가 경고 비즈니스 로직 서비스
"""
import logging
from datetime import date, datetime
from typing import Optional, Any
import pandas as pd

from services.npay_service import fetch_npay_items

logger = logging.getLogger(__name__)


def get_live_price_map(items: list[dict], cached_dfs: Optional[list[pd.DataFrame]] = None) -> dict[str, float]:
    """
    포트폴리오 종목 리스트의 티커를 기준으로 실시간 현재가 맵을 생성합니다.
    1. 인메모리 Npay 캐시 DataFrame에서 우선 탐색
    2. 미발견 종목은 yfinance 조회 또는 종목 매수가 기반 현실적 fallback 매핑
    """
    price_map: dict[str, float] = {}
    if not items:
        return price_map

    # 1. Npay 캐시 데이터프레임에서 빠른 색인
    lookup_dfs = cached_dfs or []
    if not lookup_dfs:
        try:
            krx_df = fetch_npay_items("KRX")
            us_df = fetch_npay_items("US")
            lookup_dfs = [krx_df, us_df]
        except Exception as e:
            logger.warning(f"Failed to fetch npay items for price lookup: {e}")

    npay_dict = {}
    for df in lookup_dfs:
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                t = str(row["ticker"]).strip().upper()
                p = float(row["current_price"])
                if t and p > 0:
                    npay_dict[t] = p

    # 2. 각 종목 현재가 매핑 (Npay 캐시 우선)
    missing_items = []
    for item in items:
        ticker = str(item.get("ticker", "")).strip().upper()
        if not ticker:
            continue

        if ticker in npay_dict:
            price_map[ticker] = npay_dict[ticker]
        else:
            missing_items.append(item)

    # 3. Npay Top 100 미포함 종목에 대한 네이버 증권/해외 API (stock_search_service) 우선 실시간 조회
    still_missing = []
    if missing_items:
        try:
            from services.stock_search_service import search_stock_by_ticker_or_name
            for it in missing_items:
                t = str(it.get("ticker", "")).strip().upper()
                m = str(it.get("market", "")).strip().upper() or None
                nm = str(it.get("name", "")).strip() or None
                found = None
                try:
                    found = search_stock_by_ticker_or_name(t, market=m)
                    if not found and nm:
                        found = search_stock_by_ticker_or_name(nm, market=m)
                except Exception as e:
                    logger.debug(f"stock_search_service lookup failed for {t}: {e}")

                if found and float(found.get("current_price") or found.get("price") or 0.0) > 0:
                    price_map[t] = float(found.get("current_price") or found.get("price"))
                else:
                    still_missing.append(it)
        except Exception as e:
            logger.debug(f"stock_search_service import/lookup error: {e}")
            still_missing = missing_items

    # 4. 여전히 미발견된 종목에 대한 yfinance 조회 (필요 시 보조 조회)
    if still_missing:
        try:
            import yfinance as yf
            # 쉼표 구분 티커 일괄 조회
            yf_symbols = []
            for it in still_missing:
                t = str(it.get("ticker", "")).strip().upper()
                m = str(it.get("market", "")).strip().upper()
                if m == "KRX" or (t.isdigit() and len(t) == 6):
                    yf_symbols.append(f"{t}.KS")
                else:
                    yf_symbols.append(t)
            
            if yf_symbols:
                data = yf.download(yf_symbols, period="1d", interval="1d", progress=False, timeout=4)
                close_df = data["Close"] if "Close" in data else None
                if close_df is not None and not close_df.empty:
                    for it, yf_t in zip(still_missing, yf_symbols):
                        orig_t = str(it.get("ticker", "")).strip().upper()
                        if yf_t in close_df.columns:
                            val = close_df[yf_t].dropna()
                            if len(val) > 0:
                                price_map[orig_t] = round(float(val.iloc[-1]), 2)
        except Exception as e:
            logger.debug(f"yfinance missing ticker fetch skipped: {e}")

    # 5. 여전히 현재가가 없는 경우 매수가 기준 안전한 Fallback 매핑
    for item in items:
        ticker = str(item.get("ticker", "")).strip().upper()
        if ticker and ticker not in price_map:
            price_map[ticker] = float(item.get("buy_price", 0.0))

    return price_map


def format_quantity(qty: float) -> str:
    """수량 표시 정리: 15.0 -> '15주', 1.25 -> '1.25주' (불필요한 .0000 제거, 최대 4자리)"""
    q_rounded = round(float(qty), 4)
    if q_rounded == int(q_rounded):
        return f"{int(q_rounded)}주"
    # 소수점 끝의 불필요한 0 제거
    formatted = f"{q_rounded:.4f}".rstrip("0").rstrip(".")
    return f"{formatted}주"


def format_won_compact(val: float, is_signed: bool = False, prefix_approx: bool = False) -> str:
    """
    원화 금액을 한국어 직관적 단위(억원, 만원, 원)로 컴팩트하게 변환합니다.
    - 1억원 이상: 1.2억원
    - 1,000만원 이상: 448만원 (소수점 생략으로 간결화)
    - 1만원 이상: 32.2만원, 44.8만원
    - 1만원 미만: 9,800원
    """
    abs_v = abs(float(val))
    sign = ("+" if val > 0 else ("-" if val < 0 else "")) if is_signed else ""
    prefix = "약 " if prefix_approx else ""

    if abs_v >= 100_000_000:
        won_str = f"{abs_v / 100_000_000:,.1f}억원"
    elif abs_v >= 10_000:
        man_val = abs_v / 10_000
        if man_val >= 100 or abs_v % 10_000 == 0:
            won_str = f"{man_val:,.0f}만원"
        else:
            won_str = f"{man_val:,.1f}만원"
    else:
        won_str = f"{abs_v:,.0f}원"

    return f"{prefix}{sign}{won_str}"


def calculate_rebalanced_position(
    action: str,
    current_qty: float,
    current_buy_price: float,
    trade_qty: float,
    trade_price: float
) -> tuple[float, float, str]:
    """
    특정 종목의 추가 매수(물타기/불타기) 또는 부분 매도 시 신규 보유 수량 및 개정 평단가를 산출합니다.
    - BUY (추가 매수):
      신규 수량 = current_qty + trade_qty
      신규 평단가 = (current_qty * current_buy_price + trade_qty * trade_price) / 신규 수량
    - SELL (부분 매도):
      신규 수량 = max(0.0, current_qty - trade_qty)
      신규 평단가 = current_buy_price (보유 평단가는 유지)
    """
    if current_qty < 0 or current_buy_price < 0 or trade_qty <= 0 or trade_price < 0:
        return current_qty, current_buy_price, "유효한 수량과 단가를 입력해주세요."

    if action.upper() == "BUY":
        new_qty = current_qty + trade_qty
        total_spent = (current_qty * current_buy_price) + (trade_qty * trade_price)
        new_price = total_spent / new_qty if new_qty > 0 else 0.0
        price_diff = new_price - current_buy_price
        diff_str = f"평단가 {price_diff:+,.1f} 변동" if price_diff != 0 else "평단가 동일"
        msg = f"추가 매수 완료: 신규 평단가 {new_price:,.1f} / 보유 {new_qty:g}주 ({diff_str})"
        return round(new_qty, 4), round(new_price, 2), msg
    else:  # SELL
        new_qty = max(0.0, current_qty - trade_qty)
        msg = f"부분 매도 완료: 잔여 {new_qty:g}주 (평단가 {current_buy_price:,.1f} 유지)"
        return round(new_qty, 4), round(current_buy_price, 2), msg


def is_valid_price(val: Any) -> bool:
    """
    목표가/손절가 등의 유효성을 검사합니다.
    None, np.nan, pd.isna(), 문자열 'nan'/'none', 0 이하 등은 유효하지 않음(False)으로 판정합니다.
    """
    if val is None or pd.isna(val):
        return False
    if isinstance(val, str):
        val_str = val.strip().lower()
        if val_str in ("", "none", "nan", "null"):
            return False
        try:
            val = float(val)
        except (ValueError, TypeError):
            return False
    try:
        val_float = float(val)
        return not (pd.isna(val_float) or val_float <= 0)
    except (ValueError, TypeError):
        return False


def calculate_target_recommendations(row: dict | pd.Series) -> dict[str, Any]:
    """
    보유 종목에 대한 실시간 기준 매수 추천가(단기 지지선 눌림목) 및 매도 추천가(목표가/저항선)를 산출합니다.
    - 추가 매수 추천가: 현재가 대비 -4% 눌림목 지지선 (KRX는 호가 단위 반올림)
    - 분할 매도 추천가: 사용자가 설정한 목표가(현재가보다 높을 경우) 또는 현재가 대비 +8% 단기 저항선
    """
    market = str(row.get("market", "KRX")).upper()
    curr_price = float(row.get("current_price", 0.0))
    if curr_price <= 0:
        curr_price = float(row.get("buy_price", 0.0))

    raw_target = row.get("target_price")
    user_target = float(raw_target) if is_valid_price(raw_target) else 0.0

    # 1. 추가 매수 추천가 (-4% 눌림목 지지선)
    raw_buy = curr_price * 0.96
    if market == "KRX":
        if raw_buy >= 100000:
            recom_buy = round(raw_buy, -2)
        elif raw_buy >= 1000:
            recom_buy = round(raw_buy, -1)
        else:
            recom_buy = round(raw_buy)
        buy_str = f"{recom_buy:,.0f}원"
    else:
        recom_buy = round(raw_buy, 2)
        buy_str = f"${recom_buy:,.2f}"

    buy_reason = "단기 지지선 (-4%)"

    # 2. 분할 매도 추천가 (목표가 or +8% 저항선)
    if user_target > 0 and user_target > curr_price:
        recom_sell = user_target
        diff_pct = ((user_target - curr_price) / curr_price) * 100
        sell_reason = f"설정 목표가 (+{diff_pct:.1f}%)"
    else:
        raw_sell = curr_price * 1.08
        if market == "KRX":
            if raw_sell >= 100000:
                recom_sell = round(raw_sell, -2)
            elif raw_sell >= 1000:
                recom_sell = round(raw_sell, -1)
            else:
                recom_sell = round(raw_sell)
        else:
            recom_sell = round(raw_sell, 2)
        sell_reason = "단기 저항선 (+8%)"

    if market == "KRX":
        sell_str = f"{recom_sell:,.0f}원"
    else:
        sell_str = f"${recom_sell:,.2f}"

    return {
        "recom_buy_price": recom_buy,
        "recom_buy_display": buy_str,
        "buy_reason": buy_reason,
        "recom_sell_price": recom_sell,
        "recom_sell_display": sell_str,
        "sell_reason": sell_reason,
    }


def generate_ai_comment(
    item: dict | pd.Series,
    news_list: Optional[list[dict[str, str]]] = None
) -> dict[str, str]:
    """
    보유 종목의 수익률, 손절/목표가 상태 및 최신 뉴스/공시 헤드라인을 분석하여
    규칙 기반(Rule-based)의 실시간 '종목별 AI 한줄평' 및 포지션 판단 배지를 생성합니다.
    """
    ticker = str(item.get("ticker", "")).strip().upper()
    profit_rate = float(item.get("profit_rate", 0.0))
    is_stop_loss = bool(item.get("is_stop_loss", False))
    curr_price = float(item.get("current_price", 0.0))
    target_price = float(item["target_price"]) if is_valid_price(item.get("target_price")) else 0.0

    # 1. 해당 종목 관련 최신 뉴스 검색 및 키워드 추출
    matched_news = []
    if news_list:
        clean_news = [n for n in news_list if str(n.get("ticker", "")).strip().upper() == ticker]
        if clean_news:
            matched_news = clean_news

    news_context = ""
    if matched_news:
        first_title = matched_news[0].get("title", "").strip()
        cleaned_title = first_title.replace("[공시]", "").replace("속보:", "").strip()
        
        # 주요 핵심 키워드 매칭
        key_terms = ["HBM", "실적", "배당", "공급", "양산", "AI", "수주", "계약", "신제품", "FSD", "투자", "칩셋", "메모리", "자사주"]
        found_terms = [term for term in key_terms if term in cleaned_title]
        
        if found_terms:
            terms_str = "/".join(found_terms[:2])
            news_context = f"{terms_str} 호재 모멘텀 반영 중. "
        else:
            short_title = cleaned_title[:24] + ("..." if len(cleaned_title) > 24 else "")
            news_context = f"최근 '{short_title}' 이슈 주목. "

    # 2. 포지션 판정 및 코멘트 조합
    # A. 손절가 도달 또는 -5% 이하 급락 구간 (리스크 관리)
    if is_stop_loss or profit_rate <= -5.0:
        badge = "🚨 리스크 관리"
        badge_type = "danger"
        if is_stop_loss:
            comment = f"{news_context}설정 손절가 하회로 하방 압력 지속. 추가 하락 방어를 위한 비중 축소 및 리스크 관리 권고."
        else:
            comment = f"{news_context}단기 지지선 이탈 주의 구간. 무리한 물타기 지양 및 리스크 관리 우선 필요."

    # B. 고수익 구간 (+8% 이상) 또는 목표가 근접 (95% 이상 도달)
    elif profit_rate >= 8.0 or (target_price > 0 and curr_price >= target_price * 0.95):
        badge = "🔴 분할 익절(매도)"
        badge_type = "sell"
        if target_price > 0 and curr_price >= target_price * 0.95:
            comment = f"{news_context}설정 목표가 근접 도달. 차익실현 매물 출회 가능성에 대비해 비중 20~30% 분할 매도 고려."
        else:
            comment = f"{news_context}단기 저항선 도달 및 차익실현 구간. 수익 보전을 위한 분할 매도 검토."

    # C. 단기 눌림목 / 지지선 부근 (-4% ~ +1% 미만)
    elif -4.0 <= profit_rate < 1.0:
        badge = "🟢 매수 고려"
        badge_type = "buy"
        comment = f"{news_context}단기 지지선 눌림목 반등 테스트 구간. 분할 매수 관점 유효."

    # D. 그 외 안정적 추세 구간 (+1% ~ +8% 미만)
    else:
        badge = "🟡 홀딩(유지)"
        badge_type = "hold"
        comment = f"{news_context}주요 이평선 및 지지선 위에서 안정적 추세 지속 중. 추가 상승 여력 홀딩 유지."

    return {
        "badge": badge,
        "badge_type": badge_type,
        "comment": comment
    }


def calculate_portfolio_performance(
    items: list[dict],
    price_map: dict[str, float],
    usd_krw_rate: float = 1345.0
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    보유 종목 리스트와 현재가 맵을 전달받아 개별 평가손익과 포트폴리오 총계 메트릭을 계산합니다.
    - 미국(US) 종목은 달러($), 국내(KRX) 종목은 원(원) 단위로 분리 계산
    - 포트폴리오 전체 요약(원금, 평가금, 손익)은 환율(usd_krw_rate)을 적용하여 원화로 통합 합산
    """
    if not items:
        empty_df = pd.DataFrame(columns=[
            "id", "account", "market", "currency", "ticker", "name", "buy_price", "quantity",
            "quantity_display", "current_price", "eval_amount", "eval_profit", "profit_rate",
            "target_price", "target_rate", "stop_loss_price", "is_stop_loss", "memo",
            "eval_amount_won", "eval_profit_won"
        ])
        summary = {
            "total_invested": 0.0,
            "total_eval": 0.0,
            "total_profit": 0.0,
            "total_profit_rate": 0.0,
            "item_count": 0,
            "stop_loss_count": 0,
            "usd_krw_rate": usd_krw_rate,
        }
        return empty_df, summary

    rows = []
    total_invested_won = 0.0
    total_eval_won = 0.0
    stop_loss_count = 0

    for item in items:
        ticker = str(item.get("ticker", "")).strip().upper()
        name = str(item.get("name", ticker))
        market = str(item.get("market", "KRX")).upper()
        buy_price = float(item.get("buy_price", 0.0))
        quantity = float(item.get("quantity", 0.0))
        target_price = float(item["target_price"]) if is_valid_price(item.get("target_price")) else None
        stop_loss_price = float(item["stop_loss_price"]) if is_valid_price(item.get("stop_loss_price")) else None
        memo = item.get("memo")

        # 통화 구분
        currency = "$" if market == "US" else "원"
        fx = usd_krw_rate if market == "US" else 1.0

        # 현재가 매핑 (없을 시 매수가 폴백)
        current_price = float(price_map.get(ticker, buy_price))

        # 개별 종목 통화 기준 금액
        invested_origin = buy_price * quantity
        eval_amount_origin = current_price * quantity
        eval_profit_origin = eval_amount_origin - invested_origin
        profit_rate = ((current_price - buy_price) / buy_price * 100.0) if buy_price > 0 else 0.0

        # 원화 환산 금액 (포트폴리오 총계용)
        invested_won = invested_origin * fx
        eval_won = eval_amount_origin * fx
        eval_profit_won = eval_profit_origin * fx

        # 목표가 달성률 (%)
        target_rate = ((current_price / target_price) * 100.0) if target_price and target_price > 0 else None

        # 🚨 손절가 경고 판정: 현재가가 설정한 손절가 이하로 하락 시 True
        is_stop_loss = bool(stop_loss_price and stop_loss_price > 0 and current_price <= stop_loss_price)
        if is_stop_loss:
            stop_loss_count += 1

        total_invested_won += invested_won
        total_eval_won += eval_won

        rows.append({
            "id": item.get("id"),
            "account": str(item.get("account") or "기본").strip(),
            "market": market,
            "currency": currency,
            "ticker": ticker,
            "name": name,
            "buy_price": buy_price,
            "quantity": quantity,
            "quantity_display": format_quantity(quantity),
            "current_price": round(current_price, 2) if market == "US" else round(current_price),
            "eval_amount": round(eval_amount_origin, 2) if market == "US" else round(eval_amount_origin),
            "eval_profit": round(eval_profit_origin, 2) if market == "US" else round(eval_profit_origin),
            "profit_rate": round(profit_rate, 2),
            "target_price": target_price,
            "target_rate": round(target_rate, 1) if target_rate is not None else None,
            "stop_loss_price": stop_loss_price,
            "is_stop_loss": is_stop_loss,
            "memo": memo,
            "eval_amount_won": round(eval_won),
            "eval_profit_won": round(eval_profit_won)
        })

    result_df = pd.DataFrame(rows)
    total_profit_won = total_eval_won - total_invested_won
    total_profit_rate = (total_profit_won / total_invested_won * 100.0) if total_invested_won > 0 else 0.0

    summary = {
        "total_invested": round(total_invested_won),
        "total_eval": round(total_eval_won),
        "total_profit": round(total_profit_won),
        "total_profit_rate": round(total_profit_rate, 2),
        "item_count": len(items),
        "stop_loss_count": stop_loss_count,
        "usd_krw_rate": usd_krw_rate
    }

    return result_df, summary


# ==============================================================================
# ISA 계좌 만기 계산 및 절세 AI 룰 엔진
# ==============================================================================
from datetime import date, datetime


def calculate_isa_default_maturity(opened_at: Any) -> date:
    """
    ISA 개설일 기준 의무 보유 기본 만기일(+3년)을 계산합니다.
    윤년(2월 29일)인 경우 2월 28일로 보정합니다.
    """
    if isinstance(opened_at, str):
        opened_date = datetime.strptime(opened_at[:10], "%Y-%m-%d").date()
    elif isinstance(opened_at, datetime):
        opened_date = opened_at.date()
    elif isinstance(opened_at, date):
        opened_date = opened_at
    else:
        opened_date = date.today()

    try:
        return opened_date.replace(year=opened_date.year + 3)
    except ValueError:
        # 2월 29일 윤년 처리
        return date(opened_date.year + 3, opened_date.month, 28)


def calculate_isa_dday(
    maturity_at: Any,
    base_date: Optional[date] = None
) -> Optional[dict[str, Any]]:
    """
    ISA 만기일 기준 D-Day 및 만기 상태를 계산합니다.
    - D-Day > 0: 만기 전 (active, D-180)
    - D-Day == 0: 오늘 만기 (due, D-Day)
    - D-Day < 0: 만기 경과 (expired, D+30)
    """
    if not maturity_at:
        return None

    if isinstance(maturity_at, str):
        clean_mat = maturity_at.strip()
        if not clean_mat or clean_mat in ("None", "nan", "-"):
            return None
        mat_date = datetime.strptime(clean_mat[:10], "%Y-%m-%d").date()
    elif isinstance(maturity_at, datetime):
        mat_date = maturity_at.date()
    elif isinstance(maturity_at, date):
        mat_date = maturity_at
    else:
        return None

    today = base_date or date.today()
    diff_days = (mat_date - today).days

    if diff_days > 0:
        label = f"D-{diff_days}"
        status = "active"
        badge_color = "#3b82f6"
        message = f"만기까지 {diff_days}일 남았습니다."
    elif diff_days == 0:
        label = "D-Day"
        status = "due"
        badge_color = "#f59e0b"
        message = "오늘이 ISA 계좌 만기일입니다!"
    else:
        label = f"D+{abs(diff_days)}"
        status = "expired"
        badge_color = "#ef4444"
        message = f"만기일로부터 {abs(diff_days)}일이 경과했습니다."

    return {
        "d_day": diff_days,
        "label": label,
        "status": status,
        "badge_color": badge_color,
        "message": message,
        "maturity_date": mat_date.isoformat()
    }


def evaluate_isa_tax_advice(
    account: dict,
    summary: dict
) -> Optional[dict[str, Any]]:
    """
    ISA 계좌에 대한 연금계좌 전환 세액공제(조세특례제한법) 절세 혜택을 평가합니다.
    전환 금액의 10%(최대 300만 원) 추가 세액공제 혜택 산출.
    """
    if not account or str(account.get("account_type", "")).strip() != "ISA":
        return None

    total_eval = float(summary.get("total_eval", 0) or 0)
    max_deduction = min(total_eval * 0.10, 3_000_000.0)

    broker = account.get("broker_name", "ISA")
    alias = account.get("account_alias") or "ISA 계좌"

    return {
        "account_id": account.get("id"),
        "broker_name": broker,
        "account_alias": alias,
        "title": "💡 ISA 만기자금 연금계좌 전환 절세 혜택 안내",
        "max_deduction": max_deduction,
        "max_deduction_display": f"{int(max_deduction):,}원",
        "total_eval": total_eval,
        "description": (
            f"ISA 만기 자금을 연금저축/IRP로 전환 납입하면 전환 금액의 10%(최대 300만 원 한도)를 "
            f"기존 연금세액공제 한도(최대 900만 원)와 별도로 추가 세액공제 받을 수 있습니다."
        ),
        "tax_saving_estimate_16_5": int(max_deduction * 0.165),
        "tax_saving_estimate_13_2": int(max_deduction * 0.132),
    }


def generate_daily_portfolio_briefing(
    user_id: str,
    portfolio_items: list[dict],
    accounts: list[dict],
    market_indices: dict,
    price_map: Optional[dict[str, float]] = None,
    briefing_date: Optional[str] = None
) -> dict[str, Any]:
    """
    전체 자산을 아우르는 오늘의 포트폴리오 종합 AI 진단 브리핑을 생성합니다.
    1. 전체 자산 누적 수익률 및 주요 지수(KOSPI, S&P 500) 대비 벤치마크 평가
    2. 계좌 / 절세 현황 (ISA 만기 D-Day, 연금 이전 세액공제 한도, 연금저축/IRP 납입 여력 등)
    3. 포트폴리오 리스크 & 룰 엔진 (손절 경고 종목, 국내 vs 해외 자산 분산 비중, 종합 리스크 배지)
    4. 오늘의 행동 가이드(Action Items)
    """
    today_iso = briefing_date or date.today().isoformat()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    usd_rate = float(market_indices.get("USD/KRW", {}).get("value", 1345.5))
    if price_map is None:
        price_map = get_live_price_map(portfolio_items)

    perf_df, summary = calculate_portfolio_performance(portfolio_items, price_map, usd_krw_rate=usd_rate)

    kospi_info = market_indices.get("KOSPI", {})
    sp500_info = market_indices.get("S&P 500", {})
    kospi_rate = float(kospi_info.get("change_rate", 0.0) or 0.0)
    sp500_rate = float(sp500_info.get("change_rate", 0.0) or 0.0)

    # 1. 벤치마크 비교 & 코멘트
    item_count = summary.get("item_count", 0)
    profit_rate = summary.get("total_profit_rate", 0.0)
    profit_val = summary.get("total_profit", 0.0)
    total_eval = summary.get("total_eval", 0.0)
    total_invested = summary.get("total_invested", 0.0)
    stop_loss_count = summary.get("stop_loss_count", 0)

    if item_count == 0:
        benchmark_comment = "등록된 보유 종목이 없어 포트폴리오 성과 분석이 대기 중입니다. 신규 종목을 등록해보세요."
        benchmark_tag = "분석 대기"
    elif profit_rate > 0:
        if profit_rate > kospi_rate:
            benchmark_comment = f"현재 포트폴리오 수익률은 {profit_rate:+.2f}%로, KOSPI({kospi_rate:+.2f}%) 대비 우수한 초과 성과(알파)를 기록 중입니다."
            benchmark_tag = "시장 대비 선방"
        else:
            benchmark_comment = f"현재 포트폴리오 수익률은 {profit_rate:+.2f}%로, 시장 지수 흐름과 동행하며 순항하고 있습니다."
            benchmark_tag = "시장과 동행"
    else:
        if kospi_rate < 0 and profit_rate > kospi_rate:
            benchmark_comment = f"시장 지수 하락(KOSPI {kospi_rate:+.2f}%) 국면 속에서 상대적 하방 방어력을 보여주고 있습니다."
            benchmark_tag = "방어적 흐름"
        else:
            benchmark_comment = f"현재 포트폴리오 수익률({profit_rate:+.2f}%)이 지수 대비 하회하고 있어 손실 관리 및 보유 비중 점검이 필요합니다."
            benchmark_tag = "변동성 유의"

    # 2. 계좌 / 절세 현황 요약
    isa_accounts = [a for a in accounts if str(a.get("account_type", "")).strip() == "ISA"]
    pension_accounts = [a for a in accounts if str(a.get("account_type", "")).strip() in ("연금저축", "IRP")]

    urgent_isa_list = []
    for isa in isa_accounts:
        mat_at = isa.get("maturity_at")
        if mat_at:
            dday_res = calculate_isa_dday(mat_at)
            if dday_res and (dday_res["status"] in ("due", "expired") or 0 <= dday_res["d_day"] <= 30):
                urgent_isa_list.append({
                    "id": isa.get("id"),
                    "broker_name": isa.get("broker_name"),
                    "account_alias": isa.get("account_alias") or isa.get("broker_name", "ISA"),
                    "dday_label": dday_res["label"],
                    "status": dday_res["status"],
                    "message": dday_res["message"]
                })

    # ISA 자산 평가액 기반 세액공제 한도 산출
    total_isa_eval = 0.0
    if not perf_df.empty:
        isa_ids = {a.get("id") for a in isa_accounts if a.get("id")}
        isa_brokers = {a.get("broker_name") for a in isa_accounts}
        for _, row in perf_df.iterrows():
            if (row.get("account_id") and row.get("account_id") in isa_ids) or (not row.get("account_id") and str(row.get("account", "")).strip() in isa_brokers):
                total_isa_eval += float(row.get("eval_amount_won", 0.0))
    if total_isa_eval == 0.0 and isa_accounts and total_eval > 0:
        total_isa_eval = total_eval * (len(isa_accounts) / max(1, len(accounts)))

    max_isa_deduction = min(total_isa_eval * 0.10, 3_000_000.0) if total_isa_eval > 0 else 3_000_000.0

    if urgent_isa_list:
        has_tax_issue = True
        u = urgent_isa_list[0]
        tax_comment = f"🚨 {u['account_alias']} 계좌의 만기가 임박/경과({u['dday_label']})했습니다. 연금 계좌 전환 시 최대 {int(max_isa_deduction):,}원(10%) 추가 세액공제 혜택을 챙기세요."
    elif isa_accounts:
        has_tax_issue = False
        tax_comment = f"💡 보유 중인 ISA 계좌는 만기 도래 시 연금계좌 전환 납입으로 최대 {int(max_isa_deduction):,}원의 추가 세액공제를 받을 수 있습니다."
    elif pension_accounts:
        has_tax_issue = False
        tax_comment = "📌 등록된 연금저축/IRP 계좌를 활용해 연간 최대 900만 원 한도까지 세액공제(최대 148.5만 원 환급)를 적극 활용하세요."
    else:
        has_tax_issue = False
        tax_comment = "현재 등록된 절세 계좌(ISA/연금) 관련 즉시 조치가 필요한 긴급 만기 일정은 없습니다."

    # 3. 포트폴리오 리스크 & 자산 배분 비중
    krx_eval = float(perf_df[perf_df["market"] == "KRX"]["eval_amount_won"].sum()) if not perf_df.empty and "eval_amount_won" in perf_df.columns else 0.0
    us_eval = float(perf_df[perf_df["market"] == "US"]["eval_amount_won"].sum()) if not perf_df.empty and "eval_amount_won" in perf_df.columns else 0.0
    
    if total_eval > 0:
        krx_ratio = round((krx_eval / total_eval) * 100, 1)
        us_ratio = round((us_eval / total_eval) * 100, 1)
    else:
        krx_ratio, us_ratio = 50.0, 50.0

    if stop_loss_count >= 2 or profit_rate <= -15.0:
        risk_level = "경고"
        risk_color = "#EF4444"
        risk_emoji = "🔴"
        risk_comment = f"손절가 도달 종목이 {stop_loss_count}건 발생했습니다. 추가 손실 확대를 막기 위한 적극적인 비중 축소 및 손절 대응을 권고합니다."
    elif stop_loss_count == 1 or profit_rate <= -5.0 or (total_eval > 0 and (krx_ratio >= 90.0 or us_ratio >= 90.0)):
        risk_level = "주의"
        risk_color = "#F59E0B"
        risk_emoji = "🟡"
        if stop_loss_count == 1:
            risk_comment = "설정 손절가 이하로 하락한 종목이 1건 있습니다. 지지선 이탈 여부와 리스크 관리를 점검하세요."
        elif krx_ratio >= 90.0 or us_ratio >= 90.0:
            dominant = "국내(KRX)" if krx_ratio >= 90.0 else "해외(US)"
            risk_comment = f"{dominant} 주식 비중이 90% 이상으로 극단적 편중 상태입니다. 시장 분산 투자를 검토해보세요."
        else:
            risk_comment = f"포트폴리오 누적 수익률이 {profit_rate:+.2f}%로 조정 구간입니다. 단기 무리한 추가 매수보다 관망을 권장합니다."
    else:
        risk_level = "안정"
        risk_color = "#10B981"
        risk_emoji = "🟢"
        risk_comment = "손절 위험 종목이 0건이며, 포트폴리오가 안정적인 리스크 허용 범위 내에서 운용 중입니다."

    # 4. 오늘의 실천 액션 가이드 (Action Items)
    action_items = []
    if stop_loss_count > 0:
        action_items.append(f"🚨 손절가 도달 종목({stop_loss_count}건)의 지지선 이탈 여부 확인 및 리스크 관리")
    else:
        action_items.append("🛡️ 전 종목 손절가 안전 구간 유지 중 — 기존 추세 유지 및 홀딩")

    if urgent_isa_list:
        action_items.append(f"⏳ ISA 만기({urgent_isa_list[0]['dday_label']}) 자금 연금 전환 세액공제(최대 {int(max_isa_deduction):,}원) 혜택 챙기기")
    elif isa_accounts or pension_accounts:
        action_items.append("💡 절세 계좌(ISA/연금) 연간 납입 여력 및 세액공제 한도 점검")

    if total_eval > 0 and (krx_ratio >= 85.0 or us_ratio >= 85.0):
        action_items.append(f"🌐 한쪽 시장 비중 편중 완화 (국내 {krx_ratio}% / 해외 {us_ratio}%) 고려")
    else:
        action_items.append("📊 시장 지수(KOSPI / S&P 500) 대비 포트폴리오 상대 강도 모니터링")

    return {
        "user_id": user_id,
        "briefing_date": today_iso,
        "generated_at": now_str,
        "summary_metrics": {
            "total_invested": total_invested,
            "total_eval": total_eval,
            "total_profit": profit_val,
            "total_profit_rate": profit_rate,
            "item_count": item_count,
            "stop_loss_count": stop_loss_count,
        },
        "market_benchmark": {
            "kospi_rate": kospi_rate,
            "sp500_rate": sp500_rate,
            "usd_krw_rate": usd_rate,
            "comment": benchmark_comment,
            "status_tag": benchmark_tag,
        },
        "tax_accounts": {
            "has_issue": has_tax_issue,
            "isa_count": len(isa_accounts),
            "pension_count": len(pension_accounts),
            "urgent_isa": urgent_isa_list,
            "max_deduction_estimate": max_isa_deduction,
            "comment": tax_comment,
        },
        "risk_analysis": {
            "level": risk_level,
            "badge_color": risk_color,
            "badge_emoji": risk_emoji,
            "stop_loss_count": stop_loss_count,
            "krx_ratio": krx_ratio,
            "us_ratio": us_ratio,
            "comment": risk_comment,
        },
        "action_items": action_items,
    }

