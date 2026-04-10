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

from ..agent.planner import AgentPlanner, AgentPlannerError
from ..agent.schema import AgentDecision, DependencySelection
from ..providers.anthropic_provider import AnthropicProvider
from ..providers.base import ProviderError
from ..providers.openai_provider import OpenAIProvider
from ..storage.paths import artifacts_dir, workspace_dir
from ..tools.clone import clone_repos
from ..tools.inspect import inspect_repos
from ..tools.parse import parse_dependencies
from ..tui import prompts, render
from .state import ManifestSelectionState, ReviewedChange, SessionState, UserOverride
from .workflow import summarize_failure, write_run_artifacts

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


def _trim_result(result: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = dict(result)
    if "history" in cleaned and isinstance(cleaned["history"], list):
        cleaned["history"] = _trim_history(cleaned["history"])
    return cleaned


def _select_provider(state: SessionState):
    if state.provider == "anthropic":
        return AnthropicProvider(api_key=state.api_key, model=state.model)
    return OpenAIProvider(api_key=state.api_key, model=state.model)


def _render_decision(decision: AgentDecision, title: str) -> None:
    table = Table(show_header=False, box=None)
    table.add_row("Action", decision.action)
    table.add_row("Reason", decision.reason)
    table.add_row(
        "Changes",
        json.dumps([change.to_dict() for change in decision.changes], indent=2) or "[]",
    )
    table.add_row("Retry", str(decision.retry))
    table.add_row("Confidence", f"{decision.confidence:.2f}")
    console.print(Panel(table, title=title, expand=False))


def _render_selection(selection: DependencySelection) -> None:
    table = Table(show_header=False, box=None)
    files = selection.selected_files or []
    table.add_row("Selected files", "\n".join(files) if files else "(none)")
    table.add_row("Reason", selection.reason)
    table.add_row("Confidence", f"{selection.confidence:.2f}")
    console.print(Panel(table, title="Dependency Selection", expand=False))


def _render_failure(summary: Dict[str, Any]) -> None:
    table = Table(show_header=False, box=None)
    table.add_row("Error type", summary.get("error_type", "unknown"))
    table.add_row("Message", summary.get("message", ""))
    logs = summary.get("logs", [])
    if logs:
        table.add_row("Logs", "\n".join(logs[-5:]))
    console.print(Panel(table, title="Failure", style="red", expand=False))


def _render_dependency_summary(parse_data: Dict[str, Any]) -> None:
    table = Table(show_header=False, box=None)
    manifests = parse_data.get("manifests", [])
    conflicts = parse_data.get("conflicts", [])
    unsupported_manifests = parse_data.get("unsupported_manifests", [])
    unsupported_entries = parse_data.get("unsupported_entries", [])
    normalized_dependencies = parse_data.get("normalized_dependencies", [])
    table.add_row("Parsed manifests", str(len(manifests)))
    table.add_row("Dependencies", str(len(normalized_dependencies)))
    table.add_row("Conflicts", str(len(conflicts)))
    table.add_row("Unsupported manifests", str(len(unsupported_manifests)))
    table.add_row("Unsupported entries", str(len(unsupported_entries)))
    console.print(Panel(table, title="Dependency Analysis", expand=False))


def _render_generated_artifacts(artifacts: Dict[str, Any]) -> None:
    table = Table(show_header=False, box=None)
    table.add_row("Artifact dir", str(artifacts.get("artifact_dir", "")))
    table.add_row("Environment", str(artifacts.get("environment_yml", "")))
    table.add_row("Manual setup", str(artifacts.get("manual_setup_md", "")))
    table.add_row("Manual setup JSON", str(artifacts.get("manual_setup_json", "")))
    environment_spec = artifacts.get("environment_spec", {})
    manual_setup = artifacts.get("manual_setup", {})
    if isinstance(environment_spec, dict):
        table.add_row(
            "Resolved packages",
            str(len(environment_spec.get("resolved_packages", []))),
        )
        table.add_row(
            "Unresolved conflicts",
            str(len(environment_spec.get("unresolved_conflicts", []))),
        )
    if isinstance(manual_setup, dict):
        table.add_row("Setup clues", str(len(manual_setup.get("setup_clues", []))))
        table.add_row("Manual items", str(len(manual_setup.get("manual_items", []))))
    console.print(Panel(table, title="Generated Artifacts", expand=False))


def _sanitize_session(state: SessionState) -> Dict[str, Any]:
    payload = asdict(state)
    payload["api_key_provided"] = bool(payload.get("api_key"))
    payload.pop("api_key", None)
    return payload


def _alternates_for_change(change: Dict[str, Any], dependency_analysis: Dict[str, Any]) -> list[str]:
    alternates: list[str] = []
    seen: set[str] = set()
    conflicts = dependency_analysis.get("conflicts", [])
    if not isinstance(conflicts, list):
        return alternates

    normalized_name = str(change.get("package", "")).lower().replace("_", "-")
    manager = str(change.get("manager", "unknown"))
    current_value = change.get("current_value")
    proposed_value = change.get("proposed_value")

    for conflict in conflicts:
        if not isinstance(conflict, dict):
            continue
        if str(conflict.get("normalized_name", "")) != normalized_name:
            continue
        if str(conflict.get("manager", "unknown")) != manager:
            continue
        specs = conflict.get("specs", [])
        if not isinstance(specs, list):
            continue
        for spec_entry in specs:
            if not isinstance(spec_entry, dict):
                continue
            spec = spec_entry.get("spec")
            if not isinstance(spec, str):
                continue
            if spec in seen or spec == current_value or spec == proposed_value:
                continue
            seen.add(spec)
            alternates.append(spec)
    return alternates


def _review_decision_changes(
    session_state: SessionState,
    decision: AgentDecision,
    dependency_analysis: Dict[str, Any],
) -> tuple[list[Dict[str, Any]], list[ReviewedChange]]:
    applied_changes: list[Dict[str, Any]] = []
    deferred_changes: list[ReviewedChange] = []
    accepted = 0
    overridden = 0

    if not decision.changes:
        return applied_changes, deferred_changes

    for index, change in enumerate(decision.changes, start=1):
        alternates = _alternates_for_change(change.to_dict(), dependency_analysis)
        if change.requires_user_review and session_state.mode != "auto":
            render.show_change_review(change, index, len(decision.changes), alternates)
        resolution = prompts.prompt_change_resolution(
            change,
            alternates,
            session_state.mode if change.requires_user_review else "auto",
        )

        reviewed = ReviewedChange(
            package=change.package,
            manager=change.manager,
            current_value=change.current_value,
            selected_value=resolution.get("selected_value"),
            proposed_value=change.proposed_value,
            action=str(resolution.get("action", change.action)),
            resolution=str(resolution.get("resolution", "accepted")),
            reason=change.reason,
            confidence=change.confidence,
            sources=list(change.sources),
        )
        session_state.reviewed_changes.append(reviewed)

        if reviewed.resolution == "deferred":
            deferred_changes.append(reviewed)
            continue

        if reviewed.resolution in {"alternate", "custom", "rejected"}:
            overridden += 1
            if reviewed.selected_value:
                session_state.user_overrides.append(
                    UserOverride(
                        package=reviewed.package,
                        manager=reviewed.manager,
                        selected_value=reviewed.selected_value,
                        action=reviewed.action,
                        reason=reviewed.reason,
                        sources=reviewed.sources,
                    )
                )
        else:
            accepted += 1

        if reviewed.selected_value is None:
            continue

        updated = change.to_dict()
        updated["proposed_value"] = reviewed.selected_value
        updated["action"] = reviewed.action
        updated["review_resolution"] = reviewed.resolution
        updated["requires_user_review"] = False
        applied_changes.append(updated)

    render.show_review_summary(
        total=len(decision.changes),
        accepted=accepted,
        overridden=overridden,
        deferred=len(deferred_changes),
    )
    return applied_changes, deferred_changes


def _assign_run_artifacts(session_state: SessionState, run_id: str) -> None:
    run_artifact_dir = artifacts_dir() / run_id
    session_state.run_artifacts.run_id = run_id
    session_state.run_artifacts.artifact_dir = str(run_artifact_dir)
    session_state.run_artifacts.environment_yml = str(run_artifact_dir / "environment.generated.yml")
    session_state.run_artifacts.manual_setup_md = str(run_artifact_dir / "manual-setup.md")
    session_state.run_artifacts.manual_setup_json = str(run_artifact_dir / "manual-setup.json")
    session_state.run_artifacts.report_json = str(run_artifact_dir / "report.json")


def _write_report(
    workspace: Path,
    session_state: SessionState,
    result: Dict[str, Any],
    run_id: str,
    timestamp: str,
) -> str:
    report_target = session_state.run_artifacts.report_json
    if not report_target:
        raise RuntimeError("Run artifact report path is not initialized.")
    path = Path(report_target)
    path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "run_id": run_id,
        "timestamp": timestamp,
        "session": _sanitize_session(session_state),
        "history": _trim_history(session_state.history),
        "result": _trim_result(result),
    }
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    session_state.run_artifacts.report_json = str(path)
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


def _finalize_failure(
    workspace: Path,
    session_state: SessionState,
    stage: str,
    message: str,
    run_id: str,
    timestamp: str,
    logs: list[str] | None = None,
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    failure = {
        "error_type": stage,
        "message": message,
        "logs": logs or [],
    }
    _render_failure(failure)
    return _finalize(
        workspace,
        session_state,
        {"success": False, "stage": stage, "failure": failure, **(extra or {})},
        run_id,
        timestamp,
    )


def run_supervisor(session_state: SessionState, max_attempts: int = 3) -> Dict[str, Any]:
    console.print(Panel("Starting supervisor run...", title="RepoResolve"))

    workspace = workspace_dir()
    console.print(f"Workspace: {workspace}")
    run_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()
    _assign_run_artifacts(session_state, run_id)
    provider = _select_provider(session_state)

    try:
        provider.validate_configuration()
    except ProviderError as exc:
        return _finalize_failure(
            workspace,
            session_state,
            "provider",
            str(exc),
            run_id,
            timestamp,
        )

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

    planner = AgentPlanner(provider)

    try:
        with console.status("Selecting dependency files..."):
            selection = planner.select_dependency_files(inspect_result.data)
    except (ProviderError, AgentPlannerError) as exc:
        return _finalize_failure(
            workspace,
            session_state,
            "dependency_selection",
            str(exc),
            run_id,
            timestamp,
        )
    allowed_candidates = set()
    for repo in inspect_result.data.get("repos", []):
        for candidate in repo.get("candidates", []):
            allowed_candidates.add(candidate)
    if allowed_candidates:
        selection.selected_files = [
            path for path in selection.selected_files if path in allowed_candidates
        ]
    session_state.manifest_selection = ManifestSelectionState(
        selected_files=list(selection.selected_files),
        reason=selection.reason,
        confidence=selection.confidence,
    )
    _render_selection(selection)

    with console.status("Parsing dependencies..."):
        parse_result = parse_dependencies(inspect_result.data, selection.selected_files)
    console.print(
        "[green]Parsing complete.[/green]"
        if parse_result.success
        else "[red]Parsing failed.[/red]"
    )
    dependency_analysis = parse_result.data
    _render_dependency_summary(dependency_analysis)
    if not parse_result.success:
        failure = summarize_failure("parse_dependencies", parse_result)
        _render_failure(failure)
        return _finalize(
            workspace,
            session_state,
            {
                "success": False,
                "stage": "parse",
                "failure": failure,
                "dependency_analysis": dependency_analysis,
            },
            run_id,
            timestamp,
        )

    try:
        decision = planner.plan_initial_environment(parse_result.data)
    except (ProviderError, AgentPlannerError) as exc:
        return _finalize_failure(
            workspace,
            session_state,
            "plan_initial_environment",
            str(exc),
            run_id,
            timestamp,
        )
    _render_decision(decision, "Agent Decision (initial)")

    try:
        reviewed_changes, deferred_changes = _review_decision_changes(
            session_state,
            decision,
            dependency_analysis,
        )
    except KeyboardInterrupt:
        return _finalize_failure(
            workspace,
            session_state,
            "review",
            "Guided review aborted by user.",
            run_id,
            timestamp,
            extra={"dependency_analysis": dependency_analysis},
        )
    if deferred_changes:
        return _finalize_failure(
            workspace,
            session_state,
            "review",
            "One or more dependency changes were deferred and the environment remains blocked.",
            run_id,
            timestamp,
            logs=[f"{item.package} ({item.manager}) deferred." for item in deferred_changes],
            extra={
                "dependency_analysis": dependency_analysis,
                "deferred_changes": [asdict(item) for item in deferred_changes],
            },
        )

    with console.status("Generating run artifacts..."):
        generated = write_run_artifacts(session_state, inspect_result.data, dependency_analysis)
    _render_generated_artifacts(generated)

    environment_spec = generated.get("environment_spec", {})
    unresolved_conflicts = []
    if isinstance(environment_spec, dict):
        unresolved_conflicts = environment_spec.get("unresolved_conflicts", [])
    blocked = bool(unresolved_conflicts)

    final = {
        "success": not blocked,
        "stage": "generated",
        "dependency_analysis": dependency_analysis,
        "decision": decision.to_dict(),
        "artifacts": {
            "artifact_dir": generated.get("artifact_dir"),
            "environment_yml": generated.get("environment_yml"),
            "manual_setup_md": generated.get("manual_setup_md"),
            "manual_setup_json": generated.get("manual_setup_json"),
        },
        "manual_setup_summary": {
            "setup_clues": len(generated.get("manual_setup", {}).get("setup_clues", []))
            if isinstance(generated.get("manual_setup"), dict)
            else 0,
            "manual_items": len(generated.get("manual_setup", {}).get("manual_items", []))
            if isinstance(generated.get("manual_setup"), dict)
            else 0,
        },
        "environment_spec": environment_spec,
    }
    if blocked:
        final["failure"] = {
            "error_type": "generation",
            "message": "Generated artifacts contain unresolved dependency conflicts.",
            "logs": [
                f"{item.get('package', 'unknown')} ({item.get('manager', 'unknown')}) unresolved."
                for item in unresolved_conflicts
                if isinstance(item, dict)
            ],
        }
        console.print(Panel("Artifacts generated, but unresolved conflicts remain.", title="Blocked", style="yellow"))
        console.print(
            Panel(
                "Status: blocked\nArtifacts: generated",
                title="Summary",
                style="yellow",
            )
        )
    else:
        console.print(Panel("Artifacts generated successfully.", title="Success", style="green"))
        console.print(
            Panel(
                "Status: generated\nArtifacts: environment.generated.yml, manual-setup.md, manual-setup.json",
                title="Summary",
                style="green",
            )
        )
    return _finalize(workspace, session_state, final, run_id, timestamp)
