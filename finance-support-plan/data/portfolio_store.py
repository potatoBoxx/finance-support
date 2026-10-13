import json
from pathlib import Path
from typing import Dict, List, Optional, Any

# 상대 경로 기준 데이터 파일 위치 설정
DATA_DIR = Path(__file__).resolve().parent
DATA_FILE = DATA_DIR / "portfolios.json"


def _load_raw_data() -> Dict[str, Any]:
    """로컬 JSON 파일에서 데이터를 읽어옵니다."""
    if not DATA_FILE.exists():
        initial_data = {"users": {}}
        _save_raw_data(initial_data)
        return initial_data

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"users": {}}


def _save_raw_data(data: Dict[str, Any]) -> None:
    """데이터를 로컬 JSON 파일에 영구 저장합니다."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ok=False, indent=2)


def authenticate_user(user_id: str, pin: str) -> bool:
    """사용자 ID와 PIN 번호를 검증합니다.
    새로운 사용자일 경우 자동으로 신규 프로필을 생성합니다.
    """
    user_id = user_id.strip()
    pin = pin.strip()
    if not user_id or not pin:
        return False

    data = _load_raw_data()
    users = data.get("users", {})

    if user_id in users:
        return users[user_id].get("pin") == pin
    else:
        # 신규 사용자 자동 등록
        users[user_id] = {
            "pin": pin,
            "user_name": f"사용자_{user_id}",
            "holdings": []
        }
        data["users"] = users
        _save_raw_data(data)
        return True


def get_user_holdings(user_id: str) -> List[Dict[str, Any]]:
    """특정 사용자의 보유 종목 리스트를 반환합니다."""
    data = _load_raw_data()
    return data.get("users", {}).get(user_id, {}).get("holdings", [])


def add_or_update_holding(user_id: str, holding: Dict[str, Any]) -> bool:
    """보유 종목을 신규 등록하거나 기존 티커를 수정합니다."""
    data = _load_raw_data()
    user_data = data.get("users", {}).get(user_id)
    if not user_data:
        return False

    ticker = holding.get("ticker", "").strip().upper()
    if not ticker:
        return False

    holding["ticker"] = ticker
    holdings = user_data.get("holdings", [])

    # 기존 종목 여부 확인
    existing_index = next((i for i, item in enumerate(holdings) if item.get("ticker") == ticker), None)
    if existing_index is not None:
        holdings[existing_index] = holding
    else:
        holdings.append(holding)

    user_data["holdings"] = holdings
    data["users"][user_id] = user_data
    _save_raw_data(data)
    return True


def delete_holding(user_id: str, ticker: str) -> bool:
    """보유 종목을 삭제합니다."""
    data = _load_raw_data()
    user_data = data.get("users", {}).get(user_id)
    if not user_data:
        return False

    ticker = ticker.strip().upper()
    holdings = user_data.get("holdings", [])
    new_holdings = [item for item in holdings if item.get("ticker") != ticker]

    if len(holdings) == len(new_holdings):
        return False

    user_data["holdings"] = new_holdings
    data["users"][user_id] = user_data
    _save_raw_data(data)
    return True
