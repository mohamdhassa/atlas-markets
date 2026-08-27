from app.services.automation import _canonical_symbol, _has_exposure, _open_symbols


def test_canonical_symbol_normalizes_fx_aliases():
    assert _canonical_symbol('EUR/USD') == 'EURUSD'
    assert _canonical_symbol(' eurusd ') == 'EURUSD'
    assert _canonical_symbol('EUR USD') == 'EURUSD'


def test_open_symbols_collapses_duplicate_positions():
    rows = [
        {'symbol': 'EURUSD', 'ticket': 1},
        {'symbol': 'EUR/USD', 'ticket': 2},
        {'symbol': 'eurusd', 'ticket': 3},
    ]
    assert _open_symbols(rows) == {'EURUSD'}


def test_existing_exposure_blocks_alias_of_same_instrument():
    open_symbols = {'EURUSD'}
    assert _has_exposure(open_symbols, 'EUR/USD') is True
    assert _has_exposure(open_symbols, 'EURUSD') is True
    assert _has_exposure(open_symbols, 'GBPUSD') is False


def test_quantity_filter_ignores_flat_positions():
    rows = [
        {'symbol': 'AAPL', 'quantity': 0},
        {'symbol': 'MSFT', 'quantity': 2},
    ]
    assert _open_symbols(rows, 'quantity') == {'MSFT'}
