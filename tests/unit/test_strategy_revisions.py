from pathlib import Path


def test_strategy_revision_migration_extends_canonical_head():
    migration = Path("migrations/versions/20260930_0020_strategy_revisions.py").read_text()

    assert 'revision = "20260930_0020"' in migration
    assert 'down_revision = "20260925_0019"' in migration
    assert '"symbol_strategy_revisions"' in migration
    assert '"snapshot"' in migration
    assert '"restored_from_revision"' in migration


def test_strategy_revision_model_is_immutable_audit_data():
    model = Path("app/db/models/strategy_revision.py").read_text()

    assert 'class SymbolStrategyRevision' in model
    assert '"strategy_id"' in model
    assert '"revision_number"' in model
    assert 'snapshot: Mapped[dict]' in model
    assert 'actor_user_id' in model


def test_strategy_routes_record_changes_and_offer_history_and_rollback():
    routes = Path("app/api/routes_symbol_strategies.py").read_text()

    assert "_record_revision(db,row,user,'CREATE')" in routes
    assert "_record_revision(db,row,user,'UPDATE')" in routes
    assert "_record_revision(db,row,user,'DELETE')" in routes
    assert "@router.get('/{row_id}/revisions')" in routes
    assert "@router.post('/{row_id}/rollback/{revision_number}')" in routes
    assert "'ROLLBACK'" in routes
    assert "stored revision exceeds current Admin safety limit" in routes


def test_strategy_rollback_never_restores_account_or_symbol_identity():
    routes = Path("app/api/routes_symbol_strategies.py").read_text()

    editable = routes.split("EDITABLE_FIELDS=", 1)[1].split("\n", 1)[0]
    assert "profile_id" not in editable
    assert "user_id" not in editable
    assert "market" not in editable
    assert "symbol" not in editable


def test_strategy_workspace_exposes_history_and_rollback_controls():
    workspace = Path("app/static/management-workspaces.js").read_text()
    index = Path("app/static/index.html").read_text()

    assert "strategy-history:" in workspace
    assert "revision history" in workspace
    assert "strategy-rollback:" in workspace
    assert "Manual rollback from Strategy workspace" in workspace
    assert "management-workspaces.js?v=82.0" in index
