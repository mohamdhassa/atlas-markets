import pytest

from app.brokers.bybit_private import BybitPrivateClient, BybitPrivateError


@pytest.mark.asyncio
async def test_spot_certification_refuses_live_endpoint():
    client = BybitPrivateClient("key", "secret", "https://api.bybit.com")
    with pytest.raises(BybitPrivateError, match="refuses Spot certification"):
        await client.place_test_spot_market_order(symbol="BTCUSDT", side="Buy", qty=0.0001)


@pytest.mark.asyncio
async def test_spot_certification_rejects_invalid_side():
    client = BybitPrivateClient("key", "secret", "https://api-testnet.bybit.com")
    with pytest.raises(BybitPrivateError, match="INVALID_SPOT_SIDE"):
        await client.place_test_spot_market_order(symbol="BTCUSDT", side="Hold", qty=0.0001)
