from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

from .base import ToolResult

_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__"}
_SETUP_FILE_LIMIT = 100
_SETUP_CLUE_LIMIT = 200

_SETUP_CLUE_RULES = [
    {
        "pattern": re.compile(r"\bapt(?:-get)?\s+install\b", re.IGNORECASE),
        "category": "system_package_command",
        "platform": "linux",
        "severity": "required",
        "summary": "Linux system package installation command detected.",
    },
    {
        "pattern": re.compile(r"\bapt(?:-get)?\s+update\b", re.IGNORECASE),
        "category": "system_package_command",
        "platform": "linux",
        "severity": "required",
        "summary": "Linux package index update command detected.",
    },
    {
        "pattern": re.compile(r"\byum\s+install\b", re.IGNORECASE),
        "category": "system_package_command",
        "platform": "linux",
        "severity": "required",
        "summary": "Yum system package installation command detected.",
    },
    {
        "pattern": re.compile(r"\bbrew\s+install\b", re.IGNORECASE),
        "category": "system_package_command",
        "platform": "macos",
        "severity": "required",
        "summary": "Homebrew installation command detected.",
    },
    {
        "pattern": re.compile(r"\b(?:\.\/)?(?:extras/|scripts/)?install_[^\s]+\.sh\b", re.IGNORECASE),
        "category": "setup_script",
        "platform": "any",
        "severity": "required",
        "summary": "Repository setup script reference detected.",
    },
    {
        "pattern": re.compile(r"\bpip\s+install\b", re.IGNORECASE),
        "category": "post_env_command",
        "platform": "any",
        "severity": "required",
        "summary": "Additional pip installation command detected outside the generated environment.",
    },
    {
        "pattern": re.compile(r"\bconda\s+env\s+create\b", re.IGNORECASE),
        "category": "environment_command",
        "platform": "any",
        "severity": "note",
        "summary": "Conda environment creation command detected.",
    },
    {
        "pattern": re.compile(
            r"\b(?:export\s+)?(LD_LIBRARY_PATH|MUJOCO_GL|MUJOCO_PY_MUJOCO_PATH|CUDA_HOME|CUDA_PATH)\b",
            re.IGNORECASE,
        ),
        "category": "environment_variable",
        "platform": "any",
        "severity": "required",
        "summary": "Environment variable setup detected.",
    },
    {
        "pattern": re.compile(r"\b(mujoco(?:-py)?|dm-control|metaworld)\b", re.IGNORECASE),
        "category": "runtime_dependency",
        "platform": "any",
        "severity": "required",
        "summary": "MuJoCo or simulator runtime dependency mention detected.",
    },
    {
        "pattern": re.compile(r"\b(cuda|cudatoolkit|nvidia-smi)\b", re.IGNORECASE),
        "category": "gpu_runtime",
        "platform": "gpu",
        "severity": "warning",
        "summary": "CUDA or GPU runtime requirement mention detected.",
    },
    {
        "pattern": re.compile(r"\b(egl|osmesa|libosmesa|opengl|glx)\b", re.IGNORECASE),
        "category": "graphics_runtime",
        "platform": "linux",
        "severity": "required",
        "summary": "Graphics or headless rendering runtime mention detected.",
    },
    {
        "pattern": re.compile(r"\bpatchelf\b", re.IGNORECASE),
        "category": "binary_runtime",
        "platform": "linux",
        "severity": "warning",
        "summary": "Linux binary patching requirement mention detected.",
    },
    {
        "pattern": re.compile(r"\bgym==0\.21\b", re.IGNORECASE),
        "category": "post_env_command",
        "platform": "any",
        "severity": "required",
        "summary": "Pinned gym installation requirement detected outside core manifest parsing.",
    },
]


def _classify_manifest(path: Path) -> Tuple[str, bool]:
    name = path.name.lower()
    if name.startswith("requirements") and name.endswith(".txt"):
        return "requirements_txt", True
    if name in {"environment.yml", "environment.yaml"}:
        return "environment_yml", True
    if name.endswith((".yml", ".yaml")) and any(
        token in name for token in ("env", "conda", "environment", "requirements", "deps")
    ):
        return "environment_like_yaml", True
    if name.startswith("requirements") and name.endswith(".in"):
        return "requirements_in", False
    if name == "pyproject.toml":
        return "pyproject_toml", False
    if name == "setup.py":
        return "setup_py", False
    if name == "setup.cfg":
        return "setup_cfg", False
    if name == "pipfile":
        return "pipfile", False
    if name == "pipfile.lock":
        return "pipfile_lock", False
    if name == "poetry.lock":
        return "poetry_lock", False
    if name == "uv.lock":
        return "uv_lock", False
    if name.endswith(".txt") and any(
        token in name for token in ("requirements", "deps", "dependency")
    ):
        return "dependency_txt", False
    return "unknown", False


def _is_dependency_candidate(path: Path) -> bool:
    manifest_type, _ = _classify_manifest(path)
    return manifest_type != "unknown"


def _is_setup_clue_file(repo_path: Path, path: Path) -> bool:
    relative = path.relative_to(repo_path)
    relative_parts = [part.lower() for part in relative.parts]
    name = path.name.lower()

    if name == "readme.md":
        return True
    if name == "dockerfile":
        return True
    if relative_parts[:2] == [".github", "workflows"] and name.endswith((".yml", ".yaml")):
        return True
    if name.endswith(".sh"):
        if "extras" in relative_parts or "scripts" in relative_parts:
            return True
        if name.startswith("install_"):
            return True
    return False


def _iter_candidate_files(repo_path: Path, limit: int = 200) -> List[Dict[str, object]]:
    candidates: List[Dict[str, object]] = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for filename in files:
            if len(candidates) >= limit:
                return candidates
            path = Path(root) / filename
            if _is_dependency_candidate(path):
                manifest_type, supported = _classify_manifest(path)
                candidates.append(
                    {
                        "path": str(path),
                        "manifest_type": manifest_type,
                        "supported": supported,
                    }
                )
    return candidates


def _iter_setup_files(repo_path: Path, limit: int = _SETUP_FILE_LIMIT) -> List[str]:
    files: List[str] = []
    for root, dirs, filenames in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for filename in filenames:
            if len(files) >= limit:
                return files
            path = Path(root) / filename
            if _is_setup_clue_file(repo_path, path):
                files.append(str(path))
    return files


def _extract_setup_clues(repo_path: Path, setup_files: List[str]) -> List[Dict[str, object]]:
    clues: List[Dict[str, object]] = []
    seen: set[Tuple[str, int, str]] = set()

    for file_path_raw in setup_files:
        if len(clues) >= _SETUP_CLUE_LIMIT:
            break
        file_path = Path(file_path_raw)
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            if len(clues) >= _SETUP_CLUE_LIMIT:
                break
            line = raw_line.strip()
            if not line:
                continue
            for rule in _SETUP_CLUE_RULES:
                if rule["pattern"].search(line):
                    key = (str(file_path), line_number, str(rule["category"]))
                    if key in seen:
                        break
                    seen.add(key)
                    clues.append(
                        {
                            "repo_path": str(repo_path),
                            "file_path": str(file_path),
                            "relative_path": str(file_path.relative_to(repo_path)),
                            "line_number": line_number,
                            "category": rule["category"],
                            "platform": rule["platform"],
                            "severity": rule["severity"],
                            "summary": rule["summary"],
                            "excerpt": line[:240],
                        }
                    )
                    break

    return clues


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
            "candidates": [],
            "candidate_details": _iter_candidate_files(path),
            "setup_files": _iter_setup_files(path),
            "setup_clues": [],
        }
        repo_info["candidates"] = [
            str(item["path"]) for item in repo_info["candidate_details"] if isinstance(item, dict)
        ]
        repo_info["setup_clues"] = _extract_setup_clues(path, repo_info["setup_files"])
        repos.append(repo_info)
        logs.append(
            f"Inspected repo: {path} "
            f"({len(repo_info['candidate_details'])} manifests, {len(repo_info['setup_clues'])} setup clues)"
        )

    return ToolResult(
        name="inspect_repos",
        success=len(errors) == 0,
        logs=logs,
        errors=errors,
        data={"repos": repos},
    )
