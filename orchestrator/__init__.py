"""OCCP Orchestrator – Verified Autonomy Pipeline vezérlő.

A modul felel a Plan → Gate → Execute → Validate → Ship pipeline
koordinálásáért, az ügynökök ütemezéséért és a futási állapot kezeléséért.
"""

__version__ = "0.9.0"

from orchestrator.models import (
    Task,
    TaskStatus,
    PipelineResult,
    AgentConfig,
    RiskLevel,
)
from orchestrator.pipeline import Pipeline
from orchestrator.scheduler import Scheduler
from orchestrator.config_loader import ConfigLoader, AgentDefinition
from orchestrator.sessions import SessionManager, SessionTier, SessionState
from orchestrator.message_pipeline import MessagePipeline, InboundMessage, OutboundMessage
from orchestrator.project_manager import Project, ProjectManager
from orchestrator.task_router import TaskRouter, RouteDecision
from orchestrator.quality_gate import QualityGate, QualityCheck
from orchestrator.feedback_loop import FeedbackLoop, AgentFeedback
from orchestrator.brain_flow import BrainFlowEngine, BrainConversation, FlowPhase

__all__ = [
    "Task",
    "TaskStatus",
    "PipelineResult",
    "AgentConfig",
    "RiskLevel",
    "Pipeline",
    "Scheduler",
    "ConfigLoader",
    "AgentDefinition",
    "SessionManager",
    "SessionTier",
    "SessionState",
    "MessagePipeline",
    "InboundMessage",
    "OutboundMessage",
    "Project",
    "ProjectManager",
    "TaskRouter",
    "RouteDecision",
    "QualityGate",
    "QualityCheck",
    "FeedbackLoop",
    "AgentFeedback",
    "BrainFlowEngine",
    "BrainConversation",
    "FlowPhase",
]
