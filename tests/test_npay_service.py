import pytest
import pandas as pd
from services.npay_service import (
    normalize_market_data,
    calculate_top3_quant,
    get_mock_market_data,
    fetch_npay_items,
    STANDARD_COLUMNS,
)

def test_normalize_domestic_data():
    sample_domestic_raw = {
        "items": [
            {
                "itemCode": "069500",
                "itemName": "KODEX 200",
                "currentPrice": "35,000",
                "changeRate": "+1.25%",
                "tradingValue": "50,000,000"
            },
            {
                "itemCode": "379800",
                "itemName": "KODEX 미국S&P500TR",
                "currentPrice": "18,000",
                "changeRate": "-0.50%",
                "tradingValue": "30,000,000"
            }
        ]
    }
    df = normalize_market_data(sample_domestic_raw, market="KRX")
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == STANDARD_COLUMNS
    assert len(df) == 2
    assert df.iloc[0]["ticker"] == "069500"
    assert df.iloc[0]["name"] == "KODEX 200"
    assert df.iloc[0]["current_price"] == 35000.0
    assert df.iloc[0]["change_rate"] == 1.25
    assert df.iloc[0]["trading_value"] == 50000000.0
    assert df.iloc[0]["market"] == "KRX"

def test_normalize_global_data_list():
    sample_global_raw = [
        {
            "reutersCode": "AAPL.O",
            "stockName": "Apple Inc",
            "closePrice": "220.50",
            "fluctuationsRatio": "2.10",
            "marketValue": "3,000,000,000"
        },
        {
            "symbolCode": "NVDA",
            "koreanCodeName": "엔비디아",
            "currentPrice": "125.00",
            "fluctuationsRatio": "-1.50",
            "accumulatedTradingValue": "2,500,000,000"
        }
    ]
    df = normalize_market_data(sample_global_raw, market="US")
    assert len(df) == 2
    assert df.iloc[0]["ticker"] == "AAPL"  # .O 접미사 제거 확인
    assert df.iloc[0]["current_price"] == 220.50
    assert df.iloc[1]["ticker"] == "NVDA"
    assert df.iloc[1]["name"] == "엔비디아"
    assert df.iloc[1]["market"] == "US"

def test_calculate_top3_quant():
    mock_df = get_mock_market_data("KRX")
    top3 = calculate_top3_quant(mock_df)
    assert isinstance(top3, pd.DataFrame)
    assert len(top3) == 3
    assert "total_score" in top3.columns
    assert "value_score" in top3.columns
    assert "supply_score" in top3.columns
    assert "reason" in top3.columns
    # 점수 내림차순 정렬 확인
    assert top3.iloc[0]["total_score"] >= top3.iloc[1]["total_score"]
    assert top3.iloc[1]["total_score"] >= top3.iloc[2]["total_score"]

def test_fetch_npay_items_returns_valid_dataframe():
    df_krx = fetch_npay_items("KRX")
    assert not df_krx.empty
    assert list(df_krx.columns) == STANDARD_COLUMNS

    df_us = fetch_npay_items("US")
    assert not df_us.empty
    assert list(df_us.columns) == STANDARD_COLUMNS
