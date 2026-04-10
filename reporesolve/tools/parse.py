from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .base import ToolResult

_PIP_NAME_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)")
_PIP_PIN_RE = re.compile(r"^\s*[A-Za-z0-9_.-]+(?:\[[^\]]+\])?\s*===?\s*([^\s;]+)\s*$")
_CONDA_PIN_RE = re.compile(
    r"^\s*(?:[A-Za-z0-9_.-]+::)?([A-Za-z0-9_.-]+)\s*=\s*([^=<>!\s]+(?:=[^=<>!\s]+)?)\s*$"
)


def _classify_manifest(path: Path) -> Tuple[str, bool]:
    name = path.name.lower()
    if name.startswith("requirements") and name.endswith(".txt"):
        return "requirements_txt", True
    if name in {"environment.yml", "environment.yaml"}:
        return "environment_yml", True
    if name.endswith((".yml", ".yaml")) and any(
        token in name for token in ("env", "conda", "environment", "requirements", "deps")
    ):
        return "environment_like_yaml", True
    if name.startswith("requirements") and name.endswith(".in"):
        return "requirements_in", False
    if name == "pyproject.toml":
        return "pyproject_toml", False
    if name == "setup.py":
        return "setup_py", False
    if name == "setup.cfg":
        return "setup_cfg", False
    if name == "pipfile":
        return "pipfile", False
    if name == "pipfile.lock":
        return "pipfile_lock", False
    if name == "poetry.lock":
        return "poetry_lock", False
    if name == "uv.lock":
        return "uv_lock", False
    if name.endswith(".txt") and any(
        token in name for token in ("requirements", "deps", "dependency")
    ):
        return "dependency_txt", False
    return "unknown", False


def _normalize_package_name(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def _extract_package_name(spec: str, manager: str) -> Optional[str]:
    raw = spec.strip()
    if not raw:
        return None

    if manager == "conda":
        raw = raw.split("::", 1)[-1]
        for operator in ("<=", ">=", "==", "!=", "~=", "=", "<", ">", " "):
            if operator in raw:
                raw = raw.split(operator, 1)[0]
                break
        raw = raw.strip()
        return raw or None

    match = _PIP_NAME_RE.match(raw)
    if not match:
        return None
    return match.group(1)


def _exact_pin(spec: str, manager: str) -> Optional[str]:
    if manager == "pip":
        match = _PIP_PIN_RE.match(spec)
        if match:
            return match.group(1)
        return None

    match = _CONDA_PIN_RE.match(spec)
    if match:
        return match.group(2)
    return None


def _make_dependency_record(
    *,
    repo_path: str,
    manifest_path: Path,
    manifest_type: str,
    manager: str,
    spec: str,
    line_number: int,
    raw_spec: str,
) -> Optional[Dict[str, Any]]:
    package = _extract_package_name(spec, manager)
    if not package:
        return None

    return {
        "package": package,
        "normalized_name": _normalize_package_name(package),
        "manager": manager,
        "spec": spec,
        "raw_spec": raw_spec,
        "repo_path": repo_path,
        "manifest_path": str(manifest_path),
        "manifest_type": manifest_type,
        "source_file": manifest_path.name,
        "line_number": line_number,
    }


def _parse_requirements_file(
    path: Path,
    repo_path: str,
    manifest_type: str,
    logs: List[str],
    unsupported_entries: List[Dict[str, Any]],
    visited: Set[str],
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    resolved = str(path.resolve())
    if resolved in visited:
        logs.append(f"Skipped already visited requirements file: {path}")
        return records
    visited.add(resolved)

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        content = re.split(r"\s+#", stripped, maxsplit=1)[0].strip()
        lowered = content.lower()

        if lowered.startswith(("-r ", "--requirement ")):
            target = content.split(maxsplit=1)[1].strip()
            target_path = (path.parent / target).resolve()
            if target_path.exists():
                records.extend(
                    _parse_requirements_file(
                        target_path,
                        repo_path,
                        "requirements_txt",
                        logs,
                        unsupported_entries,
                        visited,
                    )
                )
            else:
                unsupported_entries.append(
                    {
                        "repo_path": repo_path,
                        "manifest_path": str(path),
                        "manifest_type": manifest_type,
                        "line_number": line_number,
                        "entry": content,
                        "reason": f"Included requirements file not found: {target}",
                    }
                )
            continue

        if lowered.startswith(("-c ", "--constraint ")):
            target = content.split(maxsplit=1)[1].strip()
            target_path = (path.parent / target).resolve()
            if target_path.exists():
                records.extend(
                    _parse_requirements_file(
                        target_path,
                        repo_path,
                        "requirements_txt",
                        logs,
                        unsupported_entries,
                        visited,
                    )
                )
            else:
                unsupported_entries.append(
                    {
                        "repo_path": repo_path,
                        "manifest_path": str(path),
                        "manifest_type": manifest_type,
                        "line_number": line_number,
                        "entry": content,
                        "reason": f"Constraint file not found: {target}",
                    }
                )
            continue

        if content.startswith(("-", "git+", "http://", "https://", "svn+", "hg+", "bzr+")):
            unsupported_entries.append(
                {
                    "repo_path": repo_path,
                    "manifest_path": str(path),
                    "manifest_type": manifest_type,
                    "line_number": line_number,
                    "entry": content,
                    "reason": "Unsupported non-package requirements entry in v0.",
                }
            )
            continue

        record = _make_dependency_record(
            repo_path=repo_path,
            manifest_path=path,
            manifest_type=manifest_type,
            manager="pip",
            spec=content,
            line_number=line_number,
            raw_spec=stripped,
        )
        if record is None:
            unsupported_entries.append(
                {
                    "repo_path": repo_path,
                    "manifest_path": str(path),
                    "manifest_type": manifest_type,
                    "line_number": line_number,
                    "entry": content,
                    "reason": "Could not determine package name from requirements entry.",
                }
            )
            continue
        records.append(record)

    return records


def _parse_environment_file(
    path: Path,
    repo_path: str,
    manifest_type: str,
    unsupported_entries: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    records: List[Dict[str, Any]] = []
    channels: List[str] = []
    in_deps = False
    deps_indent: Optional[int] = None
    in_pip = False
    pip_indent: Optional[int] = None
    in_channels = False
    channels_indent: Optional[int] = None

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        raw = line.rstrip()
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue

        indent = len(raw) - len(raw.lstrip())
        stripped = raw.strip()

        if stripped == "channels:":
            in_channels = True
            channels_indent = indent
            in_deps = False
            in_pip = False
            continue

        if in_channels:
            if channels_indent is not None and indent <= channels_indent and not stripped.startswith("-"):
                in_channels = False
            elif stripped.startswith("-"):
                channels.append(stripped[1:].strip())
                continue

        if stripped == "dependencies:":
            in_deps = True
            deps_indent = indent
            in_pip = False
            continue

        if not in_deps:
            continue

        if deps_indent is not None and indent <= deps_indent and not stripped.startswith("-"):
            in_deps = False
            in_pip = False
            continue

        if stripped.startswith("- pip:"):
            in_pip = True
            pip_indent = indent
            continue

        if in_pip and pip_indent is not None and indent <= pip_indent:
            in_pip = False
            pip_indent = None

        if not stripped.startswith("-"):
            continue

        spec = stripped[1:].strip()
        manager = "pip" if in_pip else "conda"
        record = _make_dependency_record(
            repo_path=repo_path,
            manifest_path=path,
            manifest_type=manifest_type,
            manager=manager,
            spec=spec,
            line_number=line_number,
            raw_spec=stripped,
        )
        if record is None:
            unsupported_entries.append(
                {
                    "repo_path": repo_path,
                    "manifest_path": str(path),
                    "manifest_type": manifest_type,
                    "line_number": line_number,
                    "entry": spec,
                    "reason": "Could not determine package name from environment entry.",
                }
            )
            continue
        records.append(record)

    return records, channels


def _summarize_dependencies(parsed: List[Dict[str, object]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for repo in parsed:
        repo_dependencies = repo.get("dependencies", [])
        if not isinstance(repo_dependencies, list):
            continue
        for dependency in repo_dependencies:
            if not isinstance(dependency, dict):
                continue
            key = (
                str(dependency.get("manager", "unknown")),
                str(dependency.get("normalized_name", "")),
            )
            grouped.setdefault(key, []).append(dependency)

    normalized: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []

    for (manager, normalized_name), items in sorted(grouped.items()):
        package = str(items[0].get("package", normalized_name))
        specs: Dict[str, List[Dict[str, Any]]] = {}
        for item in items:
            spec = str(item.get("spec", ""))
            specs.setdefault(spec, []).append(item)

        summary = {
            "package": package,
            "normalized_name": normalized_name,
            "manager": manager,
            "specs": [
                {
                    "spec": spec,
                    "sources": [
                        {
                            "repo_path": source.get("repo_path"),
                            "manifest_path": source.get("manifest_path"),
                            "line_number": source.get("line_number"),
                        }
                        for source in sources
                    ],
                }
                for spec, sources in sorted(specs.items())
            ],
            "source_count": len(items),
        }
        normalized.append(summary)

        if len(specs) <= 1:
            continue

        exact_pins = {
            pin
            for spec in specs
            if (pin := _exact_pin(spec, manager)) is not None
        }
        if len(exact_pins) > 1:
            conflict_type = "direct_conflict"
            message = "Multiple incompatible exact pins were detected."
        else:
            conflict_type = "review_required"
            message = "Multiple distinct dependency specs were detected and need review."

        conflicts.append(
            {
                "package": package,
                "normalized_name": normalized_name,
                "manager": manager,
                "conflict_type": conflict_type,
                "message": message,
                "specs": summary["specs"],
            }
        )

    return normalized, conflicts


def _candidate_details_for_repo(repo: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidate_details = repo.get("candidate_details", [])
    if isinstance(candidate_details, list):
        normalized: List[Dict[str, Any]] = []
        for item in candidate_details:
            if isinstance(item, dict) and isinstance(item.get("path"), str):
                normalized.append(item)
        return normalized

    candidates = repo.get("candidates", [])
    if not isinstance(candidates, list):
        return []
    details: List[Dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        manifest_type, supported = _classify_manifest(Path(candidate))
        details.append(
            {
                "path": candidate,
                "manifest_type": manifest_type,
                "supported": supported,
            }
        )
    return details


def parse_dependencies(
    repo_metadata: Dict[str, Any],
    selected_files: Optional[List[str]] = None,
) -> ToolResult:
    logs: List[str] = []
    errors: List[str] = []
    parsed: List[Dict[str, object]] = []
    manifests: List[Dict[str, Any]] = []
    unsupported_manifests: List[Dict[str, Any]] = []
    unsupported_entries: List[Dict[str, Any]] = []

    repos = repo_metadata.get("repos", [])
    if not isinstance(repos, list):
        return ToolResult(
            name="parse_dependencies",
            success=False,
            logs=logs,
            errors=["Invalid repo metadata: expected list under 'repos'."],
            data={
                "dependencies": [],
                "selected_files": [],
                "manifests": [],
                "unsupported_manifests": [],
                "unsupported_entries": [],
                "normalized_dependencies": [],
                "conflicts": [],
            },
        )

    selected_set = set(selected_files or [])

    for repo in repos:
        if not isinstance(repo, dict):
            errors.append("Invalid repo entry; expected dict.")
            continue

        repo_path = repo.get("path")
        if not repo_path:
            errors.append("Repo entry missing 'path'.")
            continue

        repo_root = Path(str(repo_path))
        candidate_details = _candidate_details_for_repo(repo)
        selected_repo_details = [
            item
            for item in candidate_details
            if isinstance(item.get("path"), str) and item["path"] in selected_set
        ]
        repo_details = selected_repo_details or [
            item for item in candidate_details if bool(item.get("supported"))
        ]

        repo_dependencies: List[Dict[str, Any]] = []
        parsed_manifest_count = 0

        try:
            for detail in repo_details:
                manifest_path_raw = detail.get("path")
                manifest_type = str(detail.get("manifest_type", "unknown"))
                supported = bool(detail.get("supported"))
                if not isinstance(manifest_path_raw, str):
                    continue

                manifest_path = Path(manifest_path_raw)
                if not manifest_path.exists():
                    continue

                manifest_record = {
                    "repo_path": str(repo_root),
                    "path": str(manifest_path),
                    "manifest_type": manifest_type,
                    "supported": supported,
                    "selected": manifest_path_raw in selected_set,
                    "status": "unsupported",
                }

                if not supported:
                    unsupported_manifests.append(
                        {
                            "repo_path": str(repo_root),
                            "path": str(manifest_path),
                            "manifest_type": manifest_type,
                            "reason": "Detected manifest type is not supported in v0 parsing.",
                        }
                    )
                    manifests.append(manifest_record)
                    continue

                if manifest_type == "requirements_txt":
                    dependencies = _parse_requirements_file(
                        manifest_path,
                        str(repo_root),
                        manifest_type,
                        logs,
                        unsupported_entries,
                        visited=set(),
                    )
                    repo_dependencies.extend(dependencies)
                    parsed_manifest_count += 1
                    manifest_record["status"] = "parsed"
                    manifests.append(manifest_record)
                    continue

                if manifest_type in {"environment_yml", "environment_like_yaml"}:
                    dependencies, channels = _parse_environment_file(
                        manifest_path,
                        str(repo_root),
                        manifest_type,
                        unsupported_entries,
                    )
                    repo_dependencies.extend(dependencies)
                    parsed_manifest_count += 1
                    manifest_record["status"] = "parsed"
                    manifest_record["channels"] = channels
                    manifests.append(manifest_record)
                    continue

                unsupported_manifests.append(
                    {
                        "repo_path": str(repo_root),
                        "path": str(manifest_path),
                        "manifest_type": manifest_type,
                        "reason": "Detected manifest type is not supported in v0 parsing.",
                    }
                )
                manifests.append(manifest_record)

            if parsed_manifest_count == 0:
                if selected_repo_details:
                    selected_paths = [
                        str(item.get("path"))
                        for item in selected_repo_details
                        if isinstance(item.get("path"), str)
                    ]
                    errors.append(
                        "No supported manifests could be parsed for "
                        f"{repo_root}. Selected files: {', '.join(selected_paths)}"
                    )
                elif candidate_details:
                    errors.append(
                        "No supported manifests could be parsed for "
                        f"{repo_root}. Detected manifests are unsupported in v0."
                    )
                else:
                    errors.append(f"No dependency manifests were detected for {repo_root}.")
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(f"Failed parsing dependencies for {repo_root}: {exc}")

        parsed.append(
            {
                "path": str(repo_root),
                "dependencies": repo_dependencies,
            }
        )

    normalized_dependencies, conflicts = _summarize_dependencies(parsed)

    for unsupported in unsupported_manifests:
        logs.append(
            f"{unsupported['path']}: {unsupported['manifest_type']} detected but unsupported in v0."
        )
    for conflict in conflicts:
        logs.append(
            f"{conflict['package']} ({conflict['manager']}): {conflict['conflict_type']} detected."
        )

    return ToolResult(
        name="parse_dependencies",
        success=len(errors) == 0,
        logs=logs,
        errors=errors,
        data={
            "dependencies": parsed,
            "selected_files": list(selected_set),
            "manifests": manifests,
            "unsupported_manifests": unsupported_manifests,
            "unsupported_entries": unsupported_entries,
            "normalized_dependencies": normalized_dependencies,
            "conflicts": conflicts,
        },
    )
