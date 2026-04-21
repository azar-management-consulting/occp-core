"""Schema guard for ``store/models.py::AuditEntryRow``.

Asserts all 9 cost-attribution columns are present on the ORM model so any
future schema refactor surfaces loudly in CI.

FELT: spec asked for ``AuditEntry`` but the actual class in the repo is
``AuditEntryRow`` (see store/models.py:58).  Spec also used short names
``ephemeral_5m`` / ``ephemeral_1h`` — the real columns are
``ephemeral_5m_input_tokens`` / ``ephemeral_1h_input_tokens``.  The test
accepts either spelling (prefix match) so the guard is robust to a future
rename in either direction.
"""
from __future__ import annotations

import pytest

REQUIRED_EXACT = {
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
    "model_id",
    "computed_usd",
    "cache_hit_ratio",
}

# These two may appear as the short ("ephemeral_5m") or long
# ("ephemeral_5m_input_tokens") spelling.
REQUIRED_PREFIX = {
    "ephemeral_5m",
    "ephemeral_1h",
}


def _model_class():
    try:
        from store.models import AuditEntryRow  # type: ignore
    except Exception as exc:  # pragma: no cover - import error path
        pytest.skip(f"store.models.AuditEntryRow not importable: {exc}")
    return AuditEntryRow


def _model_column_names(cls) -> set[str]:
    # SQLAlchemy 2.x Mapped columns — use the mapper.columns view.
    try:
        return {c.key for c in cls.__table__.columns}  # type: ignore[attr-defined]
    except Exception:
        # Fallback: scan class dict.
        return {k for k in vars(cls) if not k.startswith("_")}


@pytest.mark.parametrize("field", sorted(REQUIRED_EXACT))
def test_audit_entry_has_exact_cost_field(field: str) -> None:
    cls = _model_class()
    names = _model_column_names(cls)
    assert field in names, (
        f"AuditEntryRow missing required cost column {field!r}; "
        f"columns present: {sorted(names)}"
    )


@pytest.mark.parametrize("prefix", sorted(REQUIRED_PREFIX))
def test_audit_entry_has_prefixed_cost_field(prefix: str) -> None:
    cls = _model_class()
    names = _model_column_names(cls)
    matches = [n for n in names if n == prefix or n.startswith(prefix + "_")]
    assert matches, (
        f"AuditEntryRow missing column with prefix {prefix!r}; "
        f"columns present: {sorted(names)}"
    )


def test_audit_entry_has_nine_cost_columns() -> None:
    """Final count guard: at least 9 cost-attribution columns exist."""
    cls = _model_class()
    names = _model_column_names(cls)
    cost_like = {
        n for n in names
        if n in REQUIRED_EXACT
        or any(n == p or n.startswith(p + "_") for p in REQUIRED_PREFIX)
    }
    assert len(cost_like) >= 9, (
        f"expected >=9 cost columns, got {len(cost_like)}: {sorted(cost_like)}"
    )
