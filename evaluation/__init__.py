"""OCCP safe evaluation lane (L6 foundation, v0.10.0 completion).

This package provides the infrastructure for testing architectural
changes in an isolated, non-destructive way before they reach
production.

v0.10.0 scope:
- Feature flag runtime store (in-memory, DB-backed in v0.11.0)
- Replay harness with real in-process comparison
- Canary engine: baseline-vs-candidate metric verdict
- Self-modifier: runtime governance path validator
- Proposal generator: reads issue_registry + anomalies → RFC candidates
"""

from evaluation.canary_engine import (
    CanaryCriteria,
    CanaryEngine,
    CanaryVerdict,
    get_canary_engine,
)
from evaluation.feature_flags import (
    FeatureFlag,
    FeatureFlagStore,
    get_flag_store,
)
from evaluation.proposal_generator import (
    ProposalCandidate,
    ProposalGenerator,
    get_proposal_generator,
)
from evaluation.replay_harness import (
    ReplayHarness,
    ReplayResult,
    ReplayScenario,
    get_replay_harness,
)
from evaluation.self_modifier import (
    ModificationVerdict,
    SelfModifier,
    get_self_modifier,
)

__all__ = [
    # Feature flags
    "FeatureFlag",
    "FeatureFlagStore",
    "get_flag_store",
    # Replay harness
    "ReplayHarness",
    "ReplayScenario",
    "ReplayResult",
    "get_replay_harness",
    # Canary engine
    "CanaryEngine",
    "CanaryCriteria",
    "CanaryVerdict",
    "get_canary_engine",
    # Self-modifier
    "SelfModifier",
    "ModificationVerdict",
    "get_self_modifier",
    # Proposal generator
    "ProposalGenerator",
    "ProposalCandidate",
    "get_proposal_generator",
]
