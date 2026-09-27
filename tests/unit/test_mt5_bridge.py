from app.brokers.mt5_bridge import Mt5BridgeClient

def test_mt5_bridge_headers_and_url():
    c=Mt5BridgeClient('http://host.docker.internal:8765/','abc')
    assert c.base_url=='http://host.docker.internal:8765'
    assert c._headers()['X-ATLAS-BRIDGE-TOKEN']=='abc'
