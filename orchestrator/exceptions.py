"""Orchestrator exception hierarchy."""

from __future__ import annotations


class OccpError(Exception):
    """Base exception for all OCCP errors."""


class PipelineError(OccpError):
    """Raised when the Verified Autonomy Pipeline encounters an error."""


class GateRejectedError(PipelineError):
    """Raised when the Gate stage rejects a task due to policy violation."""

    def __init__(self, task_id: str, reason: str) -> None:
        self.task_id = task_id
        self.reason = reason
        super().__init__(f"Gate rejected task {task_id}: {reason}")


class ValidationError(PipelineError):
    """Raised when the Validate stage finds issues."""

    def __init__(self, task_id: str, failures: list[str]) -> None:
        self.task_id = task_id
        self.failures = failures
        super().__init__(
            f"Validation failed for task {task_id}: {'; '.join(failures)}"
        )


class ExecutionError(PipelineError):
    """Raised when the Execute stage fails."""

    def __init__(self, task_id: str, detail: str) -> None:
        self.task_id = task_id
        self.detail = detail
        super().__init__(f"Execution failed for task {task_id}: {detail}")


class SchedulerError(OccpError):
    """Raised for agent scheduling failures."""


class AgentNotFoundError(SchedulerError):
    """Raised when a requested agent adapter is not registered."""

    def __init__(self, agent_type: str) -> None:
        self.agent_type = agent_type
        super().__init__(f"No adapter registered for agent type: {agent_type}")


class TimeoutError(OccpError):  # noqa: A001
    """Raised when an operation exceeds its time budget."""
