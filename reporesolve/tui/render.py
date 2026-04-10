from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..agent.schema import ProposedChange
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


def show_change_review(
    change: ProposedChange,
    index: int,
    total: int,
    alternates: list[str],
) -> None:
    table = Table(show_header=False, box=None)
    table.add_row("Package", change.package)
    table.add_row("Manager", change.manager)
    table.add_row("Action", change.action)
    table.add_row("Current", change.current_value or "(none)")
    table.add_row("Suggested", change.proposed_value or "(none)")
    table.add_row("Reason", change.reason)
    table.add_row("Confidence", f"{change.confidence:.2f}")
    table.add_row("Sources", "\n".join(change.sources) if change.sources else "(none)")
    if alternates:
        table.add_row("Alternates", "\n".join(alternates))
    console.print(Panel(table, title=f"Review Change {index}/{total}", expand=False))


def show_review_summary(total: int, accepted: int, overridden: int, deferred: int) -> None:
    table = Table(show_header=False, box=None)
    table.add_row("Reviewed", str(total))
    table.add_row("Accepted", str(accepted))
    table.add_row("Overrides", str(overridden))
    table.add_row("Deferred", str(deferred))
    console.print(Panel(table, title="Review Summary", expand=False))
