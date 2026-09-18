from pathlib import Path

def test_bybit_performance_includes_persisted_executed_automation_actions():
    source=Path('app/api/routes_broker_native.py').read_text()
    assert 'from app.db.models.automation import AutomationAction' in source
    block=source.split("if p.provider=='BYBIT':",1)[1].split("elif p.provider=='MT5':",1)[0]
    assert "AutomationAction.status=='EXECUTED'" in block
    assert "AutomationAction.provider=='BYBIT'" in block
    assert "'execution_source':'ATLAS_AUTOMATION_ACTION'" in block
    assert "'pnl_available':False" in block

def test_bybit_ledger_deduplicates_known_broker_order_ids():
    source=Path('app/api/routes_broker_native.py').read_text()
    block=source.split("if p.provider=='BYBIT':",1)[1].split("elif p.provider=='MT5':",1)[0]
    assert 'existing_ids' in block
    assert 'if oid and oid in existing_ids:continue' in block
