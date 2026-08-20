from app.brokers.bybit_private import BybitPrivateClient


def test_private_headers_contain_required_bybit_auth_fields() -> None:
    client = BybitPrivateClient("api-key-123", "secret-456", "https://api-testnet.bybit.com")
    headers = client._headers("accountType=UNIFIED")
    assert headers["X-BAPI-API-KEY"] == "api-key-123"
    assert headers["X-BAPI-RECV-WINDOW"] == "5000"
    assert headers["X-BAPI-TIMESTAMP"].isdigit()
    assert len(headers["X-BAPI-SIGN"]) == 64
