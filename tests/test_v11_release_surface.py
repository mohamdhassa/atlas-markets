from pathlib import Path

from app.api.routes_symbol_strategies import router as symbol_strategy_router


def test_bulk_auto_trade_route_is_registered():
    matches=[r for r in symbol_strategy_router.routes if getattr(r,'path',None)=='/auto-trade/eligible']
    assert matches
    assert 'POST' in matches[0].methods
    main_source=Path('app/main.py').read_text(encoding='utf-8')
    assert 'app.include_router(symbol_strategies_router)' in main_source


def test_oracle_deployment_profile_is_present():
    root=Path(__file__).resolve().parents[1]
    compose=(root/'docker-compose.oracle.yml').read_text(encoding='utf-8')
    env=(root/'.env.oracle.example').read_text(encoding='utf-8')
    assert '127.0.0.1:8000:8000' in compose
    assert 'restart: unless-stopped' in compose
    assert 'ALLOW_LIVE_TRADING=false' in env
    assert 'DATABASE_URL=' in env
