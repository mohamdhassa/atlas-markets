from __future__ import annotations

import pytest

from app.market_data.bybit import BybitPublicMarketData


@pytest.mark.asyncio
async def test_tickers_are_normalized_and_filtered(monkeypatch) -> None:
    provider = BybitPublicMarketData("https://example.test")

    async def fake_get(path, params):
        assert path == "/v5/market/tickers"
        assert params["category"] == "linear"
        return {
            "retCode": 0,
            "result": {
                "list": [
                    {
                        "symbol": "ETHUSDT",
                        "lastPrice": "3200.5",
                        "bid1Price": "3200.4",
                        "ask1Price": "3200.6",
                        "price24hPcnt": "0.025",
                        "highPrice24h": "3250",
                        "lowPrice24h": "3100",
                        "volume24h": "12000",
                        "turnover24h": "38000000",
                    },
                    {"symbol": "OTHERUSDT", "lastPrice": "1"},
                ]
            },
        }

    monkeypatch.setattr(provider, "_get", fake_get)
    snapshot = await provider.get_tickers(symbols=("ETHUSDT",))
    assert snapshot.count == 1
    assert snapshot.tickers[0].symbol == "ETHUSDT"
    assert snapshot.tickers[0].last_price == 3200.5
    assert snapshot.tickers[0].change_24h_pct == 2.5


@pytest.mark.asyncio
async def test_candles_are_sorted_oldest_first(monkeypatch) -> None:
    provider = BybitPublicMarketData("https://example.test")

    async def fake_get(path, params):
        assert path == "/v5/market/kline"
        assert params["interval"] == "5"
        return {
            "retCode": 0,
            "result": {
                "list": [
                    ["2000", "101", "103", "100", "102", "12", "1224"],
                    ["1000", "100", "102", "99", "101", "10", "1010"],
                ]
            },
        }

    monkeypatch.setattr(provider, "_get", fake_get)
    candles = await provider.get_candles(symbol="btcusdt", interval="5m", limit=2)
    assert [c.timestamp_ms for c in candles] == [1000, 2000]
    assert candles[-1].symbol == "BTCUSDT"
    assert candles[-1].close == 102.0
