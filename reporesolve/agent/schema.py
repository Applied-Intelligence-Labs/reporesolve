"""Agent decision schema and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List

ALLOWED_ACTIONS = {"revise_environment", "retry", "stop", "explain"}


class DecisionError(ValueError):
    """Raised when an agent decision fails validation."""


@dataclass
class AgentDecision:
    action: str
    reason: str
    changes: List[Dict[str, Any]] = field(default_factory=list)
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

        return cls(
            action=action,
            reason=reason.strip(),
            changes=changes,
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
            "changes": self.changes,
            "retry": self.retry,
            "confidence": self.confidence,
        }


def fallback_decision(message: str) -> AgentDecision:
    return AgentDecision(
        action="explain",
        reason=message,
        changes=[],
        retry=False,
        confidence=0.0,
    )
