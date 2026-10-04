import httpx
import pytest

from app.brokers.ibkr_bridge import IbkrBridgeClient


def rejected(code, detail):
    response = httpx.Response(code, json={'detail': detail}, request=httpx.Request('GET', 'http://bridge/account'))
    return httpx.HTTPStatusError('rejected', request=response.request, response=response)


@pytest.mark.asyncio
async def test_busy_account_read_retries_until_fresh_result(monkeypatch):
    client = IbkrBridgeClient('http://bridge')
    calls = []

    async def get(path):
        calls.append(path)
        if len(calls) < 3:
            raise rejected(503, 'IBKR account summary already in progress; retry shortly')
        return {'account_id': 'paper-test', 'equity': 100, 'simulation': True}

    monkeypatch.setattr(client, '_get', get)
    assert (await client.account())['equity'] == 100
    assert calls == ['/account'] * 3


@pytest.mark.asyncio
@pytest.mark.parametrize('code,detail', [(503, 'IBKR disconnected'), (502, 'IBKR account summary rejected'), (401, 'Unauthorized'), (503, 'Other failure')])
async def test_real_provider_errors_are_not_retried(monkeypatch, code, detail):
    client = IbkrBridgeClient('http://bridge')
    calls = []

    async def get(path):
        calls.append(path)
        raise rejected(code, detail)

    monkeypatch.setattr(client, '_get', get)
    with pytest.raises(httpx.HTTPStatusError):
        await client.account()
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_busy_wait_is_bounded(monkeypatch):
    client = IbkrBridgeClient('http://bridge', timeout=.02)

    async def get(path):
        raise rejected(503, 'IBKR account summary already in progress; retry shortly')

    monkeypatch.setattr(client, '_get', get)
    with pytest.raises(RuntimeError, match='IBKR_ACCOUNT_READ_TIMEOUT'):
        await client.account()


@pytest.mark.asyncio
async def test_order_preflight_is_never_retried(monkeypatch):
    client = IbkrBridgeClient('http://bridge')
    calls = []

    async def post(path, payload):
        calls.append(path)
        raise rejected(503, 'IBKR account summary already in progress; retry shortly')

    monkeypatch.setattr(client, '_post', post)
    with pytest.raises(httpx.HTTPStatusError):
        await client.order_check({'symbol': 'MSFT'})
    assert calls == ['/order-check']
