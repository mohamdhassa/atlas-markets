from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "ops" / "ibkr-ibc" / "compose.yml"
ENV_EXAMPLE = ROOT / "ops" / "ibkr-ibc" / ".env.example"
WATCHDOG = ROOT / "ops" / "ibkr_bridge_watchdog.sh"
WATCHDOG_SERVICE = ROOT / "ops" / "systemd" / "atlas-ibkr-bridge-watchdog.service"


def _service():
    data = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    return data["services"]["ib-gateway"]


def _compose():
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def test_ibc_gateway_is_pinned_paper_and_localhost_only():
    service = _service()
    assert service["image"] == "ghcr.io/gnzsnz/ib-gateway:10.50.1e"
    assert service["environment"]["TRADING_MODE"] == "paper"
    assert service["environment"]["ALLOW_BLIND_TRADING"] == "no"
    assert all(str(port).startswith("127.0.0.1:") for port in service["ports"])


def test_ibc_passwords_are_file_secrets_not_plaintext_environment():
    service = _service()
    environment = service["environment"]
    assert "TWS_PASSWORD" not in environment
    assert environment["TWS_PASSWORD_FILE"] == "/run/secrets/tws_password"
    assert environment["VNC_SERVER_PASSWORD_FILE"] == "/run/secrets/vnc_password"
    example = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "TWS_PASSWORD=" not in example
    assert "VNC_SERVER_PASSWORD=" not in example


def test_ibc_stages_on_nonproduction_ports():
    example = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "IBKR_PAPER_HOST_PORT=14002" in example
    assert "IBKR_VNC_HOST_PORT=15902" in example


def test_ibc_initializes_persistent_settings_permissions_before_gateway():
    services = _compose()["services"]
    init = services["settings-init"]
    gateway = services["ib-gateway"]
    assert init["user"] == "0:0"
    assert "chown -R 1000:1000" in init["command"][0]
    assert gateway["depends_on"]["settings-init"]["condition"] == "service_completed_successfully"


def test_watchdog_uses_gateway_container_health_not_proxy_port_alone():
    script = WATCHDOG.read_text(encoding="utf-8")
    assert "IBKR_GATEWAY_CONTAINER" in script
    assert "gateway_health" in script
    assert '== "healthy"' in script
    assert "IBKR_GATEWAY_RECOVERY" in script
    assert "IBKR_GATEWAY_RECOVERED" in script
    assert "IBKR_AUTH_REQUIRED" in script
    assert script.index("if ! gateway_ready") < script.index('health="$(curl')


def test_watchdog_gateway_recovery_has_authentication_cooldown():
    script = WATCHDOG.read_text(encoding="utf-8")
    assert "IBKR_GATEWAY_RECOVERY_COOLDOWN_SECONDS" in script
    assert "IBKR_GATEWAY_RECOVERY_STAMP" in script
    assert "IBKR_GATEWAY_RECOVERY_COOLDOWN" in script


def test_watchdog_service_no_longer_depends_on_masked_legacy_gateway():
    service = WATCHDOG_SERVICE.read_text(encoding="utf-8")
    assert "atlas-ibgateway.service" not in service
    assert "docker.service" in service
