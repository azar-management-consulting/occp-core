"""Production smoke tests for OCCP live surfaces.

Marked ``@pytest.mark.smoke`` so they are **excluded** from the regular
regression run.  Execute with::

    pytest tests/smoke --smoke -v

Offline / local-dev bypass
--------------------------
Set ``OCCP_SMOKE_MODE=offline`` to activate ``respx`` mocks so the suite
can be imported and run without touching real prod.

Env overrides
-------------
OCCP_SMOKE_TARGET_BASE   – base URL for the API (default: https://api.occp.ai)
OCCP_SMOKE_DASH_BASE     – base URL for the dashboard (default: https://dash.occp.ai)
OCCP_SMOKE_LANDING_BASE  – base URL for the landing page (default: https://occp.ai)
"""

from __future__ import annotations

import os
import re
import time
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Constants (resolved lazily — never executed during collection)
# ---------------------------------------------------------------------------
_DEFAULT_API_BASE = "https://api.occp.ai"
_DEFAULT_DASH_BASE = "https://dash.occp.ai"
_DEFAULT_LANDING_BASE = "https://occp.ai"

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+")

_OFFLINE = os.environ.get("OCCP_SMOKE_MODE", "").lower() == "offline"


# ---------------------------------------------------------------------------
# Helpers (lazy — only called inside test bodies)
# ---------------------------------------------------------------------------

def _api_base() -> str:
    return os.environ.get("OCCP_SMOKE_TARGET_BASE", _DEFAULT_API_BASE).rstrip("/")


def _dash_base() -> str:
    return os.environ.get("OCCP_SMOKE_DASH_BASE", _DEFAULT_DASH_BASE).rstrip("/")


def _landing_base() -> str:
    return os.environ.get("OCCP_SMOKE_LANDING_BASE", _DEFAULT_LANDING_BASE).rstrip("/")


def _client():  # type: ignore[return]
    """Return a configured httpx.Client (or mock transport in offline mode)."""
    import httpx  # noqa: PLC0415

    timeout = httpx.Timeout(10.0)

    if _OFFLINE:
        import respx  # noqa: PLC0415

        mock = respx.MockRouter(assert_all_called=False)

        api_base = _api_base()
        dash_base = _dash_base()
        landing_base = _landing_base()

        mock.get(f"{api_base}/api/v1/status").mock(
            return_value=httpx.Response(
                200,
                json={
                    "platform": "OCCP",
                    "version": "0.10.1",
                    "status": "running",
                    "environment": "production",
                    "tasks_count": 0,
                    "audit_entries": 0,
                },
                headers={
                    "x-content-type-options": "nosniff",
                    "strict-transport-security": "max-age=31536000; includeSubDomains",
                    "content-type": "application/json",
                },
            )
        )
        mock.get(f"{api_base}/docs").mock(
            return_value=httpx.Response(
                200,
                text="<html><title>Swagger UI</title></html>",
            )
        )
        mock.get(f"{dash_base}/").mock(
            return_value=httpx.Response(
                200,
                text="<html>OCCP Dashboard <button>Login</button></html>",
                headers={
                    "content-security-policy": (
                        "default-src 'self'; connect-src 'self' https://api.occp.ai"
                    ),
                },
            )
        )
        mock.get(f"{landing_base}/").mock(
            return_value=httpx.Response(200, text="<html>OCCP landing</html>")
        )

        transport = mock.handler  # respx ASGI/sync transport shim
        return httpx.Client(transport=transport, timeout=timeout)

    return httpx.Client(timeout=timeout, follow_redirects=True)


# ---------------------------------------------------------------------------
# Smoke tests
# ---------------------------------------------------------------------------

@pytest.mark.smoke
def test_status_endpoint_healthy() -> None:
    """GET /api/v1/status returns 200 with valid OCCP identity payload."""
    with _client() as client:
        resp = client.get(f"{_api_base()}/api/v1/status")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    body = resp.json()
    assert body.get("platform") == "OCCP", f"platform mismatch: {body.get('platform')!r}"
    assert body.get("status") == "running", f"status not 'running': {body.get('status')!r}"
    assert body.get("environment") == "production", (
        f"environment not 'production': {body.get('environment')!r}"
    )
    version = body.get("version", "")
    assert _VERSION_RE.match(str(version)), f"version does not match semver: {version!r}"

    # Confirm schema keys present (values may be 0)
    for key in ("tasks_count", "audit_entries"):
        assert key in body, f"Missing key in status payload: {key!r}"


@pytest.mark.smoke
def test_swagger_live() -> None:
    """GET /docs returns 200 and renders Swagger / OpenAPI UI."""
    with _client() as client:
        resp = client.get(f"{_api_base()}/docs")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    body = resp.text
    assert "Swagger UI" in body or "OpenAPI" in body, (
        "Swagger UI marker not found in /docs response body"
    )


@pytest.mark.smoke
def test_dash_live() -> None:
    """GET https://dash.occp.ai/ returns 200 and contains OCCP content."""
    with _client() as client:
        resp = client.get(f"{_dash_base()}/")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    body = resp.text.lower()
    # Accept any of: product name mention or a login / sign-in affordance.
    assert "occp" in body or "login" in body or "sign in" in body or "sign-in" in body, (
        "Dashboard body contains neither 'occp' nor a login prompt"
    )


@pytest.mark.smoke
def test_landing_live() -> None:
    """GET https://occp.ai/ returns 200."""
    with _client() as client:
        resp = client.get(f"{_landing_base()}/")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"


@pytest.mark.smoke
def test_api_response_under_1s() -> None:
    """SLO: /api/v1/status must respond in < 1 s (wall-clock)."""
    with _client() as client:
        t0 = time.perf_counter()
        resp = client.get(f"{_api_base()}/api/v1/status")
        elapsed = time.perf_counter() - t0

    assert resp.status_code == 200, f"Status check failed: {resp.status_code}"
    assert elapsed < 1.0, (
        f"API SLO breached: response took {elapsed:.3f}s (threshold: 1.000s)"
    )


@pytest.mark.smoke
def test_api_security_headers() -> None:
    """GET /api/v1/status must include mandatory security response headers."""
    with _client() as client:
        resp = client.get(f"{_api_base()}/api/v1/status")

    assert resp.status_code == 200

    headers = {k.lower(): v for k, v in resp.headers.items()}

    # MIME-type sniffing protection — tolerate stacked layers (FastAPI +
    # reverse proxy): some deployments set the header twice, which httpx
    # joins as "nosniff, nosniff". Presence of the value is what matters.
    xcto = headers.get("x-content-type-options", "")
    assert "nosniff" in xcto.lower(), (
        f"x-content-type-options must contain 'nosniff', got: {xcto!r}"
    )

    # HSTS (presence is sufficient — directives vary by CDN config)
    assert "strict-transport-security" in headers, (
        "strict-transport-security header missing from API response"
    )


@pytest.mark.smoke
def test_dash_csp_header() -> None:
    """GET https://dash.occp.ai/ must have a CSP that allows api.occp.ai as connect-src."""
    with _client() as client:
        resp = client.get(f"{_dash_base()}/")

    assert resp.status_code == 200

    headers = {k.lower(): v for k, v in resp.headers.items()}

    csp = headers.get("content-security-policy", "")
    assert csp, "Content-Security-Policy header is absent from dashboard response"

    # Extract the connect-src directive value (case-insensitive directive name)
    match = re.search(r"connect-src\s+([^;]+)", csp, re.IGNORECASE)
    assert match, f"connect-src directive missing from CSP: {csp!r}"

    connect_src_value = match.group(1)
    assert "api.occp.ai" in connect_src_value, (
        f"api.occp.ai not in connect-src: {connect_src_value!r}"
    )
