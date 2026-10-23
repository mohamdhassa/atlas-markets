import asyncio
from datetime import date, datetime, timezone
from types import SimpleNamespace as NS

import pytest
from fastapi import HTTPException
from app.api import routes_broker_native as native
from app.services.profit_chart import build_profit_chart, instrument_key


def row(symbol='TSLA', pnl=10, day='2026-10-01', **changes):
    return {'symbol':symbol,'provider':'IBKR','environment':'PAPER','market':'STOCK',
            'pnl':pnl,'pnl_available':True,
            'time':int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp()*1000),**changes}


def test_default_overall_uses_full_untruncated_recorded_history():
    data=build_profit_chart([row(pnl=1) for _ in range(350)])
    assert data['recorded_pnl']==350 and data['pnl_records']==350
    assert len(data['series'])==1 and data['series'][0]['label']=='Overall'
    assert data['start'] is data['end'] is None
    assert data['series'][0]['points'][0]['value']==0


def test_multiple_symbols_keep_common_timeline_and_selected_total():
    a,b=row(),row('AAPL',-3,day='2026-10-02')
    data=build_profit_chart([a,b,row('SPY',999)],symbols=[instrument_key(a),instrument_key(b)])
    assert data['recorded_pnl']==7
    assert len(data['series'])==3
    assert [s['points'][-1]['value'] for s in data['series']]==[7,-3,10]
    assert all([p['time'] for p in s['points']]==[p['time'] for p in data['series'][0]['points']] for s in data['series'])


def test_date_filter_is_inclusive_and_rebases_without_prior_profit():
    rows=[row(pnl=999,day='2026-09-30'),row(pnl=3),row(pnl=-2,day='2026-10-02'),row(pnl=999,day='2026-10-03')]
    data=build_profit_chart(rows,start=date(2026,10,1),end=date(2026,10,2))
    assert data['recorded_pnl']==1 and data['pnl_records']==2
    assert data['series'][0]['points'][0]['value']==0


@pytest.mark.parametrize('bad', [None,float('nan'),float('inf'),'bad'])
def test_unknown_pnl_does_not_become_zero(bad):
    data=build_profit_chart([row(pnl=bad)])
    assert data['series']==[] and data['recorded_pnl'] is None
    assert data['excluded_unknown_pnl_records']==1 and data['partial'] is True


def test_missing_pnl_flag_and_undated_records_are_explicit():
    data=build_profit_chart([row(pnl_available=False),row(time=None),row(time=1e30)])
    assert data['excluded_unknown_pnl_records']==1
    assert data['excluded_undated_records']==2
    assert data['series']==[]


def test_known_zero_is_valid_and_provider_failure_is_partial_without_secret_text():
    data=build_profit_chart([row(pnl=0)],errors=[{'provider':'IBKR','account':'Paper','error':'secret URL'}])
    assert data['recorded_pnl']==0
    assert data['partial'] is True
    assert 'secret' not in str(data)


def test_same_symbol_in_different_provider_environment_is_separate():
    a,b=row(),row(pnl=3,environment='LIVE')
    data=build_profit_chart([a,b],symbols=[instrument_key(a)])
    assert len(data['symbols'])==2 and data['recorded_pnl']==10


def test_symbol_without_known_pnl_is_not_drawn_as_flat_profit():
    a,b=row(),row('AAPL',pnl_available=False)
    data=build_profit_chart([a,b],symbols=[instrument_key(a),instrument_key(b)])
    assert len(data['series'])==2
    assert data['excluded_unknown_pnl_records']==1


@pytest.mark.asyncio
async def test_profit_endpoint_validates_dates_before_provider_requests(monkeypatch):
    async def forbidden(**kwargs):pytest.fail('Provider requested for invalid range')
    monkeypatch.setattr(native,'_broker_performance',forbidden)
    with pytest.raises(HTTPException) as exc:
        await native.profit_chart.__wrapped__(symbols=None,start=date(2026,10,3),end=date(2026,10,1),user=NS(),db=None)
    assert exc.value.status_code==400


@pytest.mark.asyncio
async def test_chart_uses_full_ledger_before_display_limit_and_rejects_other_ibkr_account(monkeypatch):
    p=NS(id=1,user_id=1,provider='IBKR',environment='PAPER',credentials_configured=True,
         account_label='Paper',simulation_capital_override_usd=None)
    class Broker:
        async def account(self):return {'equity':100,'available':100}
        async def executions(self,days):
            assert days==366
            return {'list':[{'account':'DU1','execution_id':str(i),'order_id':i,
                'symbol':'TSLA','side':'SLD','quantity':1,'price':100,
                'realized_pnl':1,'pnl_available':True,'time':'20261001  12:00:00'} for i in range(250)] +
                [{'account':'OTHER','symbol':'TSLA','realized_pnl':999,'pnl_available':True}]}
    monkeypatch.setattr(native,'_accounts',lambda db,user:[p])
    monkeypatch.setattr(native,'_symbol_market_map',lambda *args:{})
    monkeypatch.setattr(native,'_ibkr',lambda p:Broker())
    monkeypatch.setattr(native,'_creds',lambda p:{'account_id':'DU1'})
    monkeypatch.setattr(native,'_trade_context',lambda *args:pytest.fail('Chart should not fetch editorial context'))
    data=await native.profit_chart.__wrapped__(symbols=None,start=None,end=None,user=NS(role='USER',id=1),db=NS(scalars=lambda q:NS(all=lambda:[])))
    assert data['pnl_records']==250 and data['recorded_pnl']==250


def test_account_scope_still_limits_user_profiles():
    from sqlalchemy.dialects import postgresql
    seen=[]
    db=NS(scalars=lambda q:seen.append(q) or NS(all=lambda:[]))
    native._accounts(db,NS(role='USER',id=7))
    sql=str(seen[0].compile(dialect=postgresql.dialect()))
    assert 'broker_profiles.user_id =' in sql


def test_http_query_parsing_for_multiple_symbols_dates_and_limits(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.dependencies import get_current_user
    from app.db.session import get_db
    app=FastAPI()
    app.include_router(native.router)
    app.dependency_overrides[get_current_user]=lambda:NS(id=7,role='USER')
    app.dependency_overrides[get_db]=lambda:None
    seen=[]
    async def report(**kwargs):
        seen.append(kwargs)
        return build_profit_chart([],**kwargs['chart_request'])
    monkeypatch.setattr(native,'_broker_performance',report)
    client=TestClient(app)
    response=client.get('/performance/profit-chart',params=[('symbols','IBKR:PAPER:STOCK:TSLA'),('symbols','IBKR:PAPER:STOCK:AAPL'),('start','2026-10-01'),('end','2026-10-02')])
    assert response.status_code==200,response.text
    assert seen[0]['user'].id==7
    assert seen[0]['chart_request']['start']==date(2026,10,1)
    assert len(response.json()['selected_symbols'])==2
    assert client.get('/performance/profit-chart?start=invalid').status_code==422
    assert client.get('/performance/profit-chart',params=[('symbols',str(i)) for i in range(51)]).status_code==422


def test_insights_attribute_profit_giveback_and_daily_drawdown():
    data = build_profit_chart([
        row('TSLA', 100), row('AAPL', -160, day='2026-10-02'),
        row('TSLA', 20, day='2026-10-03'),
        row('SPY', 999, pnl_available=False),
    ])
    a = data['insights']
    assert a['peak_pnl'] == 100 and a['peak_day'] == '2026-10-01'
    assert a['current_drawdown'] == 140
    assert a['max_daily_drawdown'] == 160
    assert a['worst_day'] == {'date': '2026-10-02', 'pnl': -160}
    assert [(r['symbol'], r['pnl']) for r in a['loss_drivers_since_peak']] == [('AAPL', -160)]
    assert a['largest_loss_records'][0]['symbol'] == 'AAPL'
    assert data['partial']


def test_insights_follow_filters_and_rebase_from_zero():
    a, b = row('TSLA', 100), row('AAPL', -10, day='2026-10-02')
    data = build_profit_chart([a, b], symbols=[instrument_key(b)], start=date(2026, 10, 2))
    audit = data['insights']
    assert audit['peak_pnl'] == 0 and audit['peak_day'] is None
    assert audit['current_drawdown'] == audit['max_daily_drawdown'] == 10
    assert [r['symbol'] for r in audit['loss_drivers']] == ['AAPL']
    assert build_profit_chart([row(pnl=None)])['insights'] is None
    zero = build_profit_chart([row(pnl=0)])['insights']
    assert zero['worst_day'] is None and zero['current_drawdown'] == 0


def test_insights_aggregate_split_records_and_distinguish_environments():
    rows = [row('TSLA', 50), row('TSLA', -30, day='2026-10-02'),
            row('TSLA', -20, day='2026-10-02'),
            row('TSLA', -5, day='2026-10-02', environment='LIVE')]
    a = build_profit_chart(rows)['insights']
    assert a['worst_day']['pnl'] == -55
    assert [(r['environment'], r['pnl']) for r in a['loss_drivers_since_peak']] == [('PAPER', -50), ('LIVE', -5)]
    assert len(a['largest_loss_records']) == 3


def test_wins_distinguish_positive_records_from_net_symbol_and_day():
    a = build_profit_chart([
        row('TSLA', 100), row('TSLA', -150),
        row('AAPL', 20, day='2026-10-02'), row('AAPL', 30, day='2026-10-02'),
        row('SPY', 999, pnl_available=False),
    ])['insights']
    assert a['winning_records'] == 3 and a['winning_record_pnl'] == 150
    assert a['losing_records'] == 1 and a['losing_record_pnl'] == -150
    assert a['winning_record_pnl'] + a['losing_record_pnl'] == 0
    assert a['best_day'] == {'date': '2026-10-02', 'pnl': 50}
    assert [(r['symbol'], r['pnl']) for r in a['profit_contributors']] == [('AAPL', 50)]
    assert [r['pnl'] for r in a['largest_win_records']] == [100, 30, 20]
    assert a['largest_win_records'][0]['day'] == '2026-10-01'


def test_wins_follow_dates_symbols_and_keep_unknown_distinct_from_zero():
    b = row('AAPL', 10, day='2026-10-02', environment='LIVE')
    data = build_profit_chart([row('TSLA', 999), b, row('AAPL', -2, day='2026-10-03')],
                              symbols=[instrument_key(b)], start=date(2026, 10, 2))
    a = data['insights']
    assert a['winning_records'] == 1 and a['winning_record_pnl'] == 10
    assert a['profit_contributors'][0]['environment'] == 'LIVE'
    for pnl in [0, -10]:
        a = build_profit_chart([row(pnl=pnl)])['insights']
        assert a['best_day'] is None and a['winning_records'] == 0
        assert a['largest_win_records'] == a['profit_contributors'] == []
    assert build_profit_chart([row(pnl=None)])['insights'] is None


def test_wins_rank_and_limit_records_without_merging_environments():
    rows = [row('TSLA', i+1, environment='PAPER' if i%2 else 'LIVE') for i in range(8)]
    a = build_profit_chart(rows)['insights']
    assert [r['pnl'] for r in a['largest_win_records']] == [8, 7, 6, 5, 4]
    assert a['winning_records'] == 8
    assert {(r['environment'], r['pnl']) for r in a['profit_contributors']} == {('PAPER', 20), ('LIVE', 16)}
