from __future__ import annotations

from typing import Any, Dict, List

from .base import ToolResult


def install_repos(env: Dict[str, Any], repo_paths: List[str]) -> ToolResult:
    logs: List[str] = ["Mock install_repos invoked."]
    errors: List[str] = []

    if not repo_paths:
        logs.append("No repositories provided; skipping install (mock).")

    return ToolResult(
        name="install_repos",
        success=True,
        logs=logs,
        errors=errors,
        data={},
    )
