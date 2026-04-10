from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import questionary

from ..agent.schema import ProposedChange
from ..config.settings import load_settings


_REPO_URL = re.compile(r"^(https?|ssh)://", re.IGNORECASE)


def _is_repo_url(value: str) -> bool:
    return bool(_REPO_URL.match(value)) or value.startswith("git@")


def _is_local_path(value: str) -> bool:
    try:
        return Path(value).expanduser().exists()
    except OSError:
        return False


def _validate_repo_input(value: str) -> bool | str:
    trimmed = value.strip()
    if trimmed == "":
        return True
    if _is_repo_url(trimmed) or _is_local_path(trimmed):
        return True
    return "Enter a valid repo URL (https://, ssh://, git@) or an existing local path."


def prompt_repos() -> List[str]:
    repos: List[str] = []
    while len(repos) < 5:
        remaining = 5 - len(repos)
        answer = questionary.text(
            f"Repository path or URL ({remaining} remaining, leave blank to finish):",
            validate=_validate_repo_input,
        ).ask()
        if answer is None:
            raise KeyboardInterrupt
        answer = answer.strip()
        if answer == "":
            if repos:
                break
            print("Please add at least one repository.")
            continue
        repos.append(answer)
    return repos


def prompt_main_repo(repos: List[str]) -> str:
    answer = questionary.select("Select main repository:", choices=repos).ask()
    if answer is None:
        raise KeyboardInterrupt
    return answer


def prompt_working_name() -> str:
    answer = questionary.text("Working copy name:", default="working-repo").ask()
    if answer is None:
        raise KeyboardInterrupt
    answer = answer.strip()
    return answer or "working-repo"


def prompt_mode() -> str:
    choices = ["Guided", "Auto", "Review"]
    answer = questionary.select("Select mode:", choices=choices, default="Guided").ask()
    if answer is None:
        raise KeyboardInterrupt
    return answer.lower()


def prompt_provider() -> str:
    choices = ["OpenAI", "Anthropic"]
    answer = questionary.select("Select provider:", choices=choices, default="OpenAI").ask()
    if answer is None:
        raise KeyboardInterrupt
    return answer.lower()


def prompt_model(provider: str) -> str:
    default_model = "gpt-5.4" if provider == "openai" else "claude-sonnet-4-6"
    answer = questionary.text("Model:", default=default_model).ask()
    if answer is None:
        raise KeyboardInterrupt
    model = answer.strip()
    return model or default_model


def prompt_api_key(provider: str) -> Optional[str]:
    settings = load_settings()
    existing_key = (
        settings.openai_api_key if provider == "openai" else settings.anthropic_api_key
    )
    if existing_key:
        return existing_key

    prompt = "OpenAI API key:" if provider == "openai" else "Anthropic API key:"
    answer = questionary.password(prompt, validate=lambda v: v.strip() != "").ask()
    if answer is None:
        raise KeyboardInterrupt
    return answer.strip()


def confirm_proceed() -> bool:
    answer = questionary.confirm("Proceed?", default=True).ask()
    if answer is None:
        raise KeyboardInterrupt
    return bool(answer)


def _validate_custom_value(value: str) -> bool | str:
    if value.strip() == "":
        return "Enter a value or cancel this review."
    return True


def prompt_change_resolution(
    change: ProposedChange,
    alternates: List[str],
    mode: str,
) -> Dict[str, Any]:
    if mode == "auto":
        return {
            "resolution": "accepted",
            "selected_value": change.proposed_value,
            "action": change.action,
        }

    choices = ["Accept suggestion"]
    if change.current_value:
        choices.append("Reject and keep current value")
    else:
        choices.append("Reject suggestion")
    if alternates:
        choices.append("Choose alternate suggestion")
    choices.extend(["Enter custom value", "Defer conflict"])

    answer = questionary.select(
        f"How should RepoResolve handle {change.package}?",
        choices=choices,
        default="Accept suggestion",
    ).ask()
    if answer is None:
        raise KeyboardInterrupt

    if answer == "Accept suggestion":
        return {
            "resolution": "accepted",
            "selected_value": change.proposed_value,
            "action": change.action,
        }

    if answer == "Reject and keep current value":
        return {
            "resolution": "rejected",
            "selected_value": change.current_value,
            "action": "pin" if change.current_value else "note",
        }

    if answer == "Reject suggestion":
        return {
            "resolution": "rejected",
            "selected_value": None,
            "action": "note",
        }

    if answer == "Choose alternate suggestion":
        alternate = questionary.select(
            f"Choose an alternate value for {change.package}:",
            choices=alternates,
        ).ask()
        if alternate is None:
            raise KeyboardInterrupt
        return {
            "resolution": "alternate",
            "selected_value": alternate,
            "action": "replace" if change.current_value else "add",
        }

    if answer == "Enter custom value":
        default_value = change.proposed_value or change.current_value or ""
        custom = questionary.text(
            f"Enter the value to use for {change.package}:",
            default=default_value,
            validate=_validate_custom_value,
        ).ask()
        if custom is None:
            raise KeyboardInterrupt
        return {
            "resolution": "custom",
            "selected_value": custom.strip(),
            "action": "replace" if change.current_value else "add",
        }

    return {
        "resolution": "deferred",
        "selected_value": None,
        "action": "defer",
    }
