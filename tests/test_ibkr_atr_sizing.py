from types import SimpleNamespace as NS
import pytest
from app.core.config import Settings
from app.services.ibkr_atr_sizing import sizing_atr
from app.services.paper_execution import build_execution_plan


def bars(width=2):
    return [dict(high=100+width, low=100-width, close=100,
                 bar_end_ms=i*300000) for i in range(15)]


def settings(**kwargs):
    return NS(ibkr_paper_atr_sizing_enabled=True, allow_live_trading=False, **kwargs)


def plan(side, value):
    return build_execution_plan(decision=side, price=100, equity=10000,
        available_cash=10000, risk_per_trade_pct=1, atr=value,
        stop_atr_multiplier=1.5, take_profit_rr=2, max_position_notional_pct=20)


@pytest.mark.parametrize('side', ['BUY', 'SELL'])
def test_measured_atr_changes_geometry_and_preserves_risk_and_notional(side):
    value, proof = sizing_atr(settings(), 'PAPER', bars())
    assert value == 4 and proof['basis'] == 'COMPLETED_CANDLE_ATR'
    baseline, candidate = plan(side, None), plan(side, value)
    assert abs(100-baseline.stop_loss) == 1.5
    assert abs(100-candidate.stop_loss) == 6
    assert candidate.quantity * abs(100-candidate.stop_loss) <= candidate.risk_amount + 1e-6
    assert candidate.notional <= 2000
    assert abs(candidate.take_profit-100) == 2*abs(candidate.stop_loss-100)


def test_default_retains_baseline_without_requiring_new_candle_fields():
    assert Settings(_env_file=None).ibkr_paper_atr_sizing_enabled is False
    value, proof = sizing_atr(NS(), 'PAPER', [])
    assert value is None and proof['basis'] == 'PRICE_PERCENT_FALLBACK'


@pytest.mark.parametrize('environment,live', [('LIVE',False),('DEMO',False),('PAPER',True)])
def test_candidate_cannot_cross_paper_live_boundary(environment, live):
    with pytest.raises(ValueError, match='PAPER_ONLY'):
        sizing_atr(NS(ibkr_paper_atr_sizing_enabled=True,allow_live_trading=live),
                   environment, bars())


@pytest.mark.parametrize('change', ['missing','nan','inverted','flat'])
def test_enabled_candidate_blocks_invalid_atr_instead_of_silent_fallback(change):
    rows=bars()
    if change=='missing':rows[-1].pop('high')
    if change=='nan':rows[-1]['high']=float('nan')
    if change=='inverted':rows[-1]['low']=200
    if change=='flat':rows=[dict(high=100,low=100,close=100)]*15
    with pytest.raises(ValueError, match='ATR_UNAVAILABLE'):
        sizing_atr(settings(),'PAPER',rows)


def test_atr_warmup_floor_and_prior_close_gap():
    with pytest.raises(ValueError,match='HISTORY_INSUFFICIENT'):
        sizing_atr(settings(),'PAPER',bars()[:14])
    value,_=sizing_atr(settings(),'PAPER',bars(.01))
    assert abs(plan('BUY',value).stop_loss-100)==.5
    rows=bars();rows[-1]=dict(high=112,low=108,close=110)
    value,_=sizing_atr(settings(),'PAPER',rows)
    assert value==pytest.approx((13*4+12)/14)
