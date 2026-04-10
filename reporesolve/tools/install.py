from __future__ import annotations

from typing import Any, Dict, List

from .base import ToolResult


def install_repos(env: Dict[str, Any], repo_paths: List[str]) -> ToolResult:
    logs: List[str] = [
        "Repository installation is not part of RepoResolve v0 main flow.",
        "Use `reporesolve doctor --install` for disposable install validation of the generated environment.",
    ]
    errors: List[str] = [
        "Standalone repository installation is outside the RepoResolve v0 release flow."
    ]

    if not repo_paths:
        logs.append("No repositories were provided.")

    return ToolResult(
        name="install_repos",
        success=False,
        logs=logs,
        errors=errors,
        data={"repo_count": len(repo_paths), "env_spec_provided": bool(env)},
    )
