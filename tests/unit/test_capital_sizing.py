from app.services.capital_sizing import capital_sizing_inputs
from pathlib import Path


def test_paper_account_can_model_one_hundred_dollars():
    assert capital_sizing_inputs(
        broker_equity=1_003_221.49,
        broker_available=1_000_227.28,
        environment="PAPER",
        simulation_capital_override_usd=100,
    ) == (100.0, 100.0, "SIMULATION_OVERRIDE")


def test_simulation_override_can_be_cleared_and_scale_with_equity():
    assert capital_sizing_inputs(
        broker_equity=1_000_000,
        broker_available=900_000,
        environment="PAPER",
        simulation_capital_override_usd=None,
    ) == (1_000_000.0, 900_000.0, "BROKER_EQUITY")


def test_live_account_never_uses_simulation_override():
    assert capital_sizing_inputs(
        broker_equity=1_000_000,
        broker_available=800_000,
        environment="LIVE",
        simulation_capital_override_usd=100,
    ) == (1_000_000.0, 800_000.0, "BROKER_EQUITY")


def test_available_cash_cannot_exceed_equity():
    assert capital_sizing_inputs(
        broker_equity=75,
        broker_available=90,
        environment="TESTNET",
        simulation_capital_override_usd=100,
    ) == (75.0, 75.0, "SIMULATION_OVERRIDE")


def test_account_level_override_has_migration_api_and_schema_support():
    migration = Path("migrations/versions/20261001_0022_simulation_capital_override.py").read_text()
    routes = Path("app/api/routes_accounts.py").read_text()
    schema = Path("app/schemas/broker_profile.py").read_text()

    assert 'revision = "20261001_0022"' in migration
    assert 'down_revision = "20260930_0021"' in migration
    assert '"simulation_capital_override_usd"' in migration
    assert "@router.put('/{profile_id}/simulation-capital'" in routes
    assert "p.environment not in SIMULATION_ENVIRONMENTS" in routes
    assert "simulation_capital_override_usd" in schema
