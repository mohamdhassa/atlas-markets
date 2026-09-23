from types import SimpleNamespace

from app.api.routes_phase36_verified import _match_action
from app.api.routes_broker_native import _execution_time_ms


def _action(
    action_id,
    *,
    profile="profile-1",
    market="STOCK",
    symbol="SPY",
    order_id=None,
    position_id=None,
):
    return SimpleNamespace(
        id=action_id,
        broker_profile_id=profile,
        market=market,
        symbol=symbol,
        broker_order_id=order_id,
        broker_position_id=position_id,
        raw_json=None,
    )


def _trade(**overrides):
    row = {
        "profile_id": "profile-1",
        "market": "STOCK",
        "symbol": "SPY",
        "position_id": "",
    }
    row.update(overrides)
    return row


def test_unique_ibkr_order_id_matches_exact_action():
    a = _action("a1", order_id="474")

    matched, method = _match_action(
        _trade(),
        {"474"},
        [a],
    )

    assert matched is a
    assert method == "BROKER_ORDER_ID"


def test_duplicate_ibkr_order_id_is_ambiguous():
    a1 = _action("a1", order_id="273")
    a2 = _action("a2", order_id="273")

    matched, method = _match_action(
        _trade(),
        {"273"},
        [a1, a2],
    )

    assert matched is None
    assert method == "AMBIGUOUS_BROKER_ORDER_ID"


def test_unknown_ibkr_order_id_is_not_verified():
    a = _action("a1", order_id="474")

    matched, method = _match_action(
        _trade(),
        {"999999"},
        [a],
    )

    assert matched is None
    assert method is None


def test_unique_broker_position_id_matches():
    a = _action("a1", position_id="POS-100")

    matched, method = _match_action(
        _trade(position_id="POS-100"),
        set(),
        [a],
    )

    assert matched is a
    assert method == "BROKER_POSITION_ID"


def test_duplicate_broker_position_id_is_ambiguous():
    a1 = _action("a1", position_id="POS-100")
    a2 = _action("a2", position_id="POS-100")

    matched, method = _match_action(
        _trade(position_id="POS-100"),
        set(),
        [a1, a2],
    )

    assert matched is None
    assert method == "AMBIGUOUS_BROKER_POSITION_ID"


def test_ibkr_exit_action_can_match_closing_execution():
    exit_action = _action(
        "exit-1",
        order_id="465",
        symbol="MSFT",
    )
    exit_action.status = "EXIT_EXECUTED"

    trade = _trade(
        symbol="MSFT",
        position_id="465",
    )

    matched, method = _match_action(
        trade,
        {"465"},
        [exit_action],
    )

    assert matched is exit_action
    assert method == "BROKER_ORDER_ID"
    assert matched.status == "EXIT_EXECUTED"


def test_ibkr_execution_time_preserves_milliseconds():
    assert _execution_time_ms({"time": 1_790_200_000_123}) == 1_790_200_000_123


def test_ibkr_execution_time_normalizes_epoch_seconds():
    assert _execution_time_ms({"timestamp": 1_790_200_000}) == 1_790_200_000_000


def test_ibkr_execution_time_parses_iso_timestamp():
    assert _execution_time_ms({"executed_at": "2026-09-24T01:02:03Z"}) == 1_790_211_723_000


def test_ibkr_execution_time_missing_is_explicitly_unknown():
    assert _execution_time_ms({"symbol": "SPY"}) == 0
