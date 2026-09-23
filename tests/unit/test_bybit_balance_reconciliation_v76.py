from app.services.bybit_spot_execution import _base_coin, _wallet_coin_quantity


def test_base_coin_for_supported_spot_quotes():
    assert _base_coin("ETHUSDT") == "ETH"
    assert _base_coin("SOL/USDT") == "SOL"


def test_wallet_coin_quantity_reads_wallet_balance():
    wallet = {
        "list": [
            {
                "coin": [
                    {"coin": "ETH", "walletBalance": "0.08789386"},
                    {"coin": "SOL", "walletBalance": "2.049948"},
                ]
            }
        ]
    }
    assert _wallet_coin_quantity(wallet, "ETH") == 0.08789386
    assert _wallet_coin_quantity(wallet, "SOL") == 2.049948


def test_wallet_coin_quantity_missing_or_negative_is_zero():
    wallet = {"list": [{"coin": [{"coin": "ETH", "walletBalance": "-1"}]}]}
    assert _wallet_coin_quantity(wallet, "ETH") == 0.0
    assert _wallet_coin_quantity(wallet, "SOL") == 0.0
