from pathlib import Path

def test_unscanned_research_has_no_fake_hold_decision():
    source=Path('app/api/routes_universe_engine.py').read_text()
    block=source.split("@router.get('/universe/market-monitor')",1)[1].split("@router.get('/universe/scan-preview')",1)[0]
    assert "decision=(analysis or {}).get('decision') if analysis else None" in block
    assert "or 'HOLD'" not in block

def test_ui_labels_unscanned_as_not_scanned():
    source=Path('app/static/unified-market-monitor-v71-1.js').read_text()
    assert "x.analysis_status==='NOT_SCANNED'?'NOT SCANNED'" in source
