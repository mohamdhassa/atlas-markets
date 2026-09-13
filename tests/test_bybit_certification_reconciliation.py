from app.api.routes_bybit_certification_state import _certification_evidence


def test_certification_evidence_requires_atlas_prefix_and_fill():
    history = [
        {"orderLinkId": "manual-order", "orderStatus": "Filled", "side": "Buy", "orderId": "1", "symbol": "BTCUSDT"},
        {"orderLinkId": "atlas-spot-cert-buy", "orderStatus": "Cancelled", "side": "Buy", "orderId": "2", "symbol": "BTCUSDT"},
        {"orderLinkId": "atlas-spot-cert-buy2", "orderStatus": "Filled", "side": "Buy", "orderId": "3", "symbol": "BTCUSDT"},
        {"orderLinkId": "atlas-spot-cert-sell", "orderStatus": "PartiallyFilled", "side": "Sell", "orderId": "4", "symbol": "BTCUSDT"},
    ]

    evidence = _certification_evidence(history)

    assert evidence["buy"] is True
    assert evidence["sell"] is True
    assert [row["order_id"] for row in evidence["matched"]] == ["3", "4"]


def test_certification_evidence_does_not_accept_one_direction_only():
    history = [
        {"orderLinkId": "atlas-spot-cert-buy", "orderStatus": "Filled", "side": "Buy", "orderId": "1", "symbol": "BTCUSDT"},
    ]

    evidence = _certification_evidence(history)

    assert evidence["buy"] is True
    assert evidence["sell"] is False
