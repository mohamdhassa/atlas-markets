import pytest

from app.services.universe_scanner import scan_mode_allowed
from app.services.universe_seed import normalize_seed_mode


def test_validated_seed_allows_watch_and_signals_only():
    assert normalize_seed_mode('watch') == 'WATCH'
    assert normalize_seed_mode('SIGNALS') == 'SIGNALS'
    with pytest.raises(ValueError):
        normalize_seed_mode('AUTO_TRADE')


def test_scan_preview_defaults_to_signals_only():
    assert scan_mode_allowed('SIGNALS') is True
    assert scan_mode_allowed('WATCH') is False
    assert scan_mode_allowed('AUTO_TRADE') is False


def test_scan_preview_can_include_watch_but_never_auto_trade():
    assert scan_mode_allowed('WATCH', include_watch=True) is True
    assert scan_mode_allowed('SIGNALS', include_watch=True) is True
    assert scan_mode_allowed('AUTO_TRADE', include_watch=True) is False
