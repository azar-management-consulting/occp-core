"""OCCP safe evaluation lane (L6 foundation, v0.10.0 maximum state).

v0.10.0 scope:
- Feature flag runtime store (JSON-backed persistence)
- Replay harness with real in-process comparison
- Canary engine: baseline-vs-candidate metric verdict + history
- Self-modifier: runtime governance path validator
- Proposal generator: reads issue_registry + anomalies → RFC candidates
- Kill switch: hard-stop primitive with activation history
- Drift detector: architecture YAML vs code cross-check
"""

from evaluation.canary_engine import (
    CanaryCriteria,
    CanaryEngine,
    CanaryVerdict,
    get_canary_engine,
)
from evaluation.drift_detector import (
    DriftDetector,
    DriftEntry,
    DriftReport,
    get_drift_detector,
)
from evaluation.feature_flags import (
    FeatureFlag,
    FeatureFlagStore,
    get_flag_store,
)
from evaluation.kill_switch import (
    KillSwitch,
    KillSwitchActivation,
    KillSwitchActive,
    KillSwitchState,
    KillSwitchTrigger,
    get_kill_switch,
    require_kill_switch_inactive,
)
from evaluation.kill_switch_redis import (
    RedisKillSwitch,
    get_redis_kill_switch,
    kill_switch_backend,
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
    # Kill switch
    "KillSwitch",
    "KillSwitchActivation",
    "KillSwitchState",
    "KillSwitchTrigger",
    "KillSwitchActive",
    "get_kill_switch",
    "require_kill_switch_inactive",
    "RedisKillSwitch",
    "get_redis_kill_switch",
    "kill_switch_backend",
    # Drift detector
    "DriftDetector",
    "DriftEntry",
    "DriftReport",
    "get_drift_detector",
]
