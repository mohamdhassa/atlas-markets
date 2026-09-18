from app.api.routes_universe_engine import router


def test_unified_market_monitor_route_is_read_only_and_registered():
    route=next(r for r in router.routes if r.path=='/strategies/symbols/universe/market-monitor')
    assert 'GET' in route.methods


def test_market_monitor_source_keeps_analysis_and_execution_gate_separate():
    import inspect
    from app.api import routes_universe_engine
    source=inspect.getsource(routes_universe_engine.market_monitor)
    assert "'decision':decision" in source
    assert "'execution_gate':gate" in source
    assert "'execution_enabled':False" in source
    assert "['BYBIT','IBKR']" in source
