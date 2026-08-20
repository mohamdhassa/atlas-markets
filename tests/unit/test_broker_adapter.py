import inspect

from app.brokers.base import BrokerAdapter


def test_broker_adapter_is_abstract() -> None:
    assert inspect.isabstract(BrokerAdapter)


def test_broker_adapter_contract_contains_required_methods() -> None:
    required = {
        "connect",
        "disconnect",
        "test_connection",
        "get_account",
        "get_balance",
        "get_positions",
        "get_orders",
        "get_instruments",
        "get_quote",
        "get_candles",
        "stream_prices",
        "place_order",
        "cancel_order",
        "close_position",
        "modify_stop",
        "modify_take_profit",
    }
    assert required.issubset(set(BrokerAdapter.__abstractmethods__))
