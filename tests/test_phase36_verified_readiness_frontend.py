from pathlib import Path


def test_phase36_shows_verified_live_readiness():
    js = Path('app/static/phase36.js').read_text(encoding='utf-8')
    assert '/strategies/performance/verified?days=30' in js
    assert 'Verified Live-Readiness' in js
    assert 'LIVE MONEY LOCKED' in js
    assert 'profit factor' in js.lower()
    assert 'max_drawdown_pct' in js
    assert 'readiness_blockers' in js
    assert 'Eligibility is evidence only and never unlocks Live Money automatically.' in js
