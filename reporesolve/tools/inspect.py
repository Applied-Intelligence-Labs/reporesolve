from __future__ import annotations

from pathlib import Path
from typing import List

from .base import ToolResult

def inspect_repos(paths: List[str]) -> ToolResult:
    logs: List[str] = []
    errors: List[str] = []
    repos: List[Dict[str, object]] = []

    for raw_path in paths:
        path = Path(raw_path).expanduser()
        if not path.exists():
            errors.append(f"Repo path does not exist: {path}")
            continue

        repo_info = {
            "path": str(path),
            "requirements_txt": str(path / "requirements.txt")
            if (path / "requirements.txt").exists()
            else None,
            "environment_yml": str(path / "environment.yml")
            if (path / "environment.yml").exists()
            else None,
            "setup_py": str(path / "setup.py") if (path / "setup.py").exists() else None,
            "pyproject_toml": str(path / "pyproject.toml")
            if (path / "pyproject.toml").exists()
            else None,
        }
        repos.append(repo_info)
        logs.append(f"Inspected repo: {path}")

    return ToolResult(
        name="inspect_repos",
        success=len(errors) == 0,
        logs=logs,
        errors=errors,
        data={"repos": repos},
    )
