from __future__ import annotations

from typing import List

from .base import ToolResult


def run_smoke_tests(repo_paths: List[str]) -> ToolResult:
    logs: List[str] = ["Mock run_smoke_tests invoked."]
    errors: List[str] = []

    results = []
    for path in repo_paths:
        results.append({"path": path, "success": True, "detail": "mock"})

    return ToolResult(
        name="run_smoke_tests",
        success=True,
        logs=logs,
        errors=errors,
        data={"results": results},
    )
