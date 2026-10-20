"""
포트폴리오 및 사용자 데이터 영속성 레포지토리 (Supabase + 로컬 데모 Graceful Fallback)
"""
import uuid
import hashlib
import logging
from datetime import datetime
from typing import Optional, Any

from db.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


def hash_pin(pin: str) -> str:
    """4자리 PIN 번호를 SHA-256 해시값으로 변환합니다."""
    clean_pin = str(pin).strip()
    return hashlib.sha256(clean_pin.encode("utf-8")).hexdigest()


_UNSET = object()


class PortfolioRepository:
    """
    포트폴리오 CRUD 및 사용자 인증 관리 레포지토리.
    Supabase 연결이 없거나 실패할 경우 st.session_state 또는 인메모리 Mock 저장소로 자동 폴백합니다.
    """

    def __init__(self, client: Any = _UNSET):
        self.client = get_supabase_client() if client is _UNSET else client
        # Streamlit 외부(테스트 등)에서 session_state가 없을 때 사용할 백업 메모리
        self._fallback_users: dict[str, dict] = {}
        self._fallback_items: dict[str, list[dict]] = {}
        self._fallback_accounts: dict[str, list[dict]] = {}
        self._fallback_briefings: dict[str, dict[str, dict]] = {}
        self._fallback_disclosures: dict[str, list[dict]] = {}
        self._fallback_scraps: dict[str, list[dict]] = {}
        self._init_demo_data()

    def _init_demo_data(self):
        """데모 계정 및 초기 모의 데이터 구성"""
        demo_user_id = "00000000-0000-0000-0000-000000000001"
        self._fallback_users["demo"] = {
            "id": demo_user_id,
            "username": "demo",
            "pin_hash": hash_pin("1234"),
            "created_at": datetime.now().isoformat()
        }
        self._fallback_accounts[demo_user_id] = [
            {
                "id": "11111111-0000-0000-0000-000000000001",
                "user_id": demo_user_id,
                "broker_name": "토스증권",
                "account_alias": "주거래계좌",
                "account_type": "일반",
                "opened_at": "2023-01-10",
                "maturity_at": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            },
            {
                "id": "11111111-0000-0000-0000-000000000002",
                "user_id": demo_user_id,
                "broker_name": "키움증권",
                "account_alias": "해외직투",
                "account_type": "일반",
                "opened_at": "2023-03-15",
                "maturity_at": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            },
            {
                "id": "11111111-0000-0000-0000-000000000003",
                "user_id": demo_user_id,
                "broker_name": "한국투자증권",
                "account_alias": "중개형ISA",
                "account_type": "ISA",
                "opened_at": "2024-05-10",
                "maturity_at": "2027-05-10",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        ]
        self._fallback_items[demo_user_id] = [
            {
                "id": str(uuid.uuid4()),
                "user_id": demo_user_id,
                "account_id": "11111111-0000-0000-0000-000000000001",
                "market": "KRX",
                "ticker": "005930",
                "name": "삼성전자",
                "account": "토스증권",
                "buy_price": 72000.0,
                "quantity": 15.0,
                "target_price": 85000.0,
                "stop_loss_price": 68000.0,
                "memo": "장기 적립식",
                "created_at": datetime.now().isoformat()
            },
            {
                "id": str(uuid.uuid4()),
                "user_id": demo_user_id,
                "account_id": "11111111-0000-0000-0000-000000000002",
                "market": "US",
                "ticker": "AAPL",
                "name": "Apple Inc",
                "account": "키움증권",
                "buy_price": 195.5,
                "quantity": 10.0,
                "target_price": 240.0,
                "stop_loss_price": 180.0,
                "memo": "AI 모멘텀",
                "created_at": datetime.now().isoformat()
            },
            {
                "id": str(uuid.uuid4()),
                "user_id": demo_user_id,
                "account_id": "11111111-0000-0000-0000-000000000001",
                "market": "US",
                "ticker": "NVDA",
                "name": "NVIDIA Corp",
                "account": "토스증권",
                "buy_price": 128.0,
                "quantity": 20.0,
                "target_price": 150.0,
                "stop_loss_price": 115.0,
                "memo": "반도체 주도주",
                "created_at": datetime.now().isoformat()
            },
            {
                "id": str(uuid.uuid4()),
                "user_id": demo_user_id,
                "account_id": "11111111-0000-0000-0000-000000000003",
                "market": "KRX",
                "ticker": "472107",
                "name": "TIGER 미국테크TOP10채권혼합",
                "account": "한국투자증권",
                "buy_price": 14100.0,
                "quantity": 50.0,
                "target_price": 16000.0,
                "stop_loss_price": 13000.0,
                "memo": "채권혼합 안정형",
                "created_at": datetime.now().isoformat()
            }
        ]

    def _get_mock_store(self) -> tuple[dict[str, dict], dict[str, list[dict]], dict[str, list[dict]]]:
        """Streamlit session_state가 존재하면 이를 활용하고, 없으면 내부 딕셔너리를 반환합니다."""
        try:
            import streamlit as st
            if "mock_db_users" not in st.session_state:
                st.session_state.mock_db_users = dict(self._fallback_users)
            if "mock_db_items" not in st.session_state:
                st.session_state.mock_db_items = dict(self._fallback_items)
            if "mock_db_accounts" not in st.session_state:
                st.session_state.mock_db_accounts = dict(self._fallback_accounts)
            
            # demo 유저 항목에 한국투자증권 472107 동기화 보장
            demo_user_id = "00000000-0000-0000-0000-000000000001"
            if demo_user_id in st.session_state.mock_db_items:
                cur_tickers = [it.get("ticker") for it in st.session_state.mock_db_items[demo_user_id]]
                if "472107" not in cur_tickers and "472170" not in cur_tickers:
                    st.session_state.mock_db_items[demo_user_id].append({
                        "id": str(uuid.uuid4()),
                        "user_id": demo_user_id,
                        "account_id": "11111111-0000-0000-0000-000000000003",
                        "market": "KRX",
                        "ticker": "472107",
                        "name": "TIGER 미국테크TOP10채권혼합",
                        "account": "한국투자증권",
                        "buy_price": 14100.0,
                        "quantity": 50.0,
                        "target_price": 16000.0,
                        "stop_loss_price": 13000.0,
                        "memo": "채권혼합 안정형",
                        "created_at": datetime.now().isoformat()
                    })
            return st.session_state.mock_db_users, st.session_state.mock_db_items, st.session_state.mock_db_accounts
        except Exception:
            return self._fallback_users, self._fallback_items, self._fallback_accounts

    def is_demo_mode(self) -> bool:
        """현재 Supabase가 아닌 로컬 데모(Mock) 모드로 동작 중인지 여부"""
        return self.client is None


    # --------------------------------------------------------------------------
    # 1. 사용자 인증 및 등록
    # --------------------------------------------------------------------------
    def authenticate_or_create_user(self, username: str, pin: str) -> tuple[bool, Optional[dict], str]:
        """
        사용자 ID와 PIN을 검증합니다.
        기존 유저: PIN 일치 시 로그인 성공, 불일치 시 실패
        신규 유저: 해당 ID와 PIN으로 새 계정을 자동 생성 후 로그인 성공
        """
        clean_user = username.strip()
        clean_pin = str(pin).strip()

        if not clean_user:
            return False, None, "사용자 ID를 입력해주세요."
        if not clean_pin or len(clean_pin) < 4:
            return False, None, "PIN 번호는 4자리 이상이어야 합니다."

        target_hash = hash_pin(clean_pin)

        # 1-1. Supabase 연동 모드
        if self.client is not None:
            try:
                response = self.client.table("users").select("*").eq("username", clean_user).execute()
                users = response.data or []

                if users:
                    user = users[0]
                    if user.get("pin_hash") == target_hash:
                        return True, user, f"'{clean_user}'님 환영합니다."
                    else:
                        return False, None, "PIN 번호가 일치하지 않습니다."
                else:
                    # 신규 계정 자동 등록
                    new_user = {
                        "username": clean_user,
                        "pin_hash": target_hash
                    }
                    insert_res = self.client.table("users").insert(new_user).execute()
                    if insert_res.data:
                        created = insert_res.data[0]
                        return True, created, f"새 계정 '{clean_user}'이 생성되었습니다."
                    return False, None, "계정 생성에 실패했습니다."
            except Exception as e:
                logger.error(f"Supabase user auth error: {e}. Falling back to demo mode.")

        # 1-2. 로컬 데모(Mock) 폴백 모드
        mock_users, mock_items, mock_accounts = self._get_mock_store()
        if clean_user in mock_users:
            user = mock_users[clean_user]
            if user.get("pin_hash") == target_hash:
                return True, user, f"'{clean_user}'님 환영합니다. (로컬 데모 모드)"
            else:
                return False, None, "PIN 번호가 일치하지 않습니다."
        else:
            new_id = str(uuid.uuid4())
            new_user = {
                "id": new_id,
                "username": clean_user,
                "pin_hash": target_hash,
                "created_at": datetime.now().isoformat()
            }
            mock_users[clean_user] = new_user
            mock_items[new_id] = []
            mock_accounts[new_id] = []
            return True, new_user, f"새 계정 '{clean_user}'이 생성되었습니다. (로컬 데모 모드)"

    # --------------------------------------------------------------------------
    # 2. 포트폴리오 조회
    # --------------------------------------------------------------------------
    def get_items(self, user_id: str) -> list[dict]:
        """사용자의 보유 종목 목록을 조회합니다."""
        if not user_id:
            return []

        if self.client is not None:
            try:
                res = self.client.table("portfolio_items").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
                items = res.data or []
                for it in items:
                    if not it.get("account"):
                        it["account"] = "기본"
                    if "account_id" not in it:
                        it["account_id"] = None
                return items
            except Exception as e:
                logger.error(f"Supabase get_items error: {e}. Falling back to mock store.")

        _, mock_items, _ = self._get_mock_store()
        items = list(mock_items.get(user_id, []))
        for it in items:
            if not it.get("account"):
                it["account"] = "기본"
            if "account_id" not in it:
                it["account_id"] = None
        return items

    # --------------------------------------------------------------------------
    # 3. 보유 종목 추가
    # --------------------------------------------------------------------------
    def add_item(self, user_id: str, item_data: dict) -> tuple[bool, str]:
        """신규 보유 종목을 등록합니다."""
        if not user_id:
            return False, "유효한 사용자 정보가 없습니다."

        ticker = str(item_data.get("ticker", "")).strip().upper()
        name = str(item_data.get("name", "")).strip()
        market = str(item_data.get("market", "KRX")).strip().upper()
        account = str(item_data.get("account", "기본")).strip() or "기본"
        account_id = item_data.get("account_id")
        
        try:
            buy_price = float(item_data.get("buy_price", 0))
            quantity = float(item_data.get("quantity", 0))
        except (ValueError, TypeError):
            return False, "매수가와 수량은 올바른 숫자여야 합니다."

        if not ticker or not name:
            return False, "티커와 종목명은 필수 입력 항목입니다."
        if buy_price <= 0 or quantity <= 0:
            return False, "매수가와 수량은 0보다 커야 합니다."

        target_price = float(item_data["target_price"]) if item_data.get("target_price") else None
        stop_loss_price = float(item_data["stop_loss_price"]) if item_data.get("stop_loss_price") else None
        memo = str(item_data.get("memo", "")).strip() or None

        record = {
            "user_id": user_id,
            "account_id": account_id,
            "market": market,
            "ticker": ticker,
            "name": name,
            "account": account,
            "buy_price": buy_price,
            "quantity": quantity,
            "target_price": target_price,
            "stop_loss_price": stop_loss_price,
            "memo": memo,
            "updated_at": datetime.now().isoformat()
        }

        # Supabase 연동
        if self.client is not None:
            try:
                # 동일 사용자/종목/계좌 중복 확인
                existing = self.client.table("portfolio_items").select("id").eq("user_id", user_id).eq("ticker", ticker).eq("account", account).execute()
                if existing.data:
                    return False, f"이미 해당 계좌({account})에 등록된 종목입니다 ({ticker})."

                record["created_at"] = datetime.now().isoformat()
                insert_res = self.client.table("portfolio_items").insert(record).execute()
                if insert_res.data:
                    return True, f"'{name}' ({account}) 종목이 성공적으로 등록되었습니다."
                return False, "종목 등록에 실패했습니다."
            except Exception as e:
                logger.error(f"Supabase add_item error: {e}. Falling back to mock store.")

        # 로컬 Mock 폴백
        _, mock_items, _ = self._get_mock_store()
        user_list = mock_items.setdefault(user_id, [])
        for item in user_list:
            if item.get("ticker") == ticker and str(item.get("account") or "기본").strip() == account:
                return False, f"이미 해당 계좌({account})에 등록된 종목입니다 ({ticker})."

        record["id"] = str(uuid.uuid4())
        record["created_at"] = datetime.now().isoformat()
        user_list.insert(0, record)
        return True, f"'{name}' ({account}) 종목이 성공적으로 등록되었습니다. (로컬 데모 모드)"

    # --------------------------------------------------------------------------
    # 4. 보유 종목 수정
    # --------------------------------------------------------------------------
    def update_item(self, item_id: str, item_data: dict) -> tuple[bool, str]:
        """등록된 종목의 매수가, 수량, 목표가, 손절가, 메모, 계좌를 수정합니다."""
        if not item_id:
            return False, "종목 식별자가 누락되었습니다."

        try:
            buy_price = float(item_data.get("buy_price", 0))
            quantity = float(item_data.get("quantity", 0))
        except (ValueError, TypeError):
            return False, "매수가와 수량은 숫자여야 합니다."

        if buy_price <= 0 or quantity <= 0:
            return False, "매수가와 수량은 0보다 커야 합니다."

        update_fields = {
            "buy_price": buy_price,
            "quantity": quantity,
            "target_price": float(item_data["target_price"]) if item_data.get("target_price") else None,
            "stop_loss_price": float(item_data["stop_loss_price"]) if item_data.get("stop_loss_price") else None,
            "memo": str(item_data.get("memo", "")).strip() or None,
            "updated_at": datetime.now().isoformat()
        }

        if "account" in item_data:
            update_fields["account"] = str(item_data["account"]).strip() or "기본"
        if "account_id" in item_data:
            update_fields["account_id"] = item_data.get("account_id")
        if "name" in item_data and str(item_data["name"]).strip():
            update_fields["name"] = str(item_data["name"]).strip()

        if self.client is not None:
            try:
                res = self.client.table("portfolio_items").update(update_fields).eq("id", item_id).execute()
                if res.data:
                    return True, "종목 정보가 수정되었습니다."
                return False, "수정 대상 종목을 찾을 수 없습니다."
            except Exception as e:
                logger.error(f"Supabase update_item error: {e}. Falling back to mock store.")

        _, mock_items, _ = self._get_mock_store()
        for user_id, items in mock_items.items():
            for item in items:
                if item.get("id") == item_id:
                    item.update(update_fields)
                    return True, "종목 정보가 수정되었습니다. (로컬 데모 모드)"

        return False, "수정 대상 종목을 찾을 수 없습니다."

    # --------------------------------------------------------------------------
    # 5. 보유 종목 삭제
    # --------------------------------------------------------------------------
    def delete_item(self, item_id: str) -> tuple[bool, str]:
        """등록된 종목을 포트폴리오에서 삭제합니다."""
        if not item_id:
            return False, "종목 식별자가 누락되었습니다."

        if self.client is not None:
            try:
                res = self.client.table("portfolio_items").delete().eq("id", item_id).execute()
                if res.data:
                    return True, "종목이 포트폴리오에서 삭제되었습니다."
                return False, "삭제 대상 종목을 찾을 수 없습니다."
            except Exception as e:
                logger.error(f"Supabase delete_item error: {e}. Falling back to mock store.")

        _, mock_items, _ = self._get_mock_store()
        for user_id, items in mock_items.items():
            for idx, item in enumerate(items):
                if item.get("id") == item_id:
                    deleted = items.pop(idx)
                    return True, f"'{deleted.get('name')}' 종목이 삭제되었습니다. (로컬 데모 모드)"

        return False, "삭제 대상 종목을 찾을 수 없습니다."

    # --------------------------------------------------------------------------
    # 6. 계좌 목록 조회
    # --------------------------------------------------------------------------
    def get_accounts(self, user_id: str) -> list[dict]:
        """사용자의 계좌 목록을 조회합니다 (없으면 자동 시딩)."""
        if not user_id:
            return []

        if self.client is not None:
            try:
                res = self.client.table("accounts").select("*").eq("user_id", user_id).order("created_at").execute()
                accounts = res.data or []
                if not accounts:
                    accounts = self.auto_seed_accounts_from_items(user_id)
                return accounts
            except Exception as e:
                logger.error(f"Supabase get_accounts error: {e}. Falling back to mock store.")

        _, _, mock_accounts = self._get_mock_store()
        if user_id not in mock_accounts or len(mock_accounts[user_id]) == 0:
            mock_accounts[user_id] = self.auto_seed_accounts_from_items(user_id)
        return list(mock_accounts.get(user_id, []))

    # --------------------------------------------------------------------------
    # 7. 신규 계좌 생성
    # --------------------------------------------------------------------------
    def create_account(self, user_id: str, account_data: dict) -> tuple[bool, Optional[dict], str]:
        """신규 계좌를 생성합니다."""
        if not user_id:
            return False, None, "유효한 사용자 정보가 없습니다."

        broker_name = str(account_data.get("broker_name", "")).strip()
        account_type = str(account_data.get("account_type", "일반")).strip()
        account_alias = str(account_data.get("account_alias", "")).strip() or None
        opened_at = str(account_data.get("opened_at", "")).strip() or None
        maturity_at = str(account_data.get("maturity_at", "")).strip() or None

        if not broker_name:
            return False, None, "증권사명은 필수입니다."
        if account_type not in ("일반", "ISA", "연금저축", "IRP"):
            return False, None, f"지원하지 않는 계좌 유형입니다: {account_type}"

        rec = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "broker_name": broker_name,
            "account_alias": account_alias,
            "account_type": account_type,
            "opened_at": opened_at,
            "maturity_at": maturity_at,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        if self.client is not None:
            try:
                res = self.client.table("accounts").insert(rec).execute()
                if res.data:
                    return True, res.data[0], f"'{broker_name}' 계좌가 생성되었습니다."
                return False, None, "계좌 생성에 실패했습니다."
            except Exception as e:
                logger.error(f"Supabase create_account error: {e}. Falling back to mock store.")

        _, _, mock_accounts = self._get_mock_store()
        mock_accounts.setdefault(user_id, []).append(rec)
        return True, rec, f"'{broker_name}' 계좌가 생성되었습니다. (로컬 데모 모드)"

    # --------------------------------------------------------------------------
    # 8. 계좌 삭제
    # --------------------------------------------------------------------------
    def delete_account(self, account_id: str) -> tuple[bool, str]:
        """계좌를 삭제합니다. 연결된 종목의 account_id는 안전하게 해제(SET NULL)됩니다."""
        if not account_id:
            return False, "계좌 식별자가 누락되었습니다."

        if self.client is not None:
            try:
                res = self.client.table("accounts").delete().eq("id", account_id).execute()
                if res.data:
                    return True, "계좌가 삭제되었습니다."
                return False, "삭제 대상 계좌를 찾을 수 없습니다."
            except Exception as e:
                logger.error(f"Supabase delete_account error: {e}. Falling back to mock store.")

        _, mock_items, mock_accounts = self._get_mock_store()
        for user_id, accs in mock_accounts.items():
            for idx, acc in enumerate(accs):
                if acc.get("id") == account_id:
                    deleted = accs.pop(idx)
                    # 연결된 mock 종목들의 account_id를 None으로 해제 (종목 자체는 보존)
                    if user_id in mock_items:
                        for it in mock_items[user_id]:
                            if it.get("account_id") == account_id:
                                it["account_id"] = None
                    return True, f"'{deleted.get('broker_name')}' 계좌가 삭제되었습니다. (로컬 데모 모드)"

        return False, "삭제 대상 계좌를 찾을 수 없습니다."

    # --------------------------------------------------------------------------
    # 9. 기존 종목 기반 계좌 자동 시딩
    # --------------------------------------------------------------------------
    def auto_seed_accounts_from_items(self, user_id: str) -> list[dict]:
        """
        사용자의 기존 보유 종목(portfolio_items.account)에 기록된 고유 계좌명을 조회하여,
        accounts 테이블에 누락된 계좌를 자동 생성하고 종목의 account_id를 연결합니다.
        """
        if not user_id:
            return []

        # 1. 사용자의 보유 종목 조회
        items = self.get_items(user_id)
        distinct_names = []
        for it in items:
            acc_name = str(it.get("account") or "").strip()
            if acc_name and acc_name not in distinct_names:
                distinct_names.append(acc_name)

        if not distinct_names:
            distinct_names = ["토스증권"]

        seeded_accounts = []

        if self.client is not None:
            try:
                res = self.client.table("accounts").select("*").eq("user_id", user_id).execute()
                existing_accounts = res.data or []
                existing_brokers = {a["broker_name"] for a in existing_accounts}

                for bname in distinct_names:
                    if bname not in existing_brokers:
                        acc_id = str(uuid.uuid4())
                        rec = {
                            "id": acc_id,
                            "user_id": user_id,
                            "broker_name": bname,
                            "account_alias": None,
                            "account_type": "일반",
                            "opened_at": None,
                            "maturity_at": None,
                            "created_at": datetime.now().isoformat(),
                            "updated_at": datetime.now().isoformat()
                        }
                        ins = self.client.table("accounts").insert(rec).execute()
                        if ins.data:
                            created_acc = ins.data[0]
                            seeded_accounts.append(created_acc)
                            existing_brokers.add(bname)
                            # 해당 종목의 account_id 업데이트
                            self.client.table("portfolio_items").update({"account_id": created_acc["id"]}).eq("user_id", user_id).eq("account", bname).execute()
                    else:
                        match_acc = next((a for a in existing_accounts if a["broker_name"] == bname), None)
                        if match_acc:
                            seeded_accounts.append(match_acc)

                res_final = self.client.table("accounts").select("*").eq("user_id", user_id).order("created_at").execute()
                return res_final.data or seeded_accounts
            except Exception as e:
                logger.error(f"Supabase auto_seed_accounts error: {e}. Falling back to mock store.")

        # 로컬 Mock 모드
        mock_users, mock_items, mock_accounts = self._get_mock_store()
        user_accs = mock_accounts.setdefault(user_id, [])
        existing_brokers = {a["broker_name"] for a in user_accs}

        for bname in distinct_names:
            if bname not in existing_brokers:
                acc_id = str(uuid.uuid4())
                rec = {
                    "id": acc_id,
                    "user_id": user_id,
                    "broker_name": bname,
                    "account_alias": None,
                    "account_type": "일반",
                    "opened_at": None,
                    "maturity_at": None,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
                user_accs.append(rec)
                seeded_accounts.append(rec)
                existing_brokers.add(bname)
                # mock items 매핑
                if user_id in mock_items:
                    for it in mock_items[user_id]:
                        if it.get("account") == bname and not it.get("account_id"):
                            it["account_id"] = acc_id
            else:
                match_acc = next((a for a in user_accs if a["broker_name"] == bname), None)
                if match_acc:
                    seeded_accounts.append(match_acc)

        return user_accs

    # --------------------------------------------------------------------------
    # 일일 AI 포트폴리오 진단 브리핑 캐시 관리 (Supabase + 세션/인메모리 폴백)
    # --------------------------------------------------------------------------
    def _get_mock_briefing_store(self) -> dict[str, dict[str, dict]]:
        """Streamlit session_state가 존재하면 이를 활용하고, 없으면 내부 딕셔너리를 반환합니다."""
        try:
            import streamlit as st
            if "mock_db_briefings" not in st.session_state:
                st.session_state.mock_db_briefings = dict(self._fallback_briefings)
            return st.session_state.mock_db_briefings
        except Exception:
            return self._fallback_briefings

    def get_daily_briefing(self, user_id: str, briefing_date: str) -> Optional[dict]:
        """
        특정 날짜의 일일 AI 종합 브리핑 캐시를 조회합니다.
        Supabase 연결 시 user_briefings 테이블에서 조회하고, 실패 또는 미연결 시 로컬/세션 캐시로 폴백합니다.
        """
        if not user_id or not briefing_date:
            return None

        clean_user = str(user_id).strip()
        clean_date = str(briefing_date).strip()

        if self.client is not None:
            try:
                res = (
                    self.client.table("user_briefings")
                    .select("content")
                    .eq("user_id", clean_user)
                    .eq("briefing_date", clean_date)
                    .limit(1)
                    .execute()
                )
                if res.data and len(res.data) > 0:
                    raw_content = res.data[0].get("content")
                    if isinstance(raw_content, dict):
                        return raw_content
                    elif isinstance(raw_content, str):
                        import json
                        try:
                            return json.loads(raw_content)
                        except Exception:
                            return None
            except Exception as e:
                logger.warning(f"Supabase get_daily_briefing error: {e}. Falling back to mock store.")

        mock_briefings = self._get_mock_briefing_store()
        return mock_briefings.get(clean_user, {}).get(clean_date)

    def save_daily_briefing(self, user_id: str, briefing_date: str, content: dict) -> bool:
        """
        특정 날짜의 일일 AI 종합 브리핑을 캐싱 저장합니다 (Upsert).
        Supabase 연결 시 user_briefings 테이블에 저장하고, 실패 또는 미연결 시 로컬/세션 캐시로 폴백합니다.
        """
        if not user_id or not briefing_date or not isinstance(content, dict):
            return False

        clean_user = str(user_id).strip()
        clean_date = str(briefing_date).strip()

        # 로컬/세션 캐시 항상 동기화
        mock_briefings = self._get_mock_briefing_store()
        if clean_user not in mock_briefings:
            mock_briefings[clean_user] = {}
        mock_briefings[clean_user][clean_date] = content

        if self.client is not None:
            try:
                record = {
                    "user_id": clean_user,
                    "briefing_date": clean_date,
                    "content": content,
                    "updated_at": datetime.now().isoformat()
                }
                res = self.client.table("user_briefings").upsert(record, on_conflict="user_id, briefing_date").execute()
                return bool(res.data)
            except Exception as e:
                logger.warning(f"Supabase save_daily_briefing error: {e}. Preserved in local/session cache.")
                return True

        return True

    # --------------------------------------------------------------------------
    # 보유 종목 뉴스 및 주요 공시 관리 (Supabase + 세션/인메모리 폴백)
    # --------------------------------------------------------------------------
    def _get_mock_disclosure_store(self) -> dict[str, list[dict]]:
        """Streamlit session_state가 존재하면 이를 활용하고, 없으면 내부 딕셔너리를 반환합니다."""
        try:
            import streamlit as st
            if "mock_db_disclosures" not in st.session_state:
                st.session_state.mock_db_disclosures = dict(self._fallback_disclosures)
            return st.session_state.mock_db_disclosures
        except Exception:
            return self._fallback_disclosures

    def get_disclosures(self, user_id: str, limit: int = 20) -> list[dict]:
        """
        해당 유저의 최신 공시/기사 목록을 최신순(published_at DESC)으로 조회하여 반환합니다.
        """
        if not user_id:
            return []

        clean_user = str(user_id).strip()

        if self.client is not None:
            try:
                res = (
                    self.client.table("portfolio_disclosures")
                    .select("*")
                    .eq("user_id", clean_user)
                    .order("published_at", desc=True)
                    .limit(limit)
                    .execute()
                )
                if res.data is not None:
                    return res.data
            except Exception as e:
                logger.warning(f"Supabase get_disclosures error: {e}. Falling back to mock store.")

        mock_disclosures = self._get_mock_disclosure_store()
        user_records = mock_disclosures.get(clean_user, [])
        sorted_records = sorted(
            user_records,
            key=lambda x: str(x.get("published_at") or x.get("created_at") or ""),
            reverse=True,
        )
        return sorted_records[:limit]

    def save_disclosures(self, user_id: str, items: list[dict]) -> tuple[int, str]:
        """
        수집된 공시/기사 목록을 저장합니다. (동일 user_id, origin_url에 대해 upsert)
        반환값: (저장 건수, 결과 메시지)
        """
        if not user_id or not items:
            return 0, "저장할 데이터가 없습니다."

        clean_user = str(user_id).strip()

        now_iso = datetime.now().isoformat()
        records = []
        for it in items:
            origin_url = str(it.get("origin_url") or "").strip()
            if not origin_url:
                continue
            rec = {
                "user_id": clean_user,
                "ticker": str(it.get("ticker") or "").strip().upper(),
                "item_name": str(it.get("item_name") or "").strip(),
                "title": str(it.get("title") or "").strip(),
                "source": str(it.get("source") or "").strip() or "뉴스/공시",
                "origin_url": origin_url,
                "published_at": it.get("published_at"),
                "category": str(it.get("category") or "시장이슈").strip(),
                "content_scraped": it.get("content_scraped"),
                "summary_ai": it.get("summary_ai"),
                "created_at": it.get("created_at") or now_iso,
            }
            records.append(rec)

        if not records:
            return 0, "유효한 공시/뉴스 레코드가 없습니다."

        # 로컬/세션 캐시 항상 upsert 동기화
        mock_disclosures = self._get_mock_disclosure_store()
        if clean_user not in mock_disclosures:
            mock_disclosures[clean_user] = []

        existing_urls = {r["origin_url"]: idx for idx, r in enumerate(mock_disclosures[clean_user])}
        for rec in records:
            url = rec["origin_url"]
            if url in existing_urls:
                mock_disclosures[clean_user][existing_urls[url]].update(rec)
            else:
                existing_urls[url] = len(mock_disclosures[clean_user])
                mock_disclosures[clean_user].append(dict(rec))

        saved_count = len(records)
        if self.client is not None:
            try:
                res = (
                    self.client.table("portfolio_disclosures")
                    .upsert(records, on_conflict="user_id,origin_url")
                    .execute()
                )
                if res.data:
                    saved_count = len(res.data)
                return saved_count, f"{saved_count}건의 공시/뉴스가 성공적으로 저장되었습니다."
            except Exception as e:
                logger.warning(f"Supabase save_disclosures error: {e}. Preserved in local/session cache.")
                return saved_count, f"DB 저장 중 예외 발생, 로컬 세션에 {saved_count}건 보존되었습니다: {e}"

        return saved_count, f"{saved_count}건의 공시/뉴스가 로컬 세션에 보존되었습니다."

    # --------------------------------------------------------------------------
    # 개인 기사/공시 스크랩북 관리 (Supabase + 세션/인메모리 폴백)
    # --------------------------------------------------------------------------
    def _get_mock_scrap_store(self) -> dict[str, list[dict]]:
        """Streamlit session_state가 존재하면 이를 활용하고, 없으면 내부 딕셔너리를 반환합니다."""
        try:
            import streamlit as st
            if "mock_db_scraps" not in st.session_state:
                st.session_state.mock_db_scraps = dict(self._fallback_scraps)
            return st.session_state.mock_db_scraps
        except Exception:
            return self._fallback_scraps

    def save_scrap(
        self,
        user_id: str,
        ticker: str,
        item_name: str,
        title: str,
        origin_url: str,
        source: str = "",
        memo: str = ""
    ) -> tuple[bool, str, Optional[dict]]:
        """
        기사를 스크랩북에 추가하거나 메모를 갱신합니다 (Upsert).
        UNIQUE(user_id, origin_url) 기준.
        """
        if not user_id or not origin_url or not title:
            return False, "필수 정보(사용자 ID, 원문 링크, 제목)가 누락되었습니다.", None

        clean_user = str(user_id).strip()
        clean_url = str(origin_url).strip()
        clean_title = str(title).strip()
        clean_ticker = str(ticker or "").strip()
        clean_item = str(item_name or "").strip()
        clean_source = str(source or "").strip()
        clean_memo = str(memo or "").strip()
        now_iso = datetime.now().isoformat()

        scrap_record = {
            "id": str(uuid.uuid4()),
            "user_id": clean_user,
            "ticker": clean_ticker or None,
            "item_name": clean_item or None,
            "title": clean_title,
            "origin_url": clean_url,
            "source": clean_source or None,
            "memo": clean_memo or None,
            "created_at": now_iso,
        }

        # Mock store 동기화
        mock_scraps = self._get_mock_scrap_store()
        if clean_user not in mock_scraps:
            mock_scraps[clean_user] = []

        existing_idx = next((i for i, r in enumerate(mock_scraps[clean_user]) if r.get("origin_url") == clean_url), None)
        if existing_idx is not None:
            scrap_record["id"] = mock_scraps[clean_user][existing_idx].get("id", scrap_record["id"])
            mock_scraps[clean_user][existing_idx].update({
                "ticker": clean_ticker or None,
                "item_name": clean_item or None,
                "title": clean_title,
                "source": clean_source or None,
                "memo": clean_memo or None,
            })
            saved_item = mock_scraps[clean_user][existing_idx]
        else:
            mock_scraps[clean_user].insert(0, dict(scrap_record))
            saved_item = scrap_record

        if self.client is not None:
            try:
                payload = {
                    "user_id": clean_user,
                    "ticker": clean_ticker or None,
                    "item_name": clean_item or None,
                    "title": clean_title,
                    "origin_url": clean_url,
                    "source": clean_source or None,
                    "memo": clean_memo or None,
                    "created_at": now_iso
                }
                res = self.client.table("scraped_articles").upsert(
                    payload,
                    on_conflict="user_id,origin_url"
                ).execute()
                if res.data and len(res.data) > 0:
                    saved_item = res.data[0]
                    if existing_idx is not None:
                        mock_scraps[clean_user][existing_idx]["id"] = saved_item.get("id")
                    else:
                        mock_scraps[clean_user][0]["id"] = saved_item.get("id")
                return True, "스크랩북에 성공적으로 저장되었습니다.", saved_item
            except Exception as e:
                logger.warning(f"Supabase save_scrap error: {e}. Preserved in local/session cache.")
                return True, f"로컬 세션 스크랩북에 임시 저장되었습니다: {e}", saved_item

        return True, "스크랩북에 저장되었습니다.", saved_item

    def get_scraps(self, user_id: str, ticker_filter: str = "전체") -> list[dict]:
        """
        사용자의 스크랩 목록을 최신순(created_at DESC)으로 조회합니다.
        ticker_filter가 지정된 경우 해당 종목(ticker 또는 item_name)으로 필터링합니다.
        """
        if not user_id:
            return []

        clean_user = str(user_id).strip()
        filter_val = str(ticker_filter or "전체").strip()

        if self.client is not None:
            try:
                query = (
                    self.client.table("scraped_articles")
                    .select("*")
                    .eq("user_id", clean_user)
                    .order("created_at", desc=True)
                )
                if filter_val and filter_val != "전체":
                    query = query.or_(f"ticker.eq.{filter_val},item_name.eq.{filter_val}")
                res = query.execute()
                if res.data is not None:
                    return res.data
            except Exception as e:
                logger.warning(f"Supabase get_scraps error: {e}. Falling back to mock store.")

        mock_scraps = self._get_mock_scrap_store()
        user_records = mock_scraps.get(clean_user, [])
        if filter_val and filter_val != "전체":
            filtered = [
                r for r in user_records
                if r.get("ticker") == filter_val or r.get("item_name") == filter_val
            ]
        else:
            filtered = list(user_records)

        sorted_scraps = sorted(
            filtered,
            key=lambda x: str(x.get("created_at") or ""),
            reverse=True
        )
        return sorted_scraps

    def update_scrap_memo(self, scrap_id: str, new_memo: str, user_id: Optional[str] = None) -> tuple[bool, str]:
        """
        스크랩 항목의 메모를 수정합니다.
        """
        if not scrap_id:
            return False, "유효한 스크랩 ID가 필요합니다."

        clean_id = str(scrap_id).strip()
        clean_memo = str(new_memo or "").strip()

        mock_scraps = self._get_mock_scrap_store()
        for u_id, records in mock_scraps.items():
            for r in records:
                if str(r.get("id")) == clean_id:
                    r["memo"] = clean_memo or None
                    break

        if self.client is not None:
            try:
                res = (
                    self.client.table("scraped_articles")
                    .update({"memo": clean_memo or None})
                    .eq("id", clean_id)
                    .execute()
                )
                return bool(res.data), "메모가 성공적으로 수정되었습니다."
            except Exception as e:
                logger.warning(f"Supabase update_scrap_memo error: {e}. Updated in local/session cache.")
                return True, f"로컬 세션 메모가 수정되었습니다: {e}"

        return True, "메모가 성공적으로 수정되었습니다."

    def delete_scrap(self, scrap_id: str, user_id: Optional[str] = None) -> tuple[bool, str]:
        """
        스크랩 항목을 삭제합니다.
        """
        if not scrap_id:
            return False, "유효한 스크랩 ID가 필요합니다."

        clean_id = str(scrap_id).strip()

        mock_scraps = self._get_mock_scrap_store()
        for u_id, records in mock_scraps.items():
            mock_scraps[u_id] = [r for r in records if str(r.get("id")) != clean_id]

        if self.client is not None:
            try:
                self.client.table("scraped_articles").delete().eq("id", clean_id).execute()
                return True, "스크랩이 성공적으로 삭제되었습니다."
            except Exception as e:
                logger.warning(f"Supabase delete_scrap error: {e}. Removed from local/session cache.")
                return True, f"로컬 세션에서 삭제되었습니다: {e}"

        return True, "스크랩이 삭제되었습니다."

    def get_scraped_urls(self, user_id: str) -> set[str]:
        """
        해당 사용자가 이미 스크랩한 기사들의 origin_url 집합(Set)을 반환합니다.
        """
        if not user_id:
            return set()

        clean_user = str(user_id).strip()
        if self.client is not None:
            try:
                res = (
                    self.client.table("scraped_articles")
                    .select("origin_url")
                    .eq("user_id", clean_user)
                    .execute()
                )
                if res.data:
                    return {str(r.get("origin_url")).strip() for r in res.data if r.get("origin_url")}
            except Exception as e:
                logger.warning(f"Supabase get_scraped_urls error: {e}. Checking mock store.")

        mock_scraps = self._get_mock_scrap_store()
        user_records = mock_scraps.get(clean_user, [])
        return {str(r.get("origin_url")).strip() for r in user_records if r.get("origin_url")}



