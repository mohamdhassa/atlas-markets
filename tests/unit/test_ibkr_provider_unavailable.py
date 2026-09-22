import httpx

from app.services.autotrade_readiness import _ibkr_provider_unavailable


def _status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "http://ibkr-bridge/health")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(
        f"IBKR bridge returned {status_code}",
        request=request,
        response=response,
    )


def test_ibkr_gateway_http_failures_are_provider_unavailable():
    assert _ibkr_provider_unavailable(_status_error(502)) is True
    assert _ibkr_provider_unavailable(_status_error(503)) is True
    assert _ibkr_provider_unavailable(_status_error(504)) is True


def test_ibkr_connection_failure_is_provider_unavailable():
    request = httpx.Request("GET", "http://ibkr-bridge/health")
    exc = httpx.ConnectError("connection refused", request=request)

    assert _ibkr_provider_unavailable(exc) is True


def test_ibkr_timeout_is_provider_unavailable():
    request = httpx.Request("GET", "http://ibkr-bridge/health")
    exc = httpx.ReadTimeout("timed out", request=request)

    assert _ibkr_provider_unavailable(exc) is True


def test_non_availability_http_errors_are_not_provider_unavailable():
    assert _ibkr_provider_unavailable(_status_error(400)) is False
    assert _ibkr_provider_unavailable(_status_error(401)) is False


def test_application_errors_are_not_provider_unavailable():
    assert _ibkr_provider_unavailable(RuntimeError("NO_DIRECTION")) is False
