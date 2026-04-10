"""Supervisor workflow helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .state import SessionState
from ..tools.base import ToolResult


def summarize_failure(tool_name: str, tool_result: ToolResult) -> Dict[str, Any]:
    errors = tool_result.errors or []
    logs = tool_result.logs or []
    message = errors[0] if errors else "Unknown failure."

    return {
        "error_type": tool_name,
        "message": message,
        "logs": logs,
    }


def _normalize_name(value: str) -> str:
    return value.strip().lower().replace("_", "-")


def _unique_preserve(values: List[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def build_environment_spec(
    session_state: SessionState,
    dependency_analysis: Dict[str, Any],
) -> Dict[str, Any]:
    manifests = dependency_analysis.get("manifests", [])
    normalized_dependencies = dependency_analysis.get("normalized_dependencies", [])

    channels: List[str] = []
    for manifest in manifests if isinstance(manifests, list) else []:
        if not isinstance(manifest, dict):
            continue
        manifest_channels = manifest.get("channels", [])
        if isinstance(manifest_channels, list):
            for channel in manifest_channels:
                if isinstance(channel, str) and channel.strip():
                    channels.append(channel.strip())

    resolution_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for reviewed in session_state.reviewed_changes:
        resolution_map[(_normalize_name(reviewed.manager), _normalize_name(reviewed.package))] = {
            "selected_value": reviewed.selected_value,
            "resolution": reviewed.resolution,
            "action": reviewed.action,
            "reason": reviewed.reason,
            "sources": list(reviewed.sources),
        }

    conda_specs: List[str] = []
    pip_specs: List[str] = []
    resolved_packages: List[Dict[str, Any]] = []
    unresolved_conflicts: List[Dict[str, Any]] = []

    for dependency in normalized_dependencies if isinstance(normalized_dependencies, list) else []:
        if not isinstance(dependency, dict):
            continue

        manager = str(dependency.get("manager", "unknown"))
        normalized_name = str(dependency.get("normalized_name", ""))
        specs = dependency.get("specs", [])
        if not isinstance(specs, list):
            continue

        resolution = resolution_map.get((_normalize_name(manager), normalized_name))
        selected_spec: Optional[str] = None

        if resolution:
            selected_spec = resolution.get("selected_value")
        elif len(specs) == 1 and isinstance(specs[0], dict):
            selected_spec = specs[0].get("spec")

        if not isinstance(selected_spec, str) or not selected_spec.strip():
            unresolved_conflicts.append(
                {
                    "package": dependency.get("package"),
                    "normalized_name": normalized_name,
                    "manager": manager,
                    "reason": "No reviewed resolution exists for this dependency.",
                    "specs": specs,
                }
            )
            continue

        selected_spec = selected_spec.strip()
        if manager == "conda":
            conda_specs.append(selected_spec)
        elif manager == "pip":
            pip_specs.append(selected_spec)
        else:
            unresolved_conflicts.append(
                {
                    "package": dependency.get("package"),
                    "normalized_name": normalized_name,
                    "manager": manager,
                    "reason": "Unsupported package manager in generated environment.",
                    "specs": specs,
                }
            )
            continue

        resolved_packages.append(
            {
                "package": dependency.get("package"),
                "normalized_name": normalized_name,
                "manager": manager,
                "selected_spec": selected_spec,
                "source_count": dependency.get("source_count", 0),
            }
        )

    conda_specs = _unique_preserve(conda_specs)
    pip_specs = _unique_preserve(pip_specs)

    if pip_specs and not any(_normalize_name(spec.split("=", 1)[0]) == "pip" for spec in conda_specs):
        conda_specs.append("pip")

    return {
        "name": session_state.working_name or "working-repo",
        "channels": _unique_preserve(channels),
        "conda_dependencies": conda_specs,
        "pip_dependencies": pip_specs,
        "resolved_packages": resolved_packages,
        "unresolved_conflicts": unresolved_conflicts,
    }


def render_environment_yaml(environment_spec: Dict[str, Any]) -> str:
    lines: List[str] = [f"name: {environment_spec['name']}"]
    channels = environment_spec.get("channels", [])
    if isinstance(channels, list) and channels:
        lines.append("channels:")
        for channel in channels:
            lines.append(f"  - {channel}")

    lines.append("dependencies:")
    conda_dependencies = environment_spec.get("conda_dependencies", [])
    for dependency in conda_dependencies if isinstance(conda_dependencies, list) else []:
        lines.append(f"  - {dependency}")

    pip_dependencies = environment_spec.get("pip_dependencies", [])
    if isinstance(pip_dependencies, list) and pip_dependencies:
        lines.append("  - pip:")
        for dependency in pip_dependencies:
            lines.append(f"      - {dependency}")

    return "\n".join(lines) + "\n"


def build_manual_setup_data(
    session_state: SessionState,
    inspection_data: Dict[str, Any],
    dependency_analysis: Dict[str, Any],
    environment_spec: Dict[str, Any],
) -> Dict[str, Any]:
    unsupported_manifests = dependency_analysis.get("unsupported_manifests", [])
    unsupported_entries = dependency_analysis.get("unsupported_entries", [])
    unresolved_conflicts = environment_spec.get("unresolved_conflicts", [])
    setup_clues: List[Dict[str, Any]] = []

    inspection_repos = inspection_data.get("repos", [])
    if isinstance(inspection_repos, list):
        for repo in inspection_repos:
            if not isinstance(repo, dict):
                continue
            repo_clues = repo.get("setup_clues", [])
            if isinstance(repo_clues, list):
                for clue in repo_clues:
                    if isinstance(clue, dict):
                        setup_clues.append(clue)

    manual_items: List[Dict[str, Any]] = []
    for item in setup_clues:
        manual_items.append({"type": "setup_clue", **item})
    for item in unsupported_manifests if isinstance(unsupported_manifests, list) else []:
        if isinstance(item, dict):
            manual_items.append({"type": "unsupported_manifest", **item})
    for item in unsupported_entries if isinstance(unsupported_entries, list) else []:
        if isinstance(item, dict):
            manual_items.append({"type": "unsupported_entry", **item})
    for item in unresolved_conflicts if isinstance(unresolved_conflicts, list) else []:
        if isinstance(item, dict):
            manual_items.append({"type": "unresolved_conflict", **item})

    return {
        "run_id": session_state.run_artifacts.run_id,
        "repos": list(session_state.repos),
        "selected_manifests": list(session_state.manifest_selection.selected_files),
        "setup_clues": setup_clues,
        "unsupported_manifests": unsupported_manifests,
        "unsupported_entries": unsupported_entries,
        "unresolved_conflicts": unresolved_conflicts,
        "user_overrides": [
            {
                "package": item.package,
                "manager": item.manager,
                "selected_value": item.selected_value,
                "action": item.action,
                "reason": item.reason,
                "sources": list(item.sources),
            }
            for item in session_state.user_overrides
        ],
        "manual_items": manual_items,
    }


def render_manual_setup_markdown(
    session_state: SessionState,
    manual_setup_data: Dict[str, Any],
    environment_spec: Dict[str, Any],
) -> str:
    lines: List[str] = [
        "# Manual Setup",
        "",
        "This file lists items RepoResolve could not resolve automatically in the current run.",
        "",
        "## Run",
        "",
        f"- Run ID: `{session_state.run_artifacts.run_id}`",
        f"- Working environment: `{environment_spec['name']}`",
        "",
        "## Selected Manifests",
        "",
    ]

    selected_manifests = manual_setup_data.get("selected_manifests", [])
    if isinstance(selected_manifests, list) and selected_manifests:
        for path in selected_manifests:
            lines.append(f"- `{path}`")
    else:
        lines.append("- None recorded")

    setup_clues = manual_setup_data.get("setup_clues", [])
    lines.extend(["", "## Detected Setup Clues", ""])
    if isinstance(setup_clues, list) and setup_clues:
        for item in setup_clues:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- `{item.get('relative_path', item.get('file_path', ''))}` line {item.get('line_number', '?')}: "
                f"{item.get('summary', '')}"
            )
            lines.append(
                f"  - platform: `{item.get('platform', 'any')}`, severity: `{item.get('severity', 'note')}`"
            )
            excerpt = str(item.get("excerpt", "")).strip()
            if excerpt:
                lines.append(f"  - evidence: `{excerpt}`")
    else:
        lines.append("- None")

    unsupported_manifests = manual_setup_data.get("unsupported_manifests", [])
    lines.extend(["", "## Unsupported Manifests", ""])
    if isinstance(unsupported_manifests, list) and unsupported_manifests:
        for item in unsupported_manifests:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- `{item.get('path', '')}`: {item.get('manifest_type', 'unknown')} - {item.get('reason', '')}"
            )
    else:
        lines.append("- None")

    unsupported_entries = manual_setup_data.get("unsupported_entries", [])
    lines.extend(["", "## Unsupported Entries", ""])
    if isinstance(unsupported_entries, list) and unsupported_entries:
        for item in unsupported_entries:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- `{item.get('manifest_path', '')}` line {item.get('line_number', '?')}: "
                f"`{item.get('entry', '')}` - {item.get('reason', '')}"
            )
    else:
        lines.append("- None")

    unresolved_conflicts = manual_setup_data.get("unresolved_conflicts", [])
    lines.extend(["", "## Unresolved Conflicts", ""])
    if isinstance(unresolved_conflicts, list) and unresolved_conflicts:
        for item in unresolved_conflicts:
            if not isinstance(item, dict):
                continue
            specs = item.get("specs", [])
            lines.append(
                f"- `{item.get('package', '')}` ({item.get('manager', '')}): {item.get('reason', '')}"
            )
            if isinstance(specs, list):
                for spec in specs:
                    if isinstance(spec, dict):
                        lines.append(f"  - `{spec.get('spec', '')}`")
    else:
        lines.append("- None")

    overrides = manual_setup_data.get("user_overrides", [])
    lines.extend(["", "## User Overrides", ""])
    if isinstance(overrides, list) and overrides:
        for item in overrides:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- `{item.get('package', '')}` ({item.get('manager', '')}) -> "
                f"`{item.get('selected_value', '')}`"
            )
    else:
        lines.append("- None")

    return "\n".join(lines) + "\n"


def write_run_artifacts(
    session_state: SessionState,
    inspection_data: Dict[str, Any],
    dependency_analysis: Dict[str, Any],
) -> Dict[str, Any]:
    artifact_dir_raw = session_state.run_artifacts.artifact_dir
    env_path_raw = session_state.run_artifacts.environment_yml
    manual_md_raw = session_state.run_artifacts.manual_setup_md
    manual_json_raw = session_state.run_artifacts.manual_setup_json

    if not artifact_dir_raw or not env_path_raw or not manual_md_raw or not manual_json_raw:
        raise RuntimeError("Run artifact paths are not initialized.")

    artifact_dir = Path(artifact_dir_raw)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    environment_spec = build_environment_spec(session_state, dependency_analysis)
    environment_yaml = render_environment_yaml(environment_spec)
    manual_setup_data = build_manual_setup_data(
        session_state,
        inspection_data,
        dependency_analysis,
        environment_spec,
    )
    manual_setup_md = render_manual_setup_markdown(
        session_state,
        manual_setup_data,
        environment_spec,
    )

    env_path = Path(env_path_raw)
    env_path.write_text(environment_yaml, encoding="utf-8")

    manual_md_path = Path(manual_md_raw)
    manual_md_path.write_text(manual_setup_md, encoding="utf-8")

    manual_json_path = Path(manual_json_raw)
    manual_json_path.write_text(json.dumps(manual_setup_data, indent=2), encoding="utf-8")

    return {
        "artifact_dir": str(artifact_dir),
        "environment_yml": str(env_path),
        "manual_setup_md": str(manual_md_path),
        "manual_setup_json": str(manual_json_path),
        "environment_spec": environment_spec,
        "manual_setup": manual_setup_data,
    }
