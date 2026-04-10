"""Agent decision schema and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

ALLOWED_ACTIONS = {"revise_environment", "retry", "stop", "explain"}
ALLOWED_CHANGE_ACTIONS = {"add", "replace", "remove", "pin", "relax", "defer", "note"}
ALLOWED_MANAGERS = {"conda", "pip", "unknown"}


class DecisionError(ValueError):
    """Raised when an agent decision fails validation."""


@dataclass
class ProposedChange:
    package: str
    manager: str
    current_value: Optional[str]
    proposed_value: Optional[str]
    action: str
    reason: str
    confidence: float
    sources: List[str] = field(default_factory=list)
    requires_user_review: bool = True

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ProposedChange":
        if not isinstance(payload, dict):
            raise DecisionError("Each change must be an object.")

        package = payload.get("package")
        manager = payload.get("manager", "unknown")
        current_value = payload.get("current_value")
        proposed_value = payload.get("proposed_value")
        action = payload.get("action")
        reason = payload.get("reason")
        confidence = payload.get("confidence", 0.0)
        sources = payload.get("sources", [])
        requires_user_review = payload.get("requires_user_review", True)

        if not isinstance(package, str) or not package.strip():
            raise DecisionError("Change must include a non-empty package.")
        if manager not in ALLOWED_MANAGERS:
            raise DecisionError(f"Invalid manager: {manager}")
        if current_value is not None and not isinstance(current_value, str):
            raise DecisionError("current_value must be a string or null.")
        if proposed_value is not None and not isinstance(proposed_value, str):
            raise DecisionError("proposed_value must be a string or null.")
        if action not in ALLOWED_CHANGE_ACTIONS:
            raise DecisionError(f"Invalid change action: {action}")
        if not isinstance(reason, str) or not reason.strip():
            raise DecisionError("Change must include a non-empty reason.")
        if not isinstance(confidence, (int, float)):
            raise DecisionError("Change confidence must be a number.")
        confidence_value = float(confidence)
        if confidence_value < 0.0 or confidence_value > 1.0:
            raise DecisionError("Change confidence must be between 0 and 1.")
        if not isinstance(sources, list) or not all(isinstance(item, str) for item in sources):
            raise DecisionError("Change sources must be a list of strings.")
        if not isinstance(requires_user_review, bool):
            raise DecisionError("requires_user_review must be a boolean.")

        return cls(
            package=package.strip(),
            manager=manager,
            current_value=current_value.strip() if isinstance(current_value, str) else None,
            proposed_value=proposed_value.strip() if isinstance(proposed_value, str) else None,
            action=action,
            reason=reason.strip(),
            confidence=confidence_value,
            sources=sources,
            requires_user_review=requires_user_review,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package": self.package,
            "manager": self.manager,
            "current_value": self.current_value,
            "proposed_value": self.proposed_value,
            "action": self.action,
            "reason": self.reason,
            "confidence": self.confidence,
            "sources": self.sources,
            "requires_user_review": self.requires_user_review,
        }


@dataclass
class AgentDecision:
    action: str
    reason: str
    changes: List[ProposedChange] = field(default_factory=list)
    retry: bool = False
    confidence: float = 0.0

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AgentDecision":
        if not isinstance(payload, dict):
            raise DecisionError("Decision payload must be an object.")

        action = payload.get("action")
        reason = payload.get("reason")
        changes = payload.get("changes", [])
        retry = payload.get("retry", False)
        confidence = payload.get("confidence", 0.0)

        if action not in ALLOWED_ACTIONS:
            raise DecisionError(f"Invalid action: {action}")
        if not isinstance(reason, str) or not reason.strip():
            raise DecisionError("Decision must include a non-empty reason.")
        if not isinstance(changes, list):
            raise DecisionError("Changes must be a list.")
        if not isinstance(retry, bool):
            raise DecisionError("Retry must be a boolean.")
        if not isinstance(confidence, (int, float)):
            raise DecisionError("Confidence must be a number.")

        confidence_value = float(confidence)
        if confidence_value < 0.0 or confidence_value > 1.0:
            raise DecisionError("Confidence must be between 0 and 1.")

        parsed_changes = [ProposedChange.from_dict(item) for item in changes]

        return cls(
            action=action,
            reason=reason.strip(),
            changes=parsed_changes,
            retry=retry,
            confidence=confidence_value,
        )

    @classmethod
    def from_json(cls, raw: str) -> "AgentDecision":
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DecisionError(f"Invalid JSON output: {exc}") from exc
        return cls.from_dict(payload)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "changes": [change.to_dict() for change in self.changes],
            "retry": self.retry,
            "confidence": self.confidence,
        }
@dataclass
class DependencySelection:
    selected_files: List[str]
    reason: str
    confidence: float = 0.0

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "DependencySelection":
        if not isinstance(payload, dict):
            raise DecisionError("Selection payload must be an object.")

        selected_files = payload.get("selected_files", [])
        reason = payload.get("reason")
        confidence = payload.get("confidence", 0.0)

        if not isinstance(selected_files, list) or not all(
            isinstance(item, str) for item in selected_files
        ):
            raise DecisionError("selected_files must be a list of strings.")
        if not isinstance(reason, str) or not reason.strip():
            raise DecisionError("Selection must include a non-empty reason.")
        if not isinstance(confidence, (int, float)):
            raise DecisionError("Confidence must be a number.")

        confidence_value = float(confidence)
        if confidence_value < 0.0 or confidence_value > 1.0:
            raise DecisionError("Confidence must be between 0 and 1.")

        return cls(
            selected_files=selected_files,
            reason=reason.strip(),
            confidence=confidence_value,
        )

    @classmethod
    def from_json(cls, raw: str) -> "DependencySelection":
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DecisionError(f"Invalid JSON output: {exc}") from exc
        return cls.from_dict(payload)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selected_files": self.selected_files,
            "reason": self.reason,
            "confidence": self.confidence,
        }
