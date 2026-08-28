from app.services.autotrade_preflight import _mt5_check_ok


def test_mt5_preflight_accepts_success_retcode_zero():
    assert _mt5_check_ok({'result': {'retcode': 0}}) is True


def test_mt5_preflight_accepts_done_retcode():
    assert _mt5_check_ok({'result': {'retcode': 10009}}) is True


def test_mt5_preflight_rejects_missing_or_failed_retcode():
    assert _mt5_check_ok({'result': {'retcode': 10030}}) is False
    assert _mt5_check_ok({'result': {}}) is False
