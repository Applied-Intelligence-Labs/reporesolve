from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..supervisor.state import SessionState

console = Console()


def show_welcome() -> None:
    title = "RepoResolve"
    subtitle = "Guided setup for agentic repo resolution"
    console.print(Panel(f"{subtitle}", title=title, expand=False))


def show_summary(state: SessionState) -> None:
    table = Table(show_header=False, box=None)
    table.add_row("Repositories", "\n".join(state.repos))
    table.add_row("Main repo", state.main_repo)
    table.add_row("Working name", state.working_name)
    table.add_row("Mode", state.mode)
    table.add_row("Provider", state.provider)
    table.add_row("Model", state.model)
    console.print(Panel(table, title="Review", expand=False))


def show_abort() -> None:
    console.print("Aborted.")


def show_loading(message: str) -> None:
    console.print(message)
