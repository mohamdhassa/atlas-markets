from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.api.routes_analysis import router
from app.services.shadow_monitor import _excursions


def test_long_and_short_excursions_are_direction_aware():
    candles = [{"high": 110.0, "low": 95.0}]
    long = SimpleNamespace(entry_price=100.0, action="BUY")
    short = SimpleNamespace(entry_price=100.0, action="SELL")
    assert _excursions(long, candles) == (10.0, -5.0)
    assert _excursions(short, candles) == (round((100 / 95 - 1) * 100, 6), round((100 / 110 - 1) * 100, 6))


def test_provider_coverage_route_is_registered():
    routes = {(route.path, frozenset(route.methods or set())) for route in router.routes}
    assert ("/analysis/shadow/coverage", frozenset({"GET"})) in routes


def test_v82_migration_extends_v81_head():
    migration = Path("migrations/versions/20260925_0019_shadow_provider_analytics.py").read_text(encoding="utf-8")
    assert 'revision = "20260925_0019"' in migration
    assert 'down_revision = "20260925_0018"' in migration
    assert '"shadow_scan_events"' in migration


def test_frontend_shows_provider_coverage_and_advanced_metrics():
    frontend = Path("app/static/management-workspaces.js").read_text(encoding="utf-8")
    assert "/analysis/shadow/coverage?days=7" in frontend
    assert "Provider and skipped-symbol details" in frontend
    assert "Profit factor" in frontend
    assert "Expectancy" in frontend


def test_shadow_monitor_remains_non_executing():
    source = Path("app/services/shadow_monitor.py").read_text(encoding="utf-8")
    assert "place_order(" not in source
    assert "execute_managed_spot_order" not in source
    assert "ShadowScanEvent(" in source
