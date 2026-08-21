import pytest
from app.market_data.fx import TwelveDataFxMarketData

def test_fx_symbol_normalization():
    assert TwelveDataFxMarketData.provider_symbol("EURUSD")=="EUR/USD"
    assert TwelveDataFxMarketData.provider_symbol("gbp/usd")=="GBP/USD"

def test_fx_symbol_rejects_invalid():
    with pytest.raises(ValueError):TwelveDataFxMarketData.provider_symbol("BTCUSDT")

def test_fx_provider_requires_key():
    with pytest.raises(ValueError):TwelveDataFxMarketData("https://api.twelvedata.com","")
