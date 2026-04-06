from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from .env import load_dotenv_if_available, load_env_file
from ..storage.paths import config_file_path


@dataclass
class Settings:
    provider: Optional[str] = None
    model: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None


def _read_config_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


def load_settings() -> Settings:
    env_file = Path.cwd() / ".env"
    load_dotenv_if_available(env_file)
    env_values = load_env_file(env_file)

    config_values = _read_config_file(config_file_path())

    merged: Dict[str, str] = {}
    merged.update(env_values)
    merged.update(config_values)
    merged.update(os.environ)

    return Settings(
        provider=merged.get("REPORESOLVE_PROVIDER") or merged.get("provider"),
        model=merged.get("REPORESOLVE_MODEL") or merged.get("model"),
        openai_api_key=merged.get("OPENAI_API_KEY") or merged.get("openai_api_key"),
        anthropic_api_key=merged.get("ANTHROPIC_API_KEY")
        or merged.get("anthropic_api_key"),
    )


def _mask_secret(value: Optional[str]) -> str:
    if not value:
        return "(not set)"
    if len(value) <= 4:
        return "****"
    return "*" * (len(value) - 4) + value[-4:]


def settings_summary(settings: Settings) -> Dict[str, str]:
    return {
        "provider": settings.provider or "(not set)",
        "model": settings.model or "(not set)",
        "openai_api_key": _mask_secret(settings.openai_api_key),
        "anthropic_api_key": _mask_secret(settings.anthropic_api_key),
    }
