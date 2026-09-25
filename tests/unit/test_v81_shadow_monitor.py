from pathlib import Path

from app.api.routes_analysis import router
from app.services.shadow_monitor import _rows,timeframe_seconds

def test_timeframe_seconds_are_bounded_and_normalized():
    assert timeframe_seconds("5m")==300
    assert timeframe_seconds("1h")==3600
    assert timeframe_seconds("bad")==300

def test_bridge_candles_are_normalized_in_time_order():
    result=_rows({"candles":[{"time":2,"open":2,"high":3,"low":1,"close":2.5},{"time":1,"open":1,"high":2,"low":0.5,"close":1.5}]})
    assert [x["timestamp_ms"] for x in result]==[1,2]
    assert result[-1]["close"]==2.5

def test_shadow_reporting_routes_are_registered():
    routes={(r.path,frozenset(r.methods or set())) for r in router.routes}
    assert ("/analysis/shadow/observations",frozenset({"GET"})) in routes
    assert ("/analysis/shadow/performance",frozenset({"GET"})) in routes

def test_shadow_monitor_has_no_execution_path():
    source=Path("app/services/shadow_monitor.py").read_text(encoding="utf-8")
    assert "place_order(" not in source
    assert "place_demo_order(" not in source
    assert "execute_managed_spot_order" not in source
    assert "ShadowObservation(" in source

def test_shadow_worker_and_dashboard_are_wired():
    main=Path("app/main.py").read_text(encoding="utf-8")
    frontend=Path("app/static/management-workspaces.js").read_text(encoding="utf-8")
    assert "asyncio.create_task(shadow_monitor_loop(stop))" in main
    assert "/analysis/shadow/performance?days=30" in frontend
    assert "Shadow decisions cannot submit orders" in frontend

def test_shadow_migration_extends_current_head():
    migration=Path("migrations/versions/20260925_0018_shadow_observations.py").read_text(encoding="utf-8")
    assert 'revision = "20260925_0018"' in migration
    assert 'down_revision = "20260913_0017"' in migration
