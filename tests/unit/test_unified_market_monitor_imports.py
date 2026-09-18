from pathlib import Path


def test_universe_engine_imports_symbol_strategy_used_by_market_monitor():
    source=Path('app/api/routes_universe_engine.py').read_text()
    assert 'from app.db.models.symbol_strategy import SymbolStrategy' in source
    block=source.split("@router.get('/universe/market-monitor')",1)[1].split("@router.get('/universe/scan-preview')",1)[0]
    assert 'select(SymbolStrategy)' in block


def test_market_monitor_module_imports_cleanly():
    import app.api.routes_universe_engine as module
    assert module.SymbolStrategy is not None
