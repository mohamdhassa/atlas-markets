from pathlib import Path


def test_mt5_position_manager_is_demo_only_and_ownership_guarded():
    src = Path('app/services/mt5_position_manager.py').read_text(encoding='utf-8')
    assert "BrokerProfile.environment == 'DEMO'" in src
    assert "'MT5_DEMO_ONLY'" in src
    assert "startswith('ATLAS')" in src
    assert "close_demo_position(ticket)" in src
    assert "'EXIT_EXECUTED'" in src
    assert "'STRONG_OPPOSITE_SIGNAL'" in src


def test_mt5_position_manager_respects_global_safety_state():
    src = Path('app/services/mt5_position_manager.py').read_text(encoding='utf-8')
    assert "if not state.enabled" in src
    assert "if state.killed" in src
    assert "if not state.auto_execute_paper" in src


def test_mt5_position_manager_runs_in_app_lifespan():
    src = Path('app/main.py').read_text(encoding='utf-8')
    assert 'from app.services.mt5_position_manager import mt5_position_manager_loop' in src
    assert 'asyncio.create_task(mt5_position_manager_loop(stop))' in src
