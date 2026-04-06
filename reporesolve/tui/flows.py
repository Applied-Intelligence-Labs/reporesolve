from __future__ import annotations

from typing import Optional

from ..supervisor.state import SessionState
from . import prompts, render


def run_guided_flow() -> Optional[SessionState]:
    render.show_welcome()
    try:
        repos = prompts.prompt_repos()
        main_repo = prompts.prompt_main_repo(repos)
        working_name = prompts.prompt_working_name()
        mode = prompts.prompt_mode()
        provider = prompts.prompt_provider()
        model = prompts.prompt_model(provider)
        api_key = prompts.prompt_api_key(provider)

        state = SessionState(
            repos=repos,
            main_repo=main_repo,
            working_name=working_name,
            mode=mode,
            provider=provider,
            model=model,
            api_key=api_key,
        )

        render.show_summary(state)
        if not prompts.confirm_proceed():
            render.show_abort()
            return None
        render.show_loading("Starting session...")
        return state
    except KeyboardInterrupt:
        render.show_abort()
        return None
