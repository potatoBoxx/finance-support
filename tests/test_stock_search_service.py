import pytest
from services.stock_search_service import search_stock_by_ticker_or_name

def test_search_stock_by_popular_ticker_krx():
    res = search_stock_by_ticker_or_name("005930", market="KRX")
    assert res is not None
    assert res["ticker"] == "005930"
    assert res["name"] == "삼성전자"
    assert res["market"] == "KRX"
    assert res["price"] > 0

def test_search_stock_by_popular_name_krx():
    res = search_stock_by_ticker_or_name("카카오", market="KRX")
    assert res is not None
    assert res["ticker"] == "035720"
    assert res["name"] == "카카오"

def test_search_stock_by_ticker_us():
    res = search_stock_by_ticker_or_name("AAPL", market="US")
    assert res is not None
    assert res["ticker"] == "AAPL"
    assert "Apple" in res["name"]
    assert res["market"] == "US"

def test_search_stock_by_korean_name_us():
    res = search_stock_by_ticker_or_name("테슬라", market="US")
    assert res is not None
    assert res["ticker"] == "TSLA"
    assert "Tesla" in res["name"]

def test_search_stock_not_found():
    res = search_stock_by_ticker_or_name("NON_EXISTENT_XYZ_12345", market="KRX")
    assert res is None
