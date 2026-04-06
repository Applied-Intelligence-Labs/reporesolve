from __future__ import annotations

import os
from pathlib import Path


def home_dir() -> Path:
    override = os.environ.get("REPORESOLVE_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".reporesolve"


def config_file_path() -> Path:
    return home_dir() / "config.json"


def workspace_dir() -> Path:
    return home_dir() / "workspace"


def artifacts_dir() -> Path:
    return workspace_dir() / "artifacts"


def report_path() -> Path:
    return artifacts_dir() / "report.json"
