from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.panel import Panel

from .. import __version__
from ..config.settings import load_settings, settings_summary
from ..supervisor.supervisor import run_supervisor
from ..tui.flows import run_guided_flow
from ..utils.logging import setup_logging
from ..storage.paths import report_path

app = typer.Typer(add_completion=False, help="RepoResolve - agentic supervisor system")
console = Console()


def _print_settings() -> None:
    settings = load_settings()
    summary = settings_summary(settings)
    print("Current configuration:")
    for key, value in summary.items():
        print(f"- {key}: {value}")


def _not_implemented(feature: str) -> int:
    print(f"{feature} is not implemented yet (Phase 1 skeleton).")
    return 0


def _handle_start() -> int:
    try:
        state = run_guided_flow()
        if state is None:
            return 0
        result = run_supervisor(state)
        console.print(Panel(json.dumps(result, indent=2), title="Final Result", expand=False))
        return 0
    except Exception as exc:
        console.print(Panel(f"Unexpected error: {exc}", title="Error", style="red"))
        return 1


def _handle_resume() -> int:
    path = report_path()
    if not path.exists():
        console.print(Panel("No previous report found.", title="Resume"))
        return 0

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        console.print(Panel("Report file is invalid JSON.", title="Resume"))
        return 1
    except Exception as exc:
        console.print(Panel(f"Failed to read report: {exc}", title="Resume", style="red"))
        return 1

    history = data.get("history", [])
    result = data.get("result", {})

    console.print(Panel(f"Attempts: {len(history)}", title="Previous Session"))
    if history:
        last = history[-1]
        decision = last.get("decision", {})
        console.print(
            Panel(
                json.dumps(decision, indent=2),
                title="Last Decision",
                expand=False,
            )
        )
    console.print(Panel(json.dumps(result, indent=2), title="Last Result", expand=False))
    return 0


def _handle_doctor() -> int:
    return _not_implemented("Doctor checks")


def _handle_config() -> int:
    _print_settings()
    print("Config wizard is not implemented yet (Phase 1 skeleton).")
    return 0


def _handle_version() -> int:
    print(__version__)
    return 0


@app.callback(invoke_without_command=True)
def _main(ctx: typer.Context) -> None:
    setup_logging()
    if ctx.invoked_subcommand is None:
        raise typer.Exit(code=_handle_start())


@app.command()
def start() -> None:
    """Start guided flow."""
    raise typer.Exit(code=_handle_start())


@app.command()
def config() -> None:
    """Configure provider and model."""
    raise typer.Exit(code=_handle_config())


@app.command()
def resume() -> None:
    """Resume the last session."""
    raise typer.Exit(code=_handle_resume())


@app.command()
def doctor() -> None:
    """Run system checks."""
    raise typer.Exit(code=_handle_doctor())


@app.command()
def version() -> None:
    """Show version."""
    raise typer.Exit(code=_handle_version())


if __name__ == "__main__":
    app()
