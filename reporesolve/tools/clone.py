from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from .base import ToolResult


def _is_repo_url(value: str) -> bool:
    lower = value.lower()
    return lower.startswith(("http://", "https://", "ssh://")) or value.startswith("git@")


def _is_github_repo(value: str) -> bool:
    lower = value.lower()
    return "github.com/" in lower or lower.startswith("git@github.com:")


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


def _looks_like_github_auth_error(stderr: str) -> bool:
    lowered = stderr.lower()
    patterns = (
        "authentication failed",
        "could not read username",
        "permission denied (publickey)",
        "permission to ",
        "repository not found",
        "support for password authentication was removed",
        "fatal: could not read from remote repository",
    )
    return any(pattern in lowered for pattern in patterns)


def _github_auth_status_hint() -> Optional[str]:
    try:
        result = subprocess.run(
            ["gh", "auth", "status", "--hostname", "github.com"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    except Exception:
        return None

    if result.returncode == 0:
        return None

    return (
        "GitHub authentication does not appear to be configured. "
        "Run `gh auth login` or configure GitHub SSH access, then rerun RepoResolve."
    )


def _github_clone_guidance(repo: str, stderr: str) -> Optional[str]:
    auth_hint = _github_auth_status_hint()
    if auth_hint:
        return (
            f"Failed to clone {repo}. {auth_hint} "
            "If the repo is private, make sure your GitHub account has access."
        )

    if _looks_like_github_auth_error(stderr):
        return (
            f"Failed to clone {repo}. GitHub access may not be configured for this machine. "
            "Run `gh auth login` or configure GitHub SSH access, then rerun RepoResolve."
        )

    return None


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
                    guidance = None
                    if _is_github_repo(repo):
                        guidance = _github_clone_guidance(repo, result.stderr or "")
                    errors.append(
                        guidance or f"Failed to clone {repo} (exit {result.returncode})."
                    )
                    if guidance:
                        logs.append("Clone stopped because GitHub authentication/setup is required.")
                        break
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
