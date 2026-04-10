"""MCP Config Executor — generates audited MCP configuration.

This adapter produces MCP server configurations without requiring
an LLM token. It works through the Verified Autonomy Pipeline as a deterministic
executor for MCP installation tasks.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class MCPConfigExecutor:
    """Deterministic executor that produces MCP configurations.

    No LLM required — reads from the MCP server catalog and produces
    validated mcp.json snippets for the requested connectors.
    """

    def __init__(self, catalog: list[dict] | None = None) -> None:
        self._catalog = catalog or []

    async def execute(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Execute an MCP install plan.

        Args:
            plan: Must contain 'connector_ids' (list of str) and
                  optional 'env_vars' (dict per connector).

        Returns:
            Result dict with 'mcp_json' config and 'audit' metadata.
        """
        connector_ids = plan.get("connector_ids", [])
        env_vars = plan.get("env_vars", {})

        mcp_servers: dict[str, Any] = {}
        installed: list[str] = []
        errors: list[str] = []

        for cid in connector_ids:
            connector = next((c for c in self._catalog if c["id"] == cid), None)
            if connector is None:
                errors.append(f"Unknown connector: {cid}")
                continue

            template = connector.get("config_template", {})
            entry: dict[str, Any] = {
                "command": template.get("command", "npx"),
                "args": list(template.get("args", [])),
            }

            # Merge env vars if provided for this connector
            if cid in env_vars and isinstance(env_vars[cid], dict):
                entry["env"] = env_vars[cid]

            mcp_servers[cid] = entry
            installed.append(cid)

        result = {
            "mcp_json": {"mcpServers": mcp_servers},
            "installed": installed,
            "errors": errors,
            "audit": {
                "executor": "MCPConfigExecutor",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "connector_count": len(installed),
            },
        }

        logger.info(
            "MCPConfigExecutor: installed %d connectors, %d errors",
            len(installed),
            len(errors),
        )

        return result
