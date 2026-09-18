from pathlib import Path

def _performance_bybit_block(source: str) -> str:
    performance = source.split("@router.get('/performance/broker-native')",1)[1]
    return performance.split("if p.provider=='BYBIT':",1)[1].split("elif p.provider=='MT5':",1)[0]

def test_bybit_performance_includes_persisted_executed_automation_actions():
    source=Path('app/api/routes_broker_native.py').read_text()
    assert 'from app.db.models.automation import AutomationAction' in source
    block=_performance_bybit_block(source)
    assert "AutomationAction.status=='EXECUTED'" in block
    assert "AutomationAction.provider=='BYBIT'" in block
    assert "'execution_source':'ATLAS_AUTOMATION_ACTION'" in block
    assert "'pnl_available':False" in block

def test_bybit_ledger_deduplicates_known_broker_order_ids():
    source=Path('app/api/routes_broker_native.py').read_text()
    block=_performance_bybit_block(source)
    assert 'existing_ids' in block
    assert 'if oid and oid in existing_ids:continue' in block


def test_bybit_reporting_enriches_actions_from_spot_execution_history():
    source=Path('app/api/routes_broker_native.py').read_text()
    block=_performance_bybit_block(source)
    assert 'c.spot_executions(order_id=oid,limit=100)' in block
    assert "f.get('execPrice')" not in block  # weighted price is derived from actual execValue / execQty
    assert "f.get('execValue')" in block
    assert "f.get('execQty')" in block
    assert "f.get('execFee')" in block
    assert "'notional':exec_value or None" in block
    assert "'execution_source':'BYBIT_SPOT_EXECUTION' if fills else 'ATLAS_AUTOMATION_ACTION'" in block

def test_bybit_reporting_matches_closed_spot_round_trips_for_pnl():
    source=Path('app/api/routes_broker_native.py').read_text()
    block=_performance_bybit_block(source)
    assert "inventory=defaultdict(list)" in block
    assert "if side=='BUY':inventory[key].append([qty,_f(price)])" in block
    assert "row['pnl_available']=True" in block

def test_bybit_client_has_read_only_spot_execution_endpoint():
    source=Path('app/brokers/bybit_private.py').read_text()
    assert 'async def spot_executions' in source
    assert '"/v5/execution/list"' in source
    assert 'params["orderId"]=str(order_id)' in source
