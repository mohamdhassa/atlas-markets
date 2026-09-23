from app.api import routes_automation

def test_actions_source_joins_broker_profiles():
    import inspect
    source = inspect.getsource(routes_automation.actions)
    assert "outerjoin(BrokerProfile" in source
    assert '"account_label"' in source
    assert '"external_account_ref"' in source
    assert '"connection_status"' in source
    assert '"broker"' in source
