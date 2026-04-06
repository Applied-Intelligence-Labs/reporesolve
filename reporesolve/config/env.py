from __future__ import annotations

from pathlib import Path
from typing import Dict


def load_dotenv_if_available(path: Path) -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        return

    if path.exists():
        load_dotenv(path, override=False)


def load_env_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}

    values: Dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values
