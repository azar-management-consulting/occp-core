"""OCCP safe evaluation lane (L6 foundation).

This package provides the infrastructure for testing architectural changes
in an isolated, non-destructive way before they reach production.

Current scope (v0.10.0):
- Feature flag runtime store (in-memory + DB-backed)
- Replay harness skeleton (run historical workflows against a candidate)
- Canary primitives (traffic split + metric compare)

These modules are intentionally minimal. They establish the import surface
and data contracts that future L6 phases will extend.
"""

from evaluation.feature_flags import FeatureFlag, FeatureFlagStore, get_flag_store

__all__ = ["FeatureFlag", "FeatureFlagStore", "get_flag_store"]
