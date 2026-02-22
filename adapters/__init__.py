"""OCCP Demo Adapters – reference implementations for the VAP pipeline.

These adapters implement the Protocol interfaces defined in
``orchestrator.pipeline`` (Planner, Executor, Validator, Shipper) and
provide a working demo pipeline out of the box.
"""

from adapters.echo_planner import EchoPlanner
from adapters.policy_gate import PolicyGate
from adapters.mock_executor import MockExecutor
from adapters.basic_validator import BasicValidator
from adapters.log_shipper import LogShipper

__all__ = [
    "EchoPlanner",
    "PolicyGate",
    "MockExecutor",
    "BasicValidator",
    "LogShipper",
]
