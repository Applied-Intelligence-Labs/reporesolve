from __future__ import annotations

from typing import List

from .base import ToolResult


def run_smoke_tests(repo_paths: List[str]) -> ToolResult:
    logs: List[str] = [
        "Smoke execution is not part of RepoResolve v0 main flow.",
        "Use `reporesolve doctor` for the supported validation path.",
    ]
    errors: List[str] = [
        "Standalone smoke execution is outside the RepoResolve v0 release flow."
    ]

    return ToolResult(
        name="run_smoke_tests",
        success=False,
        logs=logs,
        errors=errors,
        data={"repo_count": len(repo_paths)},
    )
