from app.api.routes_phase36_verified import _strategy_metrics


def _trade(pnl, closed_at):
    return {'realized_pnl': pnl, 'closed_at': closed_at}


def test_small_sample_remains_validating_even_when_profitable():
    trades = [_trade(10, f'2026-09-{i:02d}T00:00:00') for i in range(1, 6)]
    result = _strategy_metrics(trades)
    assert result['verified_trades'] == 5
    assert result['verified_realized_pnl'] == 50
    assert result['live_readiness'] == 'VALIDATING'
    assert 'INSUFFICIENT_VERIFIED_SAMPLE' in result['readiness_blockers']


def test_sufficient_profitable_sample_can_be_eligible():
    trades = []
    for i in range(1, 31):
        pnl = -5 if i % 5 == 0 else 10
        trades.append(_trade(pnl, f'2026-08-{i:02d}T00:00:00'))
    result = _strategy_metrics(trades)
    assert result['verified_trades'] == 30
    assert result['verified_realized_pnl'] > 0
    assert result['profit_factor'] >= 1.2
    assert result['verified_win_rate'] >= 40
    assert result['max_drawdown_pct'] <= 15
    assert result['live_readiness'] == 'ELIGIBLE'
    assert result['readiness_blockers'] == []


def test_sufficient_losing_sample_is_not_eligible():
    trades = []
    for i in range(1, 31):
        pnl = 4 if i <= 12 else -8
        trades.append(_trade(pnl, f'2026-07-{i:02d}T00:00:00'))
    result = _strategy_metrics(trades)
    assert result['verified_trades'] == 30
    assert result['verified_realized_pnl'] < 0
    assert result['live_readiness'] == 'NOT_ELIGIBLE'
    assert 'NON_POSITIVE_VERIFIED_PNL' in result['readiness_blockers']
