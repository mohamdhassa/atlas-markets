import uuid
from app.schemas.broker_profile import BrokerProfileCreate
from app.api.routes_accounts import PROVIDER_ENVIRONMENTS,TRADING_PROVIDERS

def test_twelve_data_is_frontend_provider():
    p=BrokerProfileCreate(account_label="Twelve Data",provider="TWELVE_DATA",environment="LIVE")
    assert p.provider=="TWELVE_DATA"
    assert PROVIDER_ENVIRONMENTS["TWELVE_DATA"]=={"LIVE"}
    assert "TWELVE_DATA" not in TRADING_PROVIDERS

def test_demo_and_live_profiles_can_coexist_by_schema():
    owner=uuid.uuid4()
    demo=BrokerProfileCreate(account_label="Fusion Demo",provider="MT5",environment="DEMO",owner_user_id=owner)
    live=BrokerProfileCreate(account_label="Fusion Live",provider="MT5",environment="LIVE",owner_user_id=owner)
    assert demo.environment=="DEMO" and live.environment=="LIVE"
    assert PROVIDER_ENVIRONMENTS["MT5"]=={"DEMO","LIVE"}

def test_bybit_supports_test_and_live_modes():
    assert {"DEMO","TESTNET","LIVE"}==PROVIDER_ENVIRONMENTS["BYBIT"]
