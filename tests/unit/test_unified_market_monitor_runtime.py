from pathlib import Path


def test_market_monitor_uses_real_build_universe_contract():
    source=Path('app/api/routes_universe_engine.py').read_text()
    block=source.split("@router.get('/universe/market-monitor')",1)[1].split("@router.get('/universe/scan-preview')",1)[0]
    assert "build_universe(profiles=profiles, strategies=strategies" in block
    assert "u.provider" in block
    assert "u.market" in block
    assert "u.symbol" in block
    assert "u.get(" not in block


def test_unified_frontend_calls_market_monitor_endpoint():
    source=Path('app/static/unified-market-monitor-v71-1.js').read_text()
    assert "/strategies/symbols/universe/market-monitor" in source
    assert 'Decision:' in source
