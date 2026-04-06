from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from .base import ToolResult


def _parse_requirements(path: Path) -> List[str]:
    deps: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        deps.append(stripped)
    return deps


def _parse_environment_yml(path: Path) -> List[Tuple[str, str]]:
    deps: List[Tuple[str, str]] = []
    in_deps = False
    deps_indent = None
    in_pip = False
    pip_indent = None

    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.rstrip()
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue

        indent = len(raw) - len(raw.lstrip())
        stripped = raw.strip()

        if stripped.startswith("dependencies:"):
            in_deps = True
            deps_indent = indent
            in_pip = False
            pip_indent = None
            continue

        if not in_deps:
            continue

        if deps_indent is not None and indent <= deps_indent and not stripped.startswith("-"):
            in_deps = False
            in_pip = False
            continue

        if stripped.startswith("- pip:"):
            in_pip = True
            pip_indent = indent
            continue

        if in_pip and pip_indent is not None and indent <= pip_indent:
            in_pip = False
            pip_indent = None

        if stripped.startswith("-"):
            dep = stripped[1:].strip()
            if in_pip:
                deps.append(("pip", dep))
            else:
                deps.append(("conda", dep))

    return deps


def parse_dependencies(repo_metadata: Dict[str, Any]) -> ToolResult:
    logs: List[str] = []
    errors: List[str] = []
    parsed: List[Dict[str, object]] = []

    repos = repo_metadata.get("repos", [])
    if not isinstance(repos, list):
        return ToolResult(
            name="parse_dependencies",
            success=False,
            logs=logs,
            errors=["Invalid repo metadata: expected list under 'repos'."],
            data={"dependencies": []},
        )

    for repo in repos:
        if not isinstance(repo, dict):
            errors.append("Invalid repo entry; expected dict.")
            continue

        repo_path = repo.get("path")
        if not repo_path:
            errors.append("Repo entry missing 'path'.")
            continue

        items: List[Dict[str, str]] = []

        try:
            req_path = repo.get("requirements_txt")
            if req_path:
                for dep in _parse_requirements(Path(req_path)):
                    items.append(
                        {"spec": dep, "manager": "pip", "source": "requirements.txt"}
                    )

            env_path = repo.get("environment_yml")
            if env_path:
                for manager, dep in _parse_environment_yml(Path(env_path)):
                    items.append(
                        {
                            "spec": dep,
                            "manager": manager,
                            "source": "environment.yml",
                        }
                    )

            if repo.get("setup_py"):
                logs.append(f"{repo_path}: setup.py detected (parsing not implemented).")
            if repo.get("pyproject_toml"):
                logs.append(
                    f"{repo_path}: pyproject.toml detected (parsing not implemented)."
                )
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(f"Failed parsing dependencies for {repo_path}: {exc}")

        parsed.append({"path": repo_path, "dependencies": items})

    return ToolResult(
        name="parse_dependencies",
        success=len(errors) == 0,
        logs=logs,
        errors=errors,
        data={"dependencies": parsed},
    )
