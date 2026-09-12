from app.brokers.bybit_private import BybitPrivateClient


def test_spot_holdings_from_wallet_excludes_cash_and_zero_assets():
    wallet={"list":[{"coin":[
        {"coin":"USDT","walletBalance":"1203.77","usdValue":"1203.77"},
        {"coin":"BTC","walletBalance":"0.000129","usdValue":"9.98"},
        {"coin":"ETH","walletBalance":"0","usdValue":"0"},
    ]}]}
    holdings=BybitPrivateClient.spot_holdings_from_wallet(wallet)
    assert holdings==[{"coin":"BTC","quantity":0.000129,"usd_value":9.98,"available_to_withdraw":None}]


def test_spot_holdings_empty_wallet_is_safe():
    assert BybitPrivateClient.spot_holdings_from_wallet({})==[]
