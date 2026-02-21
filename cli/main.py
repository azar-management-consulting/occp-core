"""CLI entry point for the ``occp`` command.

Uses only stdlib (argparse) – no third-party deps for the core CLI.

Usage::

    occp start          – Start the OCCP platform (dashboard + orchestrator)
    occp run <workflow>  – Execute a workflow file
    occp status          – Show platform and agent status
    occp export          – Export audit logs
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="occp",
        description="OpenCloud Control Plane – Agent Control Plane CLI",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"occp {_get_version()}",
    )

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # start
    sp_start = sub.add_parser("start", help="Start the OCCP platform")
    sp_start.add_argument(
        "--port",
        type=int,
        default=3000,
        help="Dashboard port (default: 3000)",
    )
    sp_start.add_argument(
        "--host",
        default="0.0.0.0",
        help="Bind address (default: 0.0.0.0)",
    )

    # run
    sp_run = sub.add_parser("run", help="Execute a workflow")
    sp_run.add_argument("workflow", help="Path to workflow JSON file")
    sp_run.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate workflow without executing",
    )

    # status
    sub.add_parser("status", help="Show platform status")

    # export
    sp_export = sub.add_parser("export", help="Export audit logs")
    sp_export.add_argument(
        "--format",
        choices=["json", "csv"],
        default="json",
        help="Export format (default: json)",
    )
    sp_export.add_argument(
        "--output",
        "-o",
        default="-",
        help="Output file (default: stdout)",
    )

    return parser


def cmd_start(args: argparse.Namespace) -> int:
    """Start the OCCP platform."""
    print(f"Starting OCCP on {args.host}:{args.port} ...")
    print("Dashboard: http://localhost:{}/".format(args.port))
    print("Press Ctrl+C to stop.")
    # Placeholder – real implementation will launch uvicorn/node
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Execute a workflow file through the VAP pipeline."""
    wf_path = Path(args.workflow)
    if not wf_path.exists():
        print(f"Error: workflow file not found: {wf_path}", file=sys.stderr)
        return 1

    try:
        workflow = json.loads(wf_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in {wf_path}: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"Workflow '{workflow.get('name', 'unnamed')}' validated OK (dry run)")
        return 0

    print(f"Executing workflow '{workflow.get('name', 'unnamed')}' ...")
    print(f"  Tasks: {len(workflow.get('tasks', []))}")
    # Placeholder – real implementation will invoke Pipeline
    print("Workflow completed.")
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    """Show platform status."""
    status = {
        "platform": "OCCP",
        "version": _get_version(),
        "status": "running",
        "agents": [],
        "pipelines_active": 0,
    }
    print(json.dumps(status, indent=2))
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Export audit logs."""
    # Placeholder – real implementation reads from audit store
    entries: list[dict] = []
    output = json.dumps(entries, indent=2)

    if args.output == "-":
        print(output)
    else:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Exported {len(entries)} entries to {args.output}")
    return 0


COMMANDS = {
    "start": cmd_start,
    "run": cmd_run,
    "status": cmd_status,
    "export": cmd_export,
}


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    handler = COMMANDS.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


def _get_version() -> str:
    try:
        from cli import __version__

        return __version__
    except ImportError:
        return "0.1.0"


if __name__ == "__main__":
    sys.exit(main())
