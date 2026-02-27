"""MCP (Model Context Protocol) connector management endpoints.

Supply-chain gated: every install runs through PackageAllowlist before approval.
All operations are audit-trailed via PolicyEngine.audit().
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user_payload
from api.rbac import PermissionChecker
from api.deps import AppState, get_state
from api.models import (
    MCPCatalogResponse,
    MCPConnectorInfo,
    MCPInstallRequest,
    MCPInstallResponse,
)
from security.supply_chain import SupplyChainScanner

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mcp"])

# Singleton supply-chain scanner
_scanner = SupplyChainScanner()

# Load MCP server catalog from JSON
_CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "mcp-servers.json"
_CATALOG: list[dict] = []


def _load_catalog() -> list[dict]:
    global _CATALOG
    if _CATALOG:
        return _CATALOG
    if _CATALOG_PATH.exists():
        with open(_CATALOG_PATH) as f:
            _CATALOG = json.load(f)
    else:
        # Built-in defaults when no catalog file exists
        _CATALOG = [
            {
                "id": "filesystem",
                "name": "Filesystem",
                "description": "Read, write, and manage files on your local system.",
                "package": "@anthropic/mcp-filesystem",
                "category": "core",
                "config_template": {"command": "npx", "args": ["-y", "@anthropic/mcp-filesystem"]},
            },
            {
                "id": "github",
                "name": "GitHub",
                "description": "Manage repositories, issues, and pull requests.",
                "package": "@anthropic/mcp-github",
                "category": "integration",
                "config_template": {"command": "npx", "args": ["-y", "@anthropic/mcp-github"]},
            },
            {
                "id": "postgres",
                "name": "PostgreSQL",
                "description": "Query and manage PostgreSQL databases.",
                "package": "@anthropic/mcp-postgres",
                "category": "database",
                "config_template": {"command": "npx", "args": ["-y", "@anthropic/mcp-postgres"]},
            },
            {
                "id": "sqlite",
                "name": "SQLite",
                "description": "Query and manage SQLite databases.",
                "package": "@anthropic/mcp-sqlite",
                "category": "database",
                "config_template": {"command": "npx", "args": ["-y", "@anthropic/mcp-sqlite"]},
            },
            {
                "id": "memory",
                "name": "Memory",
                "description": "Persistent knowledge graph for context storage.",
                "package": "@anthropic/mcp-memory",
                "category": "core",
                "config_template": {"command": "npx", "args": ["-y", "@anthropic/mcp-memory"]},
            },
        ]
    return _CATALOG


@router.get(
    "/mcp/catalog",
    response_model=MCPCatalogResponse,
    dependencies=[Depends(PermissionChecker("mcp", "read"))],
)
async def list_mcp_catalog() -> MCPCatalogResponse:
    """Return the catalog of available MCP connectors."""
    catalog = _load_catalog()
    connectors = [
        MCPConnectorInfo(
            id=c["id"],
            name=c["name"],
            description=c["description"],
            package=c.get("package", ""),
            category=c.get("category", "integration"),
        )
        for c in catalog
    ]
    return MCPCatalogResponse(connectors=connectors, total=len(connectors))


@router.post(
    "/mcp/install",
    response_model=MCPInstallResponse,
)
async def install_mcp_connector(
    body: MCPInstallRequest,
    user: dict[str, Any] = Depends(PermissionChecker("mcp", "install")),
    state: AppState = Depends(get_state),
) -> MCPInstallResponse:
    """Install an MCP connector — supply-chain gated and audit-trailed."""
    catalog = _load_catalog()
    connector = next((c for c in catalog if c["id"] == body.connector_id), None)
    if connector is None:
        raise HTTPException(status_code=404, detail=f"Connector '{body.connector_id}' not found in catalog")

    # ── Supply-chain gate ────────────────────────────────────────
    package_name = connector.get("package", "")
    if package_name:
        scan_result = _scanner.scan_mcp_install(package_name)
        if not scan_result.allowed:
            # Audit the blocked install
            await state.policy_engine.audit(
                actor=user.get("sub", "unknown"),
                action="mcp_install_blocked",
                detail={
                    "connector_id": body.connector_id,
                    "package": package_name,
                    "reason": scan_result.reason,
                    "risk_level": scan_result.risk_level,
                },
            )
            raise HTTPException(
                status_code=403,
                detail=f"Supply-chain check failed: {scan_result.reason}",
            )

    # ── Build mcp.json config entry ──────────────────────────────
    config_template = connector.get("config_template", {})
    config_entry = {
        connector["id"]: {
            "command": config_template.get("command", "npx"),
            "args": config_template.get("args", []),
        }
    }

    # If env vars needed, add them
    if body.env_vars:
        config_entry[connector["id"]]["env"] = body.env_vars

    mcp_json = {"mcpServers": config_entry}

    # ── Audit trail ──────────────────────────────────────────────
    await state.policy_engine.audit(
        actor=user.get("sub", "unknown"),
        action="mcp_install",
        detail={
            "connector_id": body.connector_id,
            "connector_name": connector["name"],
            "package": package_name,
            "risk_level": scan_result.risk_level if package_name else "n/a",
        },
    )

    return MCPInstallResponse(
        connector_id=body.connector_id,
        connector_name=connector["name"],
        mcp_json=mcp_json,
        instructions="Add the following to your MCP configuration file (mcp.json or claude_desktop_config.json).",
    )
