"""OCCP Adapters – reference + production implementations for the VAP pipeline.

These adapters implement the Protocol interfaces defined in
``orchestrator.pipeline`` (Planner, Executor, Validator, Shipper) and
provide a working pipeline out of the box.

ClaudePlanner requires the optional ``anthropic`` package::

    pip install 'occp[llm]'
"""

from adapters.echo_planner import EchoPlanner
from adapters.policy_gate import PolicyGate
from adapters.mock_executor import MockExecutor
from adapters.basic_validator import BasicValidator
from adapters.log_shipper import LogShipper

__all__ = [
    "EchoPlanner",
    "ClaudePlanner",
    "PolicyGate",
    "MockExecutor",
    "BasicValidator",
    "LogShipper",
]


def __getattr__(name: str):
    """Lazy-load ClaudePlanner so 'anthropic' is only imported on demand."""
    if name == "ClaudePlanner":
        from adapters.claude_planner import ClaudePlanner
        return ClaudePlanner
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
