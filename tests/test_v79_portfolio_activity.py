from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


def test_live_activity_keeps_timestamped_broker_fills_visible():
    js = (STATIC / "live-activity-v75.js").read_text()
    assert "x.created_at||x.executed_at||(Number(x.time)>0" in js
    assert "fills.slice(0,200)" in js
    assert ".slice(0,250).map(x=>({...x,kind:'DECISION'}))" in js
    assert ").slice(0,250);" not in js


def test_portfolio_derives_open_pnl_only_from_loaded_live_marks():
    js = (STATIC / "portfolio-v61.js").read_text()
    assert 'id="v61-open-pnl"' in js
    assert "values.length===ps.length&&ps.length" in js
    assert "Derived from current live market marks" in js
    assert "Unavailable until every live mark loads" in js
    assert "data-v61-mark" in js


def test_portfolio_routes_closed_results_to_canonical_performance_ledger():
    js = (STATIC / "portfolio-v61.js").read_text()
    assert "Open Performance ledger" in js
    assert "renderPage('Performance')" in js
    assert "CLOSED POSITIONS" not in js
    assert "Execution ledger" not in js
