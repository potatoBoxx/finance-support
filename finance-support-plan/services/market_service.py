"""시장 데이터 수집 및 분석 서비스 모듈.

향후 실제 금융 데이터 API(pykrx, yfinance 등)와의 연동을 용이하게 하기 위해
인터페이스를 표준화하고, 현재는 고품질 Mock Data를 반환하도록 설계되었습니다.
"""

from typing import Dict, List, Any
from datetime import datetime


def get_market_indices() -> List[Dict[str, Any]]:
    """국내 및 미국 주요 시장 지수/지표 요약 데이터를 반환합니다.

    향후 연동 가이드:
    - 국장 (KOSPI, KOSDAQ): pykrx.stock.get_index_ohlcv_by_date()
    - 미장 (S&P500, NASDAQ, 환율 등): yfinance.Ticker('^GSPC').history()
    """
    return [
        {
            "category": "국내 지수",
            "name": "코스피 (KOSPI)",
            "ticker": "KS11",
            "value": 2748.56,
            "change": 24.12,
            "change_pct": 0.89,
            "status": "up",
            "sparkline": [2710, 2725, 2715, 2730, 2728, 2735, 2748.56],
            "unit": "pt",
        },
        {
            "category": "국내 지수",
            "name": "코스닥 (KOSDAQ)",
            "ticker": "KQ11",
            "value": 852.14,
            "change": -3.20,
            "change_pct": -0.37,
            "status": "down",
            "sparkline": [860, 858, 855, 857, 854, 856, 852.14],
            "unit": "pt",
        },
        {
            "category": "미국 지수",
            "name": "S&P 500",
            "ticker": ".INX",
            "value": 5751.07,
            "change": 45.22,
            "change_pct": 0.79,
            "status": "up",
            "sparkline": [5680, 5695, 5710, 5705, 5720, 5735, 5751.07],
            "unit": "pt",
        },
        {
            "category": "미국 지수",
            "name": "나스닥 종합 (NASDAQ)",
            "ticker": ".IXIC",
            "value": 18137.85,
            "change": 218.45,
            "change_pct": 1.22,
            "status": "up",
            "sparkline": [17850, 17920, 17990, 17940, 18020, 18090, 18137.85],
            "unit": "pt",
        },
        {
            "category": "환율 / 채권",
            "name": "원/달러 환율 (USD/KRW)",
            "ticker": "USDKRW=X",
            "value": 1334.50,
            "change": -6.50,
            "change_pct": -0.48,
            "status": "down",
            "sparkline": [1345, 1342, 1340, 1338, 1337, 1339, 1334.50],
            "unit": "원",
        },
        {
            "category": "환율 / 채권",
            "name": "미국 10년물 국채 금리",
            "ticker": "^TNX",
            "value": 3.982,
            "change": -0.045,
            "change_pct": -1.12,
            "status": "down",
            "sparkline": [4.08, 4.05, 4.03, 4.02, 4.01, 3.99, 3.982],
            "unit": "%",
        },
    ]


def get_daily_market_briefing() -> Dict[str, Any]:
    """오늘의 시장 3줄 핵심 브리핑 및 마켓 센티먼트 데이터를 반환합니다.

    향후 연동 가이드:
    - LLM(Claude/GPT) API를 통해 장 마감 후 pykrx/DART/뉴스 요약본을 자동 생성하도록 연결 가능
    """
    today_str = datetime.now().strftime("%Y년 %m월 %d일")
    return {
        "date": today_str,
        "sentiment_score": 68,  # 0~100 (탐욕/안도 구간)
        "sentiment_label": "탐욕 (Greed) - 위험선호 회복",
        "market_tags": ["#반도체_랠리", "#금리인하_선반영", "#환율_안정화", "#외인_순매수"],
        "three_line_briefing": [
            {
                "num": 1,
                "badge": "거시경제",
                "title": "미 연준 금리 인하 기대 지속 및 美 증시 기술주 강세 훈풍",
                "desc": "물가 지표 둔화에 따른 통화정책 완화 기조 확신으로 뉴욕 증시가 사상 최고치권에 근접했으며, 글로벌 위험자산 선호 심리가 국내 증시로 전이되었습니다."
            },
            {
                "num": 2,
                "badge": "수급동향",
                "title": "외국인·기관 동반 순매수, 반도체 대형주 중심 코스피 견인",
                "desc": "외국인이 코스피 시장에서 4,500억 원 이상 순매수하며 삼성전자와 SK하이닉스를 집중 매집했고, 코스피 지수는 2,740선을 안정적으로 돌파했습니다."
            },
            {
                "num": 3,
                "badge": "외환/환율",
                "title": "달러 약세 및 수출업체 네고 물량 유입으로 환율 1,330원 초반 하향",
                "desc": "달러 인덱스 하락과 원화 강세 흐름에 힘입어 환율 변동성이 완화되었으며, 이는 외국인 자금 추가 유입을 지지하는 긍정적 요인으로 작용하고 있습니다."
            }
        ]
    }


def get_top3_stock_picks() -> List[Dict[str, Any]]:
    """가치 50% + 수급 50% 혼합 기준으로 도출된 오늘 눈여겨볼 Top 3 종목을 반환합니다.

    산출 기준:
    - 가치 점수 (50%): 저PER, 저PBR, 안정적 영업이익률, ROE 지표 정규화 점수
    - 수급 점수 (50%): 최근 5일 외국인/기관 순매수 집중도, 거래대금 회전율 정규화 점수
    - 종합 점수 = (가치 점수 * 0.5) + (수급 점수 * 0.5)

    향후 연동 가이드:
    - pykrx: get_market_fundamental_by_ticker (PER, PBR 등 밸류에이션)
    - pykrx: get_market_net_purchases_of_equities_by_ticker (외인/기관 순매수)
    """
    return [
        {
            "rank": 1,
            "ticker": "005930",
            "name": "삼성전자",
            "market": "KOSPI",
            "sector": "반도체 및 IT",
            "current_price": 74500,
            "change_pct": 2.19,
            "value_score": 88.0,
            "supply_score": 94.0,
            "total_score": 91.0,
            "key_metrics": {
                "PER": "12.8배",
                "PBR": "1.15배",
                "외인 5일 순매수": "+1.2조원",
                "기관 5일 순매수": "+3,400억원",
                "ROE": "11.2%"
            },
            "reason": "HBM3E 공급 가시화 및 범용 메모리 가격 상승 국면. 밸류에이션 매력도(PBR 1.1배)가 높은 상황에서 외인 순매수가 4거래일 연속 유입 중입니다."
        },
        {
            "rank": 2,
            "ticker": "005380",
            "name": "현대차",
            "market": "KOSPI",
            "sector": "자동차 및 운송장비",
            "current_price": 248500,
            "change_pct": 1.43,
            "value_score": 95.0,
            "supply_score": 84.0,
            "total_score": 89.5,
            "key_metrics": {
                "PER": "5.4배",
                "PBR": "0.68배",
                "외인 5일 순매수": "+2,800억원",
                "기관 5일 순매수": "+1,100억원",
                "ROE": "14.5%"
            },
            "reason": "기업 밸류업 프로그램의 대표 수혜주로 강력한 주주환원 정책 및 북미 하이브리드 판매 호조 지속. 극단적 저평가(PER 5배대) 구간 탈피 국면입니다."
        },
        {
            "rank": 3,
            "ticker": "267260",
            "name": "HD현대일렉트릭",
            "market": "KOSPI",
            "sector": "전력기기 및 인프라",
            "current_price": 312000,
            "change_pct": 3.65,
            "value_score": 79.0,
            "supply_score": 96.0,
            "total_score": 87.5,
            "key_metrics": {
                "PER": "21.4배",
                "PBR": "4.80배",
                "외인 5일 순매수": "+1,950억원",
                "기관 5일 순매수": "+820억원",
                "ROE": "28.7%"
            },
            "reason": "북미 AI 데이터센터 발 전력 쇼티지 및 변압기 슈퍼사이클 지속. 기관과 외국인 동시 수급 유입 강도가 섹터 내 최고 수준을 유지하고 있습니다."
        }
    ]
