from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List

from .base import ToolResult

def _is_repo_url(value: str) -> bool:
    lower = value.lower()
    return lower.startswith(("http://", "https://", "ssh://")) or value.startswith("git@")


def _derive_repo_name(value: str) -> str:
    if _is_repo_url(value):
        cleaned = value.rstrip("/").replace(":", "/")
        name = cleaned.split("/")[-1]
    else:
        name = Path(value).name
    if name.endswith(".git"):
        name = name[:-4]
    return name or "repo"


def _unique_path(base: Path, name: str) -> Path:
    candidate = base / name
    if not candidate.exists():
        return candidate
    index = 1
    while True:
        candidate = base / f"{name}-{index}"
        if not candidate.exists():
            return candidate
        index += 1


def clone_repos(repos: List[str], workspace_path: str) -> ToolResult:
    logs: List[str] = []
    errors: List[str] = []
    cloned_paths: List[str] = []

    base_dir = Path(workspace_path) / "repos"
    base_dir.mkdir(parents=True, exist_ok=True)

    for repo in repos:
        repo = repo.strip()
        if not repo:
            continue

        dest = _unique_path(base_dir, _derive_repo_name(repo))
        try:
            src_path = Path(repo).expanduser()
            if src_path.exists():
                shutil.copytree(src_path, dest)
                logs.append(f"Copied local repo from {src_path} to {dest}.")
                cloned_paths.append(str(dest))
                continue

            if _is_repo_url(repo):
                result = subprocess.run(
                    ["git", "clone", repo, str(dest)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                logs.append(f"git clone {repo} -> {dest}")
                if result.stdout:
                    logs.append(result.stdout.strip())
                if result.stderr:
                    logs.append(result.stderr.strip())
                if result.returncode != 0:
                    errors.append(f"Failed to clone {repo} (exit {result.returncode}).")
                    continue
                cloned_paths.append(str(dest))
                continue

            errors.append(f"Invalid repo input: {repo}")
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(f"Error processing {repo}: {exc}")

    return ToolResult(
        name="clone_repos",
        success=len(errors) == 0,
        logs=logs,
        errors=errors,
        data={"cloned_paths": cloned_paths},
    )
