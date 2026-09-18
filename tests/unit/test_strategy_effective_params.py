from types import SimpleNamespace

from app.api.routes_symbol_strategies import list_effective_symbol_strategies


def test_effective_endpoint_is_registered_before_row_id_route():
    from app.api.routes_symbol_strategies import router
    paths=[r.path for r in router.routes]
    assert '/strategies/symbols/effective' in paths
    assert paths.index('/strategies/symbols/effective') < paths.index('/strategies/symbols/{row_id}')
