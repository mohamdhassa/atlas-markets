from datetime import datetime, timedelta, timezone

from app.services.performance import performance_summary


def test_performance_summary_calculates_core_metrics():
    now=datetime.now(timezone.utc)
    rows=[
        {"symbol":"BTCUSDT","realized_pnl":500.0,"created_at":now-timedelta(hours=2)},
        {"symbol":"BTCUSDT","realized_pnl":-200.0,"created_at":now-timedelta(hours=1)},
        {"symbol":"ETHUSDT","realized_pnl":300.0,"created_at":now-timedelta(days=10)},
        {"symbol":"ETHUSDT","realized_pnl":None,"created_at":now},
    ]
    p=performance_summary(rows,100000.0)
    assert p["closed_trades"]==3
    assert p["wins"]==2
    assert p["losses"]==1
    assert round(p["win_rate"],2)==66.67
    assert p["gross_profit"]==800.0
    assert p["gross_loss"]==200.0
    assert p["profit_factor"]==4.0
    assert p["total_realized_pnl"]==600.0
    assert p["daily_pnl"]==300.0
    assert p["weekly_pnl"]==300.0
    assert p["monthly_pnl"]==600.0
    assert len(p["equity_curve"])==3
    assert p["by_symbol"][0]["symbol"] in {"BTCUSDT","ETHUSDT"}


def test_profit_factor_is_none_without_losses():
    now=datetime.now(timezone.utc)
    p=performance_summary([{"symbol":"BTCUSDT","realized_pnl":100.0,"created_at":now}],100000.0)
    assert p["profit_factor"] is None
    assert p["max_drawdown_pct"]==0.0
