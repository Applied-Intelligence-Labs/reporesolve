from __future__ import annotations

from typing import Any, Dict, List

from .base import ToolResult


def build_environment(env_spec: Dict[str, Any]) -> ToolResult:
    logs: List[str] = ["Mock build_environment invoked."]
    errors: List[str] = []

    if not env_spec:
        logs.append("No environment spec provided; skipping build (mock).")

    return ToolResult(
        name="build_environment",
        success=True,
        logs=logs,
        errors=errors,
        data={},
    )
