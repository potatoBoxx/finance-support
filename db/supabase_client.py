"""
Supabase 클라이언트 초기화 및 연결 관리 모듈
"""
import os
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)

_supabase_client_instance: Optional[Any] = None
_initialization_attempted: bool = False


def _get_credential(key: str) -> Optional[str]:
    """Streamlit secrets 또는 OS 환경 변수에서 설정값을 가져옵니다."""
    # 1. Streamlit secrets 확인
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            val = str(st.secrets[key]).strip()
            if val and "your-project" not in val and "your-anon" not in val:
                return val
    except Exception:
        pass

    # 2. OS 환경 변수 확인
    env_val = os.environ.get(key, "").strip()
    if env_val and "your-project" not in env_val and "your-anon" not in env_val:
        return env_val

    return None


def is_supabase_configured() -> bool:
    """Supabase 접속 정보(URL, Key)가 유효하게 설정되어 있는지 확인합니다."""
    url = _get_credential("SUPABASE_URL")
    key = _get_credential("SUPABASE_KEY")
    return bool(url and key)


def get_supabase_client() -> Optional[Any]:
    """
    Supabase 클라이언트 싱글톤 인스턴스를 반환합니다.
    키가 설정되지 않았거나 연결 실패 시 None을 반환하며 애플리케이션이 크래시되지 않습니다.
    """
    global _supabase_client_instance, _initialization_attempted

    if _initialization_attempted:
        return _supabase_client_instance

    _initialization_attempted = True

    url = _get_credential("SUPABASE_URL")
    key = _get_credential("SUPABASE_KEY")

    if not url or not key:
        logger.info("Supabase credentials not configured. Running in Local Demo Mode.")
        _supabase_client_instance = None
        return None

    try:
        from supabase import create_client, ClientOptions
        # 클라이언트 생성
        client = create_client(url, key)
        _supabase_client_instance = client
        logger.info("Supabase client successfully initialized.")
        return _supabase_client_instance
    except ImportError:
        logger.warning("supabase-py package is not installed. Running in Local Demo Mode.")
        _supabase_client_instance = None
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Running in Local Demo Mode.")
        _supabase_client_instance = None
        return None


def reset_client():
    """테스트용 클라이언트 리셋 함수"""
    global _supabase_client_instance, _initialization_attempted
    _supabase_client_instance = None
    _initialization_attempted = False
