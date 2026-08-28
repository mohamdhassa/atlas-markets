from app.services.safe_automation import automation_certification_blocker


def test_mt5_demo_is_certified_for_automation():
    assert automation_certification_blocker('MT5', 'DEMO') is None


def test_mt5_live_is_not_certified_for_automation():
    assert automation_certification_blocker('MT5', 'LIVE') == 'AUTOMATION_ROUTE_NOT_CERTIFIED'


def test_ibkr_paper_is_certified_for_automation():
    assert automation_certification_blocker('IBKR', 'PAPER') is None


def test_ibkr_live_remains_blocked():
    assert automation_certification_blocker('IBKR', 'LIVE') == 'AUTOMATION_ROUTE_NOT_CERTIFIED'


def test_bybit_remains_hard_blocked():
    assert automation_certification_blocker('BYBIT', 'TESTNET') == 'PROVIDER_EXECUTION_NOT_CERTIFIED'
