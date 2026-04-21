"""Smoke-test pytest plugin.

Registers the ``smoke`` marker and gates all smoke tests behind the
``--smoke`` CLI flag so that regular ``pytest`` runs remain unaffected.

Environment variables
---------------------
OCCP_SMOKE_TARGET_BASE
    Override the base URL used by smoke tests (e.g. for staging).
    Default: https://api.occp.ai
"""

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--smoke",
        action="store_true",
        default=False,
        help="Run production smoke tests against live endpoints.",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "smoke: production smoke tests — run with --smoke flag only.",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Skip every ``smoke``-marked test unless --smoke was passed."""
    if config.getoption("--smoke"):
        return  # user opted in — run everything collected

    skip_smoke = pytest.mark.skip(reason="Pass --smoke to run production smoke tests.")
    for item in items:
        if item.get_closest_marker("smoke"):
            item.add_marker(skip_smoke)
