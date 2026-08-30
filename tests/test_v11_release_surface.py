from pathlib import Path

from app.main import app
from app.api.routes_symbol_strategies import router as symbol_strategy_router


def test_bulk_auto_trade_route_is_registered():
    router_matches=[r for r in symbol_strategy_router.routes if str(getattr(r,'path','')).endswith('/auto-trade/eligible')]
    assert router_matches
    assert 'POST' in router_matches[0].methods
    app_matches=[r for r in app.routes if str(getattr(r,'path','')).endswith('/auto-trade/eligible')]
    assert app_matches
    assert 'POST' in app_matches[0].methods


def test_oracle_deployment_profile_is_present():
    root=Path(__file__).resolve().parents[1]
    compose=(root/'docker-compose.oracle.yml').read_text(encoding='utf-8')
    env=(root/'.env.oracle.example').read_text(encoding='utf-8')
    assert '127.0.0.1:8000:8000' in compose
    assert 'restart: unless-stopped' in compose
    assert 'ALLOW_LIVE_TRADING=false' in env
    assert 'DATABASE_URL=' in env
