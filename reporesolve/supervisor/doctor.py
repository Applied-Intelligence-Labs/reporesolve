from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..storage.paths import latest_run_dir

console = Console()

_ENV_VAR_RE = re.compile(r"\b([A-Z][A-Z0-9_]{2,})\b")
_SCRIPT_RE = re.compile(r"(?:\.\/)?(?:extras/|scripts/)?[A-Za-z0-9._/-]+\.sh")
_INSTALL_CMD_RE = re.compile(r"\b(?:apt(?:-get)?|yum|brew)\s+install\b", re.IGNORECASE)


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _trim_lines(text: str, limit: int = 20) -> List[str]:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    return lines[-limit:]


def _run_command(command: List[str], timeout: int = 600) -> Dict[str, Any]:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    parsed: Optional[Any] = None
    if result.stdout.strip():
        try:
            parsed = json.loads(result.stdout)
        except json.JSONDecodeError:
            parsed = None

    logs = _trim_lines(result.stdout) + _trim_lines(result.stderr)
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "json": parsed,
        "logs": logs[-20:],
    }


def _render_check_table(title: str, rows: List[tuple[str, str]]) -> None:
    table = Table(show_header=False, box=None)
    for key, value in rows:
        table.add_row(key, value)
    console.print(Panel(table, title=title, expand=False))


def _artifact_paths(run_dir: Path) -> Dict[str, Path]:
    return {
        "report": run_dir / "report.json",
        "environment": run_dir / "environment.generated.yml",
        "manual_setup_md": run_dir / "manual-setup.md",
        "manual_setup_json": run_dir / "manual-setup.json",
    }


def _load_latest_run() -> Dict[str, Any]:
    run_dir = latest_run_dir()
    if run_dir is None:
        raise FileNotFoundError("No previous run artifacts were found.")

    paths = _artifact_paths(run_dir)
    missing = [name for name, path in paths.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            f"Latest run is missing required artifacts: {', '.join(sorted(missing))}."
        )

    report = _load_json(paths["report"])
    manual_setup = _load_json(paths["manual_setup_json"])
    environment_text = paths["environment"].read_text(encoding="utf-8")
    return {
        "run_dir": run_dir,
        "paths": paths,
        "report": report,
        "manual_setup": manual_setup,
        "environment_text": environment_text,
    }


def _parse_environment_name(environment_text: str) -> Optional[str]:
    for line in environment_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("name:"):
            value = stripped.split(":", 1)[1].strip()
            return value or None
    return None


def _check_conda_available() -> Dict[str, Any]:
    conda_path = shutil.which("conda")
    if not conda_path:
        return {
            "name": "conda",
            "status": "failed",
            "message": "Conda is not available on PATH.",
            "logs": [],
        }

    result = _run_command(["conda", "--version"], timeout=30)
    status = "passed" if result["returncode"] == 0 else "failed"
    message = (
        result["logs"][-1] if result["logs"] else "Conda is callable."
        if status == "passed"
        else "Conda invocation failed."
    )
    return {
        "name": "conda",
        "status": status,
        "message": message,
        "path": conda_path,
        "logs": result["logs"],
    }


def _check_environment_visibility(environment_name: Optional[str]) -> Dict[str, Any]:
    if not environment_name:
        return {
            "name": "environment_visibility",
            "status": "not_attempted",
            "message": "Generated environment does not declare a name.",
            "logs": [],
        }

    result = _run_command(["conda", "env", "list", "--json"], timeout=60)
    if result["returncode"] != 0:
        return {
            "name": "environment_visibility",
            "status": "failed",
            "message": "Failed to query conda environments.",
            "logs": result["logs"],
        }

    envs = []
    if isinstance(result["json"], dict):
        raw_envs = result["json"].get("envs", [])
        if isinstance(raw_envs, list):
            envs = [str(item) for item in raw_envs]

    exists = any(Path(path).name == environment_name for path in envs)
    return {
        "name": "environment_visibility",
        "status": "passed" if exists else "not_attempted",
        "message": (
            f"Environment `{environment_name}` is visible to conda."
            if exists
            else f"Environment `{environment_name}` is not currently visible to conda."
        ),
        "logs": result["logs"],
    }


def _check_system_package_clue(clue: Dict[str, Any]) -> List[Dict[str, Any]]:
    excerpt = str(clue.get("excerpt", ""))
    checks: List[Dict[str, Any]] = []
    match = _INSTALL_CMD_RE.search(excerpt)
    if not match:
        return [
            {
                "category": clue.get("category", "system_package_command"),
                "status": "manual_review",
                "message": "System package command detected but could not be parsed.",
                "file_path": clue.get("file_path"),
                "excerpt": excerpt,
            }
        ]

    tail = excerpt[match.end() :].strip()
    packages = [
        token
        for token in re.split(r"\s+", tail)
        if token and not token.startswith("-")
    ]
    executable_like = {"git", "wget", "gcc", "g++", "clang", "cmake", "make", "ninja"}
    for package in packages:
        if package in executable_like:
            found = shutil.which(package) is not None
            checks.append(
                {
                    "category": clue.get("category", "system_package_command"),
                    "status": "passed" if found else "blocked_manual",
                    "message": (
                        f"Executable `{package}` is available."
                        if found
                        else f"Executable `{package}` was not found on PATH."
                    ),
                    "file_path": clue.get("file_path"),
                    "excerpt": excerpt,
                }
            )
        else:
            checks.append(
                {
                    "category": clue.get("category", "system_package_command"),
                    "status": "manual_review",
                    "message": f"Package `{package}` cannot be verified automatically in v0.",
                    "file_path": clue.get("file_path"),
                    "excerpt": excerpt,
                }
            )
    return checks


def _check_environment_variable_clue(clue: Dict[str, Any]) -> List[Dict[str, Any]]:
    excerpt = str(clue.get("excerpt", ""))
    variables = [var for var in _ENV_VAR_RE.findall(excerpt) if "_" in var]
    if not variables:
        return [
            {
                "category": clue.get("category", "environment_variable"),
                "status": "manual_review",
                "message": "Environment variable setup detected but variable names could not be parsed.",
                "file_path": clue.get("file_path"),
                "excerpt": excerpt,
            }
        ]

    results: List[Dict[str, Any]] = []
    for variable in variables:
        present = bool(os.environ.get(variable))
        results.append(
            {
                "category": clue.get("category", "environment_variable"),
                "status": "passed" if present else "blocked_manual",
                "message": (
                    f"Environment variable `{variable}` is set."
                    if present
                    else f"Environment variable `{variable}` is not set."
                ),
                "file_path": clue.get("file_path"),
                "excerpt": excerpt,
            }
        )
    return results


def _check_setup_script_clue(clue: Dict[str, Any]) -> Dict[str, Any]:
    excerpt = str(clue.get("excerpt", ""))
    script_match = _SCRIPT_RE.search(excerpt)
    script_path = script_match.group(0) if script_match else None
    script_exists = False
    if script_path:
        source_file = clue.get("file_path")
        if isinstance(source_file, str):
            candidate = Path(source_file).resolve().parent / script_path
            script_exists = candidate.exists()

    return {
        "category": clue.get("category", "setup_script"),
        "status": "manual_review",
        "message": (
            f"Setup script reference `{script_path}` detected."
            if script_path
            else "Setup script reference detected."
        ),
        "file_path": clue.get("file_path"),
        "excerpt": excerpt,
        "script_exists": script_exists,
    }


def _check_gpu_runtime_clue(clue: Dict[str, Any]) -> Dict[str, Any]:
    has_gpu_tool = shutil.which("nvidia-smi") is not None
    return {
        "category": clue.get("category", "gpu_runtime"),
        "status": "passed" if has_gpu_tool else "warning",
        "message": (
            "`nvidia-smi` is available."
            if has_gpu_tool
            else "GPU runtime clue detected, but `nvidia-smi` is not available on PATH."
        ),
        "file_path": clue.get("file_path"),
        "excerpt": clue.get("excerpt"),
    }


def _check_binary_runtime_clue(clue: Dict[str, Any]) -> Dict[str, Any]:
    has_patchelf = shutil.which("patchelf") is not None
    return {
        "category": clue.get("category", "binary_runtime"),
        "status": "passed" if has_patchelf else "warning",
        "message": (
            "`patchelf` is available."
            if has_patchelf
            else "`patchelf` requirement detected, but the binary is not on PATH."
        ),
        "file_path": clue.get("file_path"),
        "excerpt": clue.get("excerpt"),
    }


def _check_generic_clue(clue: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "category": clue.get("category", "setup_clue"),
        "status": "manual_review",
        "message": str(clue.get("summary", "Manual review required.")),
        "file_path": clue.get("file_path"),
        "excerpt": clue.get("excerpt"),
    }


def _validate_manual_prerequisites(manual_setup: Dict[str, Any]) -> Dict[str, Any]:
    clues = manual_setup.get("setup_clues", [])
    results: List[Dict[str, Any]] = []

    for clue in clues if isinstance(clues, list) else []:
        if not isinstance(clue, dict):
            continue
        category = str(clue.get("category", "setup_clue"))
        if category == "system_package_command":
            results.extend(_check_system_package_clue(clue))
        elif category == "environment_variable":
            results.extend(_check_environment_variable_clue(clue))
        elif category == "setup_script":
            results.append(_check_setup_script_clue(clue))
        elif category == "gpu_runtime":
            results.append(_check_gpu_runtime_clue(clue))
        elif category == "binary_runtime":
            results.append(_check_binary_runtime_clue(clue))
        else:
            results.append(_check_generic_clue(clue))

    status_counts = {
        "passed": sum(1 for item in results if item["status"] == "passed"),
        "blocked_manual": sum(1 for item in results if item["status"] == "blocked_manual"),
        "warning": sum(1 for item in results if item["status"] == "warning"),
        "manual_review": sum(1 for item in results if item["status"] == "manual_review"),
    }
    return {"checks": results, "counts": status_counts}


def _solve_validation(environment_path: Path, run_dir: Path) -> Dict[str, Any]:
    prefix = run_dir / ".doctor" / "solve-prefix"
    prefix.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "conda",
        "env",
        "create",
        "--dry-run",
        "--json",
        "-f",
        str(environment_path),
        "-p",
        str(prefix),
    ]
    result = _run_command(command, timeout=900)
    if result["returncode"] == 0:
        message = "Conda solve validation passed."
        if isinstance(result["json"], dict):
            message = str(result["json"].get("message") or message)
        return {
            "status": "passed",
            "message": message,
            "logs": result["logs"],
            "command": command,
        }

    message = "Conda solve validation failed."
    if isinstance(result["json"], dict):
        for key in ("message", "error", "exception_name"):
            value = result["json"].get(key)
            if value:
                message = str(value)
                break
    return {
        "status": "failed",
        "message": message,
        "logs": result["logs"],
        "command": command,
    }


def _install_validation(environment_path: Path, run_dir: Path, requested: bool) -> Dict[str, Any]:
    if not requested:
        return {
            "status": "not_attempted",
            "message": "Install validation was not requested.",
            "logs": [],
        }

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    prefix = run_dir / ".doctor" / f"install-{timestamp}"
    prefix.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "conda",
        "env",
        "create",
        "--json",
        "-y",
        "-f",
        str(environment_path),
        "-p",
        str(prefix),
    ]
    result = _run_command(command, timeout=3600)
    if result["returncode"] == 0:
        return {
            "status": "passed",
            "message": f"Install validation created an environment at `{prefix}`.",
            "logs": result["logs"],
            "command": command,
            "prefix": str(prefix),
        }

    message = "Install validation failed."
    if isinstance(result["json"], dict):
        for key in ("message", "error", "exception_name"):
            value = result["json"].get(key)
            if value:
                message = str(value)
                break
    return {
        "status": "failed",
        "message": message,
        "logs": result["logs"],
        "command": command,
        "prefix": str(prefix),
    }


def run_doctor(install: bool = False) -> Dict[str, Any]:
    console.print(
        Panel(
            "Running doctor against the latest generated run in the current directory...",
            title="RepoResolve Doctor",
        )
    )

    loaded = _load_latest_run()
    run_dir: Path = loaded["run_dir"]
    paths: Dict[str, Path] = loaded["paths"]
    report = loaded["report"]
    manual_setup = loaded["manual_setup"]
    environment_text = loaded["environment_text"]

    environment_name = _parse_environment_name(environment_text)

    artifact_rows = [
        ("Run dir", str(run_dir)),
        ("Environment", str(paths["environment"])),
        ("Manual setup", str(paths["manual_setup_md"])),
        ("Manual setup JSON", str(paths["manual_setup_json"])),
    ]
    _render_check_table("Latest Run", artifact_rows)

    conda_check = _check_conda_available()
    _render_check_table(
        "Tooling",
        [
            ("Conda", conda_check["status"]),
            ("Message", conda_check["message"]),
        ],
    )
    if conda_check["status"] != "passed":
        return {
            "success": False,
            "stage": "doctor",
            "run_id": report.get("run_id"),
            "artifact_dir": str(run_dir),
            "tooling": {"conda": conda_check},
            "manual_prerequisites": {"checks": [], "counts": {}},
            "solve_validation": {
                "status": "not_attempted",
                "message": "Conda is unavailable, so solve validation could not run.",
                "logs": [],
            },
            "install_validation": {
                "status": "not_attempted",
                "message": "Conda is unavailable, so install validation could not run.",
                "logs": [],
            },
        }

    environment_visibility = _check_environment_visibility(environment_name)
    manual_prerequisites = _validate_manual_prerequisites(manual_setup)
    _render_check_table(
        "Manual Prerequisites",
        [
            ("Passed", str(manual_prerequisites["counts"].get("passed", 0))),
            ("Blocked", str(manual_prerequisites["counts"].get("blocked_manual", 0))),
            ("Warnings", str(manual_prerequisites["counts"].get("warning", 0))),
            ("Manual review", str(manual_prerequisites["counts"].get("manual_review", 0))),
        ],
    )

    solve_validation = _solve_validation(paths["environment"], run_dir)
    install_validation = (
        _install_validation(paths["environment"], run_dir, requested=install)
        if solve_validation["status"] == "passed"
        else {
            "status": "not_attempted",
            "message": "Install validation was skipped because solve validation did not pass.",
            "logs": [],
        }
    )

    _render_check_table(
        "Validation",
        [
            ("Environment visible", environment_visibility["status"]),
            ("Solve", solve_validation["status"]),
            ("Install", install_validation["status"]),
        ],
    )

    blocked_manual = manual_prerequisites["counts"].get("blocked_manual", 0)
    success = solve_validation["status"] == "passed" and blocked_manual == 0 and install_validation["status"] in {
        "passed",
        "not_attempted",
    }

    summary_rows = [
        ("Run ID", str(report.get("run_id", ""))),
        ("Solve status", solve_validation["status"]),
        ("Install status", install_validation["status"]),
        ("Blocked manual", str(blocked_manual)),
    ]
    _render_check_table("Doctor Summary", summary_rows)

    return {
        "success": success,
        "stage": "doctor",
        "run_id": report.get("run_id"),
        "artifact_dir": str(run_dir),
        "tooling": {
            "conda": conda_check,
            "environment_visibility": environment_visibility,
        },
        "manual_prerequisites": manual_prerequisites,
        "solve_validation": solve_validation,
        "install_validation": install_validation,
    }
