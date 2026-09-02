from app.main import app


def test_position_lifecycle_route_is_registered():
    routes = {(getattr(r, 'path', None), frozenset(getattr(r, 'methods', set()) or set())) for r in app.routes}
    assert ('/automation/positions/lifecycle', frozenset({'GET'})) in routes


def test_position_lifecycle_is_read_only_surface():
    route = next(r for r in app.routes if getattr(r, 'path', None) == '/automation/positions/lifecycle')
    assert 'POST' not in (getattr(route, 'methods', set()) or set())
    assert 'DELETE' not in (getattr(route, 'methods', set()) or set())
