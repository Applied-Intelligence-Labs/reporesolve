"""Supervisor workflow helpers."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from ..agent.schema import AgentDecision
from ..tools.base import ToolResult


def get_failure(
    results: Dict[str, ToolResult],
) -> Tuple[Optional[str], Optional[ToolResult]]:
    for name, result in results.items():
        if not result.success:
            return name, result
    return None, None


def summarize_failure(tool_name: str, tool_result: ToolResult) -> Dict[str, Any]:
    errors = tool_result.errors or []
    logs = tool_result.logs or []
    message = errors[0] if errors else "Unknown failure."

    return {
        "error_type": tool_name,
        "message": message,
        "logs": logs,
    }


def apply_revision(env_spec: Dict[str, Any], decision: AgentDecision) -> Dict[str, Any]:
    updated = dict(env_spec)
    changes = list(updated.get("changes", []))
    changes.extend(decision.changes)
    updated["changes"] = changes
    updated["last_action"] = decision.action
    return updated
