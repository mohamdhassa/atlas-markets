import asyncio
import copy
from types import SimpleNamespace as NS

import pytest
import httpx

from app.backtesting import spot_history as history
from app.backtesting import spot_walk_forward as model


def bundle(n=800):
    start = 1_798_761_600_000 // history.STEP_MS * history.STEP_MS
    candles = [dict(timestamp_ms=start+i*history.STEP_MS, open=100., high=101.,
                    low=99., close=100., volume=1000.) for i in range(n)]
    return {'schema_version': 1, 'provider': 'BYBIT', 'product': 'SPOT',
            'source_environment': 'MAINNET_PUBLIC', 'source_url': history.BASE_URL,
            'endpoint': '/v5/market/kline', 'symbol': 'BTCUSDT', 'interval': '5m',
            'start_ms': start, 'end_ms_exclusive': start+n*history.STEP_MS,
            'collected_at_ms': start+n*history.STEP_MS+1000, 'candles': candles,
            'candles_sha256': history.digest(candles),
            'instrument': {'symbol': 'BTCUSDT', 'quoteCoin': 'USDT',
                'lotSizeFilter': {'basePrecision': '.1','minOrderQty': '.1',
                                  'minOrderAmt': '1', 'maxMarketOrderQty': '100'}}}


def signal(side, blocked=None):
    return {'side': side, 'strength': 80, 'blocked': blocked,
            'route': {'strategy': 'trend', 'regime': 'TRENDING_UP' if side == 'BUY' else 'TRENDING_DOWN'}}


@pytest.mark.parametrize('change', ['futures','hash','missing','duplicate','forming','ohlc','nan','rules'])
def test_dataset_validation_rejects_invalid_or_wrong_product_history(change):
    b = bundle()
    if change == 'futures': b['product'] = 'LINEAR'
    elif change == 'hash': b['candles_sha256'] = 'wrong'
    elif change == 'forming': b['collected_at_ms'] = b['end_ms_exclusive'] - 1
    elif change == 'rules': b['instrument']['lotSizeFilter']['basePrecision'] = '0'
    else:
        if change == 'missing': b['candles'].pop(200)
        elif change == 'duplicate': b['candles'][200] = dict(b['candles'][199])
        elif change == 'ohlc': b['candles'][200]['low'] = 102
        elif change == 'nan': b['candles'][200]['close'] = float('nan')
        if change != 'nan': b['candles_sha256'] = history.digest(b['candles'])
    with pytest.raises(ValueError): model.validate_bundle(b)


def test_fills_use_next_open_and_charge_both_legs_once():
    rows, rules = model.validate_bundle(bundle())
    signals = [None] * len(rows)
    signals[199] = signal('BUY'); signals[201] = signal('SELL')
    rows[200]['open'] = 102
    result = model._simulate(rows, signals, 200, 210, model.PARAMS, rules, 100, 100, 100)
    trade = result['trades'][0]
    assert trade['index'] == 200 and trade['exit_index'] == 202
    assert trade['price'] == pytest.approx(103.02)
    assert trade['exit_price'] == 99
    assert trade['quantity'] == .2
    assert trade['pnl'] == pytest.approx(-1.20804)
    assert result['end_equity'] == pytest.approx(98.79196)
    assert model._metrics(result['trades'])['modeled_fees'] == pytest.approx(.40404)


def test_long_only_nonoverlap_and_no_forced_boundary_liquidation():
    rows, rules = model.validate_bundle(bundle())
    signals = [None] * len(rows)
    signals[199] = signal('SELL')  # No inventory: never opens a short.
    signals[200] = signal('BUY')
    for i in range(201, 210): signals[i] = signal('BUY')
    result = model._simulate(rows, signals, 200, 220, model.PARAMS, rules, 100, 10, 5)
    assert result['trades'] == []
    assert result['open_quantity'] == .2
    assert result['open_entry']['index'] == 201
    assert result['end_equity'] < 100


def test_router_and_strength_gates_and_minimum_order_rules():
    rows, rules = model.validate_bundle(bundle())
    signals = [None] * len(rows)
    signals[199] = signal('BUY', 'STRATEGY_ROUTER_NO_TRADE')
    signals[200] = dict(signal('BUY'), strength=60)
    result = model._simulate(rows, signals, 200, 210, model.PARAMS, rules, 100, 10, 5)
    assert result['open_quantity'] == 0
    signals[201] = signal('BUY')
    rules['minimum_notional'] = 50
    result = model._simulate(rows, signals, 200, 210, model.PARAMS, rules, 100, 10, 5)
    assert result['blockers'] == {'ENTRY_SIZE_OR_CASH': 1}


def test_validation_inventory_carries_across_folds_and_training_cannot_use_future(monkeypatch):
    b = bundle()
    signals = [None] * len(b['candles'])
    signals[399] = signal('BUY'); signals[649] = signal('SELL')
    monkeypatch.setattr(model, '_signals', lambda rows: signals)
    report = model.walk_forward_spot(b, capital=100, fee_bps=10, slippage_cases=[5],
                                     train_bars=200, test_bars=100)
    scenario = report['scenarios'][0]
    assert scenario['validation']['closed_trades'] == 1
    assert scenario['folds'][0]['training']['closed_trades'] == 0
    assert scenario['folds'][0]['validation']['closed_trades'] == 0
    assert scenario['folds'][2]['validation']['closed_trades'] == 1
    assert sum(f['validation']['closed_trades'] for f in scenario['folds']) == 1
    assert report['parameter_optimization'] is False
    assert report['executable'] is report['live_eligible'] is False
    for fold in scenario['folds']:
        assert fold['train_end_exclusive_ms'] == fold['test_start_ms']


def test_signal_windows_never_include_future_bars(monkeypatch):
    rows = bundle()['candles']
    calls = []
    def generate(window, **kwargs):
        calls.append([r['timestamp_ms'] for r in window])
        return NS(decision='BUY', strength=80)
    monkeypatch.setattr(model, 'generate_signal', generate)
    monkeypatch.setattr(model, 'route_strategy', NS(__wrapped__=lambda rows: {
        'strategy':'trend', 'regime':'TRENDING_UP'}))
    features = model._signals(rows)
    assert features[199]['side'] == 'BUY'
    assert len(calls[0]) == 200
    assert calls[0][-1] == rows[199]['timestamp_ms']
    assert calls[-1][-1] == rows[-2]['timestamp_ms']
    modified = copy.deepcopy(rows)
    for row in modified[500:]: row['close'] = 500
    assert model._signals(modified)[:500] == features[:500]


def test_cost_stress_runs_share_frozen_settings_and_features(monkeypatch):
    b = bundle(); signals = [None] * len(b['candles'])
    signals[399] = signal('BUY'); signals[401] = signal('SELL')
    calls=[]
    def features(rows): calls.append(1); return signals
    monkeypatch.setattr(model, '_signals', features)
    report = model.walk_forward_spot(b, capital=100, fee_bps=10, slippage_cases=[0,10],
                                     train_bars=200,test_bars=100)
    assert calls == [1]
    assert report['scenarios'][1]['validation']['net_realized_pnl'] < report['scenarios'][0]['validation']['net_realized_pnl']
    assert report['frozen_settings'] == model.PARAMS


def test_insufficient_samples_are_not_reported_as_success():
    with pytest.raises(ValueError, match='Insufficient'):
        model.walk_forward_spot(bundle(300), capital=100, fee_bps=10, slippage_cases=[5])


def test_public_collector_paginates_exact_spot_scope_and_preserves_closed_window(monkeypatch):
    b = bundle(12); calls=[]
    async def pause(*args): pass
    monkeypatch.setattr(history.asyncio, 'sleep', pause)
    async def get(client, path, params):
        calls.append((path,params))
        if path.endswith('instruments-info'): return {'category':'spot','list':[b['instrument']]}
        rows=[r for r in b['candles'] if r['timestamp_ms'] <= params['end']][-5:]
        return {'category':'spot','symbol':'BTCUSDT','list':[
            [str(r['timestamp_ms']),str(r['open']),str(r['high']),str(r['low']),
             str(r['close']),str(r['volume'])] for r in reversed(rows)]}
    monkeypatch.setattr(history, 'public_get', get)
    result=asyncio.run(history.collect_spot(None,'BTCUSDT',b['start_ms'],b['end_ms_exclusive']))
    assert result['candles'] == b['candles']
    assert result['candles_sha256'] == history.digest(b['candles'])
    assert len(result['pages']) == 3
    assert all(params['category'] == 'spot' for _,params in calls)
    assert calls[1][1]['end'] == b['end_ms_exclusive']-1


def test_public_collector_rejects_futures_response(monkeypatch):
    b = bundle(12)
    async def get(client,path,params):
        return {'category':'spot','list':[b['instrument']]} if path.endswith('instruments-info') else {'category':'linear','symbol':'BTCUSDT','list':[]}
    monkeypatch.setattr(history,'public_get',get)
    with pytest.raises(ValueError,match='provenance'):
        asyncio.run(history.collect_spot(None,'BTCUSDT',b['start_ms'],b['end_ms_exclusive']))


def test_public_get_never_uses_private_endpoints_and_timeout_does_not_fallback(monkeypatch):
    calls=[]
    async def pause(*args): pass
    monkeypatch.setattr(history.asyncio,'sleep',pause)
    async def get(path,params):
        calls.append(path)
        raise httpx.ReadTimeout('public read timed out')
    client=NS(get=get)
    with pytest.raises(ValueError,match='Unsupported'):
        asyncio.run(history.public_get(client,'/v5/order/create',{}))
    assert calls == []
    with pytest.raises(httpx.ReadTimeout):
        asyncio.run(history.public_get(client,'/v5/market/kline',{'category':'spot'}))
    assert calls == ['/v5/market/kline'] * 3


def test_public_rate_limit_retries_only_bounded_gets(monkeypatch):
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(429) if len(calls)==1 else httpx.Response(200,json={'retCode':0,'result':{'category':'spot'}})
    async def pause(*args): pass
    monkeypatch.setattr(history.asyncio,'sleep',pause)
    async def run():
        async with httpx.AsyncClient(base_url=history.BASE_URL,transport=httpx.MockTransport(handler)) as client:
            return await history.public_get(client,'/v5/market/kline',{'category':'spot'})
    assert asyncio.run(run()) == {'category':'spot'}
    assert len(calls)==2 and all(r.method=='GET' for r in calls)


def test_collector_detects_conflicting_duplicate_candles(monkeypatch):
    b=bundle(12)
    async def get(client,path,params):
        if path.endswith('instruments-info'): return {'category':'spot','list':[b['instrument']]}
        stamp=str(b['start_ms'])
        return {'category':'spot','symbol':'BTCUSDT','list':[
            [stamp,'100','101','99','100','1000'],[stamp,'100','102','99','101','1000']]}
    monkeypatch.setattr(history,'public_get',get)
    with pytest.raises(ValueError,match='Conflicting'):
        asyncio.run(history.collect_spot(None,'BTCUSDT',b['start_ms'],b['end_ms_exclusive']))


@pytest.mark.parametrize('code,recover,attempts', [(10016,True,3),(10016,False,3),
    (10006,True,3),(10000,True,3),(10001,False,1),(10009,False,1)])
def test_transient_api_codes_retry_but_permanent_errors_stop(monkeypatch,code,recover,attempts):
    calls=[]
    async def pause(*args): pass
    monkeypatch.setattr(history.asyncio,'sleep',pause)
    def handler(request):
        calls.append(request)
        if recover and len(calls)==3:
            return httpx.Response(200,json={'retCode':0,'result':{'category':'spot'}})
        return httpx.Response(200,json={'retCode':code,'retMsg':'public server message'})
    async def run():
        async with httpx.AsyncClient(base_url=history.BASE_URL,transport=httpx.MockTransport(handler)) as client:
            return await history.public_get(client,'/v5/market/kline',{'category':'spot'})
    if recover: assert asyncio.run(run()) == {'category':'spot'}
    else:
        with pytest.raises(ValueError,match=f'{code} public server message'): asyncio.run(run())
    assert len(calls)==attempts and all(r.method=='GET' for r in calls)


def test_each_history_request_has_at_most_one_page_time_span(monkeypatch):
    b=bundle(1200); calls=[]
    async def pause(*args): pass
    monkeypatch.setattr(history.asyncio,'sleep',pause)
    async def get(client,path,params):
        if path.endswith('instruments-info'): return {'category':'spot','list':[b['instrument']]}
        calls.append(params)
        rows=[r for r in b['candles'] if params['start'] <= r['timestamp_ms'] <= params['end']]
        return {'category':'spot','symbol':'BTCUSDT','list':[
            [str(r['timestamp_ms']),str(r['open']),str(r['high']),str(r['low']),str(r['close']),str(r['volume'])]
            for r in reversed(rows)]}
    monkeypatch.setattr(history,'public_get',get)
    result=asyncio.run(history.collect_spot(None,'BTCUSDT',b['start_ms'],b['end_ms_exclusive']))
    assert result['candles']==b['candles'] and len(calls)==3
    assert all(p['limit']==500 and p['end']-p['start'] < 500*history.STEP_MS for p in calls)


def test_exchange_clock_controls_closed_bar_cutoff_even_if_vm_clock_is_behind(monkeypatch):
    b=bundle()
    b['exchange_time_ms']=b['end_ms_exclusive']+1000
    b['collected_at_ms']=b['end_ms_exclusive']-3_600_000
    assert len(model.validate_bundle(b)[0])==800
    async def get(client,path,params):
        assert path=='/v5/market/time'
        return {'timeNano':str(b['exchange_time_ms']*1_000_000)}
    monkeypatch.setattr(history,'public_get',get)
    assert asyncio.run(history.exchange_time_ms(None))==b['exchange_time_ms']
    b['exchange_time_ms']=b['end_ms_exclusive']-1
    with pytest.raises(ValueError,match='forming'): model.validate_bundle(b)


def test_http_server_error_retry_is_bounded(monkeypatch):
    calls=[]
    async def pause(*args): pass
    monkeypatch.setattr(history.asyncio,'sleep',pause)
    def handler(request): calls.append(request); return httpx.Response(503)
    async def run():
        async with httpx.AsyncClient(base_url=history.BASE_URL,transport=httpx.MockTransport(handler)) as client:
            return await history.public_get(client,'/v5/market/time',{})
    with pytest.raises(httpx.HTTPStatusError): asyncio.run(run())
    assert len(calls)==3
