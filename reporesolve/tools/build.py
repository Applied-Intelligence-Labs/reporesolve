from __future__ import annotations

from typing import Any, Dict, List

from .base import ToolResult


def build_environment(env_spec: Dict[str, Any]) -> ToolResult:
    logs: List[str] = [
        "Build execution is not part of RepoResolve v0 main flow.",
        "Use `reporesolve doctor` for solve/install validation against generated artifacts.",
    ]
    errors: List[str] = [
        "Standalone environment build execution is outside the RepoResolve v0 release flow."
    ]

    if not env_spec:
        logs.append("No environment spec was provided.")

    return ToolResult(
        name="build_environment",
        success=False,
        logs=logs,
        errors=errors,
        data={"env_spec_provided": bool(env_spec)},
    )
