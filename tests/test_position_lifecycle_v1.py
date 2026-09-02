from app.main import app
from app.services.position_lifecycle import _opposite_signal


def test_position_lifecycle_route_is_registered():
    routes = {(getattr(r, 'path', None), frozenset(getattr(r, 'methods', set()) or set())) for r in app.routes}
    assert ('/automation/positions/lifecycle', frozenset({'GET'})) in routes
    assert ('/automation/positions/mt5-exit-signals', frozenset({'GET'})) in routes


def test_position_lifecycle_is_read_only_surface():
    for path in ('/automation/positions/lifecycle', '/automation/positions/mt5-exit-signals'):
        route = next(r for r in app.routes if getattr(r, 'path', None) == path)
        methods = getattr(route, 'methods', set()) or set()
        assert 'GET' in methods
        assert 'POST' not in methods
        assert 'DELETE' not in methods


def test_opposite_signal_detection():
    assert _opposite_signal('BUY', 'SELL') is True
    assert _opposite_signal('SELL', 'BUY') is True
    assert _opposite_signal('BUY', 'BUY') is False
    assert _opposite_signal('SELL', 'HOLD') is False
