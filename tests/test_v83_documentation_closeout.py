from pathlib import Path


DOCS = Path("docs")


def test_v83_canonical_documents_exist():
    required = {
        "DOCUMENTATION_INDEX.md",
        "API_REFERENCE.md",
        "USER_ADMIN_GUIDE.md",
        "OPERATIONS_RUNBOOK.md",
        "BACKUP_AND_RECOVERY.md",
        "SECURITY_OPERATIONS.md",
        "RELEASE_V83.md",
    }
    assert required <= {path.name for path in DOCS.glob("*.md")}


def test_erd_tracks_current_shadow_schema_and_migration():
    text = (DOCS / "ERD.md").read_text(encoding="utf-8")
    assert "20260925_0019" in text
    assert "SHADOW_OBSERVATIONS" in text
    assert "SHADOW_SCAN_EVENTS" in text
    assert "max_favorable_excursion_pct" in text
    assert "round_trip_cost_bps" in text


def test_operations_uses_production_compose_and_health_endpoint():
    text = (DOCS / "OPERATIONS_RUNBOOK.md").read_text(encoding="utf-8")
    assert "docker-compose.oracle.prod.yml" in text
    assert "http://127.0.0.1:8100/health" in text
    assert "run_shadow_scan" in text


def test_documentation_preserves_execution_safety_boundary():
    combined = "\n".join(path.read_text(encoding="utf-8") for path in (
        DOCS / "API_REFERENCE.md",
        DOCS / "USER_ADMIN_GUIDE.md",
        DOCS / "SECURITY_OPERATIONS.md",
        DOCS / "RELEASE_V83.md",
    ))
    assert "Shadow eligibility cannot enable execution" in combined
    assert "No live-money authority" in combined


def test_readme_indexes_v83_documentation():
    text = Path("README.md").read_text(encoding="utf-8")
    assert "v83 documentation" in text
    assert "docs/DOCUMENTATION_INDEX.md" in text
    assert "docs/RELEASE_V83.md" in text
