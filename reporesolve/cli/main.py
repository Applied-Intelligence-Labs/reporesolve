from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.panel import Panel

from .. import __version__
from ..supervisor.doctor import run_doctor
from ..supervisor.supervisor import run_supervisor
from ..tui.flows import run_guided_flow
from ..utils.logging import setup_logging

app = typer.Typer(
    add_completion=False,
    help="RepoResolve - guided multi-repo environment resolution",
)
console = Console()


def _handle_run() -> int:
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


def _handle_doctor(install: bool = False) -> int:
    try:
        result = run_doctor(install=install)
        console.print(Panel(json.dumps(result, indent=2), title="Doctor Result", expand=False))
        return 0 if result.get("success") else 1
    except FileNotFoundError as exc:
        console.print(Panel(str(exc), title="Doctor", style="yellow"))
        return 1
    except Exception as exc:
        console.print(Panel(f"Unexpected error: {exc}", title="Doctor", style="red"))
        return 1


def _handle_version() -> int:
    print(__version__)
    return 0


@app.callback(invoke_without_command=True)
def _main(ctx: typer.Context) -> None:
    setup_logging()
    if ctx.invoked_subcommand is None:
        raise typer.Exit(code=_handle_run())


@app.command()
def start() -> None:
    """Run the guided workflow."""
    raise typer.Exit(code=_handle_run())


@app.command()
def doctor(
    install: bool = typer.Option(
        False,
        "--install",
        help="Attempt disposable install validation after solve passes.",
    ),
) -> None:
    """Validate the latest generated run in the current directory."""
    raise typer.Exit(code=_handle_doctor(install=install))


@app.command()
def version() -> None:
    """Print the installed RepoResolve version."""
    raise typer.Exit(code=_handle_version())


if __name__ == "__main__":
    app()
