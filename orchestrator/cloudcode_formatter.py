"""CloudCode output formatting — structured Brain report for CloudCode output.

Protocol requirement P2: Formatted report with execution timeline and verification.
"""

from __future__ import annotations

from typing import Any


def format_cloudcode_report(task_id: str, result: dict, events: list) -> str:
    """Format a full structured report for CloudCode output."""
    lines = [
        f"=== OCCP BRAIN REPORT ===",
        f"Task: {task_id}",
        f"Status: {result.get('status', 'unknown')}",
        f"",
        f"-- Execution Timeline --",
    ]
    for event in events:
        lines.append(f"  [{event['timestamp'][:19]}] {event['event_type']}: {event['data']}")

    lines.extend([
        f"",
        f"-- Result --",
        f"  {result.get('output', 'No output')}",
        f"",
        f"-- Verification --",
        f"  Gate: {'PASS' if result.get('gate_approved') else 'FAIL'}",
        f"  Validation: {'PASS' if result.get('validation_passed') else 'N/A'}",
        f"",
        f"=== END REPORT ===",
    ])
    return "\n".join(lines)
