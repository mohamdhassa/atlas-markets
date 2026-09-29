from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "ops" / "ibkr-ibc" / "compose.yml"
ENV_EXAMPLE = ROOT / "ops" / "ibkr-ibc" / ".env.example"


def _service():
    data = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    return data["services"]["ib-gateway"]


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
