from app.services.safe_automation import automation_certification_blocker


def test_mt5_demo_is_certified_for_automation():
    assert automation_certification_blocker('MT5', 'DEMO') is None


def test_mt5_live_is_not_certified_for_automation():
    assert automation_certification_blocker('MT5', 'LIVE') == 'AUTOMATION_ROUTE_NOT_CERTIFIED'


def test_ibkr_paper_is_certified_for_automation():
    assert automation_certification_blocker('IBKR', 'PAPER') is None


def test_ibkr_live_remains_blocked():
    assert automation_certification_blocker('IBKR', 'LIVE') == 'IBKR_PAPER_ONLY_CERTIFIED'


def test_bybit_testnet_is_certified_route():
    assert automation_certification_blocker('BYBIT', 'TESTNET') is None


def test_bybit_demo_is_certified_route():
    assert automation_certification_blocker('BYBIT', 'DEMO') is None


def test_bybit_live_remains_blocked():
    assert automation_certification_blocker('BYBIT', 'LIVE') == 'BYBIT_SIMULATION_ONLY_CERTIFIED'
