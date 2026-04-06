"""Supervisor orchestration for RepoResolve."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..agent.planner import AgentPlanner
from ..agent.schema import AgentDecision
from ..providers.anthropic_provider import AnthropicProvider
from ..providers.openai_provider import OpenAIProvider
from ..storage.paths import artifacts_dir, report_path, workspace_dir
from ..tools.base import ToolResult
from ..tools.build import build_environment
from ..tools.clone import clone_repos
from ..tools.install import install_repos
from ..tools.inspect import inspect_repos
from ..tools.parse import parse_dependencies
from ..tools.smoke import run_smoke_tests
from .state import SessionState
from .workflow import apply_revision, get_failure, summarize_failure

console = Console()


def _trim_history(history: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    trimmed: list[Dict[str, Any]] = []
    for entry in history:
        item = dict(entry)
        results = item.get("result", {})
        if isinstance(results, dict):
            new_results = {}
            for name, result in results.items():
                if isinstance(result, dict):
                    updated = dict(result)
                    logs = updated.get("logs", [])
                    if isinstance(logs, list):
                        updated["logs"] = logs[-20:]
                    new_results[name] = updated
                else:
                    new_results[name] = result
            item["result"] = new_results
        trimmed.append(item)
    return trimmed


def _select_provider(state: SessionState):
    if state.provider == "anthropic":
        return AnthropicProvider(api_key=state.api_key, model=state.model)
    return OpenAIProvider(api_key=state.api_key, model=state.model)


def _record_history(
    state: SessionState,
    attempt: int,
    decision: AgentDecision,
    results: Dict[str, ToolResult],
) -> None:
    state.history.append(
        {
            "attempt": attempt,
            "decision": decision.to_dict(),
            "result": {name: result.to_dict() for name, result in results.items()},
        }
    )


def _render_decision(decision: AgentDecision, title: str) -> None:
    table = Table(show_header=False, box=None)
    table.add_row("Action", decision.action)
    table.add_row("Reason", decision.reason)
    table.add_row("Changes", json.dumps(decision.changes, indent=2) or "[]")
    table.add_row("Retry", str(decision.retry))
    table.add_row("Confidence", f"{decision.confidence:.2f}")
    console.print(Panel(table, title=title, expand=False))


def _render_failure(summary: Dict[str, Any]) -> None:
    table = Table(show_header=False, box=None)
    table.add_row("Error type", summary.get("error_type", "unknown"))
    table.add_row("Message", summary.get("message", ""))
    logs = summary.get("logs", [])
    if logs:
        table.add_row("Logs", "\n".join(logs[-5:]))
    console.print(Panel(table, title="Failure", style="red", expand=False))


def _sanitize_session(state: SessionState) -> Dict[str, Any]:
    payload = asdict(state)
    payload["api_key_provided"] = bool(payload.get("api_key"))
    payload.pop("api_key", None)
    return payload


def _write_report(
    workspace: Path,
    session_state: SessionState,
    result: Dict[str, Any],
    run_id: str,
    timestamp: str,
) -> str:
    artifacts = artifacts_dir()
    artifacts.mkdir(parents=True, exist_ok=True)
    report = {
        "run_id": run_id,
        "timestamp": timestamp,
        "session": _sanitize_session(session_state),
        "history": _trim_history(session_state.history),
        "result": result,
    }
    path = report_path()
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return str(path)


def _finalize(
    workspace: Path,
    session_state: SessionState,
    result: Dict[str, Any],
    run_id: str,
    timestamp: str,
) -> Dict[str, Any]:
    result["attempts"] = len(session_state.history)
    result["report_path"] = _write_report(workspace, session_state, result, run_id, timestamp)
    return result


def run_supervisor(session_state: SessionState, max_attempts: int = 3) -> Dict[str, Any]:
    console.print(Panel("Starting supervisor run...", title="RepoResolve"))

    workspace = workspace_dir()
    console.print(f"Workspace: {workspace}")
    run_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()

    with console.status("Cloning repos..."):
        clone_result = clone_repos(session_state.repos, str(workspace))
    console.print(
        "[green]Clone complete.[/green]"
        if clone_result.success
        else "[red]Clone failed.[/red]"
    )
    if not clone_result.success:
        failure = summarize_failure("clone_repos", clone_result)
        _render_failure(failure)
        return _finalize(
            workspace,
            session_state,
            {"success": False, "stage": "clone", "failure": failure},
            run_id,
            timestamp,
        )

    repo_paths = clone_result.data.get("cloned_paths") or session_state.repos

    with console.status("Inspecting repos..."):
        inspect_result = inspect_repos(repo_paths)
    console.print(
        "[green]Inspection complete.[/green]"
        if inspect_result.success
        else "[red]Inspection failed.[/red]"
    )
    if not inspect_result.success:
        failure = summarize_failure("inspect_repos", inspect_result)
        _render_failure(failure)
        return _finalize(
            workspace,
            session_state,
            {"success": False, "stage": "inspect", "failure": failure},
            run_id,
            timestamp,
        )

    with console.status("Parsing dependencies..."):
        parse_result = parse_dependencies(inspect_result.data)
    console.print(
        "[green]Parsing complete.[/green]"
        if parse_result.success
        else "[red]Parsing failed.[/red]"
    )
    if not parse_result.success:
        failure = summarize_failure("parse_dependencies", parse_result)
        _render_failure(failure)
        return _finalize(
            workspace,
            session_state,
            {"success": False, "stage": "parse", "failure": failure},
            run_id,
            timestamp,
        )

    provider = _select_provider(session_state)
    planner = AgentPlanner(provider)

    decision = planner.plan_initial_environment(parse_result.data)
    _render_decision(decision, "Agent Decision (initial)")

    attempt = 1
    env_spec: Dict[str, Any] = {"base": {}, "changes": decision.changes, "attempt": attempt}

    while attempt <= max_attempts:
        console.print(Panel(f"Attempt {attempt}/{max_attempts}", style="cyan", expand=False))
        env_spec["attempt"] = attempt

        with console.status("Building environment..."):
            build_result = build_environment(env_spec)
        with console.status("Installing repos..."):
            install_result = install_repos(env_spec, repo_paths)
        with console.status("Running smoke tests..."):
            smoke_result = run_smoke_tests(repo_paths)

        result_bundle = {
            "build": build_result,
            "install": install_result,
            "smoke": smoke_result,
        }

        _record_history(session_state, attempt, decision, result_bundle)

        # TODO: Consider validating smoke_result.data["results"] in future.
        if all(result.success for result in result_bundle.values()):
            console.print(Panel("Run completed successfully.", title="Success", style="green"))
            final = {
                "success": True,
                "stage": "smoke",
                "history": session_state.history,
                "result": smoke_result.to_dict(),
                "decision": decision.to_dict(),
            }
            console.print(
                Panel(
                    f"Attempts: {len(session_state.history)}\nStatus: success",
                    title="Summary",
                    style="green",
                )
            )
            return _finalize(workspace, session_state, final, run_id, timestamp)

        failing_name, failing_result = get_failure(result_bundle)
        failure = summarize_failure(failing_name or "unknown", failing_result or ToolResult(name="unknown", success=False))
        _render_failure(failure)

        revision = planner.revise_environment(
            {"attempt": attempt, "env_spec": env_spec},
            failure,
        )
        _render_decision(revision, "Agent Decision (revision)")

        if revision.action == "stop" or not revision.retry:
            console.print(Panel("Agent requested stop.", title="Stopped", style="yellow"))
            final = {
                "success": False,
                "stage": "revise",
                "history": session_state.history,
                "failure": failure,
                "decision": revision.to_dict(),
            }
            console.print(
                Panel(
                    f"Attempts: {len(session_state.history)}\nStatus: stopped",
                    title="Summary",
                    style="yellow",
                )
            )
            return _finalize(workspace, session_state, final, run_id, timestamp)

        env_spec = apply_revision(env_spec, revision)
        decision = revision
        attempt += 1

    console.print(Panel("Max attempts reached.", title="Stopped", style="red"))
    final = {
        "success": False,
        "stage": "max_attempts",
        "history": session_state.history,
        "failure": {"error_type": "max_attempts", "message": "Max attempts reached.", "logs": []},
    }
    console.print(
        Panel(
            f"Attempts: {len(session_state.history)}\nStatus: max attempts reached",
            title="Summary",
            style="red",
        )
    )
    return _finalize(workspace, session_state, final, run_id, timestamp)
