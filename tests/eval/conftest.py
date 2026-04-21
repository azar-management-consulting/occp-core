"""pytest fixtures / hooks scoped to the eval suite."""
from __future__ import annotations


def pytest_addoption(parser) -> None:
    """Register ``--update-snapshot``.

    Used by:
        pytest tests/eval/test_prompt_snapshot.py --update-snapshot

    Guarded with try/except so a parent conftest that already registers the
    flag does not break collection.
    """
    try:
        parser.addoption(
            "--update-snapshot",
            action="store_true",
            default=False,
            dest="update_snapshot",
            help="Rewrite tests/eval/snapshots/*.sha256 from current files.",
        )
    except ValueError:
        # Option already registered by a parent plugin/conftest.
        pass
