from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def test_v1_documentation_package_exists():
    required = {
        "DOCUMENTATION_INDEX.md",
        "ARCHITECTURE.md",
        "ERD.md",
        "ERP_OPERATING_MODEL.md",
        "API_REFERENCE.md",
        "USER_ADMIN_GUIDE.md",
        "OPERATIONS_RUNBOOK.md",
        "IBKR_CONTINUITY.md",
        "IBKR_IBC_RELIABILITY.md",
        "BACKUP_AND_RECOVERY.md",
        "SECURITY_OPERATIONS.md",
        "CURRENT_STATUS.md",
        "FINAL_HANDOVER.md",
        "ROADMAP.md",
        "RELEASE_V1_DOCUMENTATION.md",
        "DATABASE_OPERATIONS.md",
        "DEVELOPER_ONBOARDING.md",
    }
    assert required <= {path.name for path in DOCS.glob("*.md")}


def test_documentation_index_links_resolve():
    content = (DOCS / "DOCUMENTATION_INDEX.md").read_text(encoding="utf-8")
    links = re.findall(r"\[[^]]+\]\(([^)#]+\.md)\)", content)
    assert links
    assert not [link for link in links if not (DOCS / link).is_file()]


def test_canonical_baseline_is_documented():
    commit = "5ef08db6426876be6019541c45c0b3b3851f85eb"
    for name in ("CURRENT_STATUS.md", "FINAL_HANDOVER.md", "OPERATIONS_RUNBOOK.md"):
        content = (DOCS / name).read_text(encoding="utf-8")
        assert "v1.0.0" in content
        assert commit in content


def test_erd_covers_current_operational_entities():
    content = (DOCS / "ERD.md").read_text(encoding="utf-8").lower()
    entities = {
        "users",
        "broker_profiles",
        "symbol_strategies",
        "automation_scans",
        "automation_actions",
        "bybit_managed_inventory",
        "shadow_observations",
        "shadow_scan_events",
        "daily_account_reports",
    }
    assert not [entity for entity in entities if entity not in content]


def test_ibkr_continuity_records_verified_autorestart_fix():
    content = (DOCS / "IBKR_CONTINUITY.md").read_text(encoding="utf-8")
    assert "Daily auto-restart is enabled." in content
    assert "atlas-ibkr-bridge-watchdog.timer" in content
    assert "<ORACLE_PUBLIC_IP>" in content


def test_database_operations_identifies_canonical_database_safely():
    content = (DOCS / "DATABASE_OPERATIONS.md").read_text(encoding="utf-8")
    assert "atlas_markets" in content
    assert "20260925_0019" in content
    assert "built-in SSH tunnel" in content
    assert "POSTGRES_PASSWORD=" not in content


def test_human_and_agent_onboarding_exists():
    assert (ROOT / "CONTRIBUTING.md").is_file()
    agent_instructions = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "atlas_markets" in agent_instructions
    assert "Live Money" in agent_instructions
    assert "full suite" in agent_instructions
