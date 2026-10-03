from pathlib import Path

from app.api.routes_broker_native import _pair_execution_lots


def test_fifo_trade_pairing_adds_entry_investment_duration_and_return():
    rows = [
        {
            "profile_id": "profile-1",
            "provider": "IBKR",
            "symbol": "IWM",
            "side": "BOT",
            "quantity": 1,
            "execution_price": 280.12,
            "time": 1_000_000,
            "pnl_available": False,
        },
        {
            "profile_id": "profile-1",
            "provider": "IBKR",
            "symbol": "IWM",
            "side": "SLD",
            "quantity": 1,
            "execution_price": 281.57,
            "time": 1_360_000,
            "pnl": 0.444197,
            "pnl_available": True,
        },
    ]

    result = _pair_execution_lots(rows)
    closed = result[1]

    assert closed["entry_price"] == 280.12
    assert closed["invested_amount"] == 280.12
    assert closed["opened_at"] == 1_000_000
    assert closed["closed_at"] == 1_360_000
    assert closed["duration_seconds"] == 360
    assert closed["return_pct"] == round(0.444197 / 280.12 * 100, 4)


def test_frontend_has_one_users_page_and_one_trade_ledger():
    app = Path("app/static/app.js").read_text(encoding="utf-8")
    polish = Path("app/static/final-polish.js").read_text(encoding="utf-8")
    portfolio = Path("app/static/portfolio-v61.js").read_text(encoding="utf-8")
    performance = Path("app/static/live-pages.js").read_text(encoding="utf-8")

    assert app.count("async function usersPage") == 1
    assert "polishedUsers" not in polish
    assert "DAILY_REFERENCE" not in portfolio
    assert "Daily performance reference" not in portfolio
    assert "Execution ledger" not in portfolio
    assert "Open Performance ledger" in portfolio
    assert "TRADE & PERFORMANCE LEDGER" in performance
    for label in ("Starting capital", "Strategy value", "Duration", "Invested", "News context", "Attribution"):
        assert label in performance
