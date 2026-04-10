from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def home_dir() -> Path:
    override = os.environ.get("REPORESOLVE_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".reporesolve"


def config_file_path() -> Path:
    return home_dir() / "config.json"


def run_dir() -> Path:
    override = os.environ.get("REPORESOLVE_WORKDIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path.cwd().resolve()


def workspace_dir() -> Path:
    return run_dir()


def artifacts_dir() -> Path:
    return run_dir() / "artifacts"


def latest_run_dir() -> Optional[Path]:
    base = artifacts_dir()
    if not base.exists():
        return None

    candidates = [
        path
        for path in base.iterdir()
        if path.is_dir() and (path / "report.json").exists()
    ]
    if not candidates:
        return None

    return max(candidates, key=lambda path: (path / "report.json").stat().st_mtime)
