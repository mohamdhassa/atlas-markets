from pathlib import Path

from app.services.ibkr_position_manager import _opposite


def test_ibkr_exit_direction_logic():
    assert _opposite('LONG','SELL') is True
    assert _opposite('SHORT','BUY') is True
    assert _opposite('LONG','BUY') is False
    assert _opposite('SHORT','SELL') is False
    assert _opposite('LONG','HOLD') is False


def test_ibkr_exit_manager_is_paper_owned_and_lifecycle_guarded():
    text=Path('app/services/ibkr_position_manager.py').read_text()
    assert "BrokerProfile.environment=='PAPER'" in text
    assert "entry is None" in text
    assert 'OWNERSHIP_NOT_VERIFIED' in text
    assert 'ENTRY_FILL_NOT_VERIFIED' in text
    assert "cfg.mode=='AUTO_TRADE'" in text
    assert 'close_position(' in text
    assert "result['status']='EXIT_EXECUTED'" in text


def test_ibkr_close_client_rechecks_simulation_and_position():
    text=Path('app/brokers/ibkr_bridge.py').read_text()
    assert 'async def close_position' in text
    assert "not health.get('simulation')" in text
    assert "raise RuntimeError('POSITION_CHANGED')" in text
    assert "raise RuntimeError('SYMBOL_ALREADY_HAS_OPEN_ORDER')" in text
    assert 'BROKER_WHATIF_REJECTED' in text


def test_ibkr_manager_started_by_app_lifespan():
    text=Path('app/main.py').read_text()
    assert 'from app.services.ibkr_position_manager import ibkr_position_manager_loop' in text
    assert 'asyncio.create_task(ibkr_position_manager_loop(stop))' in text
