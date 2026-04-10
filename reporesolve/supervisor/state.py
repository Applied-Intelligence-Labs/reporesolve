from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


@dataclass
class ManifestSelectionState:
    selected_files: List[str] = field(default_factory=list)
    reason: str = ""
    confidence: float = 0.0


@dataclass
class UserOverride:
    package: str
    manager: str
    selected_value: str
    action: str
    reason: str = ""
    sources: List[str] = field(default_factory=list)


@dataclass
class ReviewedChange:
    package: str
    manager: str
    current_value: Optional[str]
    selected_value: Optional[str]
    proposed_value: Optional[str]
    action: str
    resolution: str
    reason: str
    confidence: float
    sources: List[str] = field(default_factory=list)


@dataclass
class RunArtifacts:
    run_id: Optional[str] = None
    artifact_dir: Optional[str] = None
    environment_yml: Optional[str] = None
    manual_setup_md: Optional[str] = None
    manual_setup_json: Optional[str] = None
    report_json: Optional[str] = None


@dataclass
class SessionState:
    repos: List[str] = field(default_factory=list)
    main_repo: str = ""
    working_name: str = "working-repo"
    mode: Literal["guided", "auto", "review"] = "guided"
    provider: Literal["openai", "anthropic"] = "openai"
    model: str = ""
    api_key: Optional[str] = None
    manifest_selection: ManifestSelectionState = field(default_factory=ManifestSelectionState)
    user_overrides: List[UserOverride] = field(default_factory=list)
    reviewed_changes: List[ReviewedChange] = field(default_factory=list)
    run_artifacts: RunArtifacts = field(default_factory=RunArtifacts)
    history: List[Dict[str, Any]] = field(default_factory=list)
