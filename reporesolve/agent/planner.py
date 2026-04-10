"""Agent planner for structured decision making."""

from __future__ import annotations

import json
from typing import Any, Dict

from .schema import (
    AgentDecision,
    DecisionError,
    DependencySelection,
)
from ..providers.base import BaseProvider


_PROMPT_HEADER = (
    "You are RepoResolve Agent. You must output STRICT JSON only. "
    "No markdown, no commentary."
)

_PROMPT_SCHEMA = {
    "action": "revise_environment | retry | stop | explain",
    "reason": "string",
    "changes": [
        {
            "package": "string",
            "manager": "conda | pip | unknown",
            "current_value": "string | null",
            "proposed_value": "string | null",
            "action": "add | replace | remove | pin | relax | defer | note",
            "reason": "string",
            "confidence": "float between 0 and 1",
            "sources": ["list of strings"],
            "requires_user_review": "bool",
        }
    ],
    "retry": "bool",
    "confidence": "float between 0 and 1",
}

_SELECTION_SCHEMA = {
    "selected_files": "list of strings",
    "reason": "string",
    "confidence": "float between 0 and 1",
}


class AgentPlannerError(RuntimeError):
    """Raised when agent output is invalid for the expected schema."""


class AgentPlanner:
    def __init__(self, provider: BaseProvider) -> None:
        self._provider = provider

    def plan_initial_environment(self, dependencies: Dict[str, Any]) -> AgentDecision:
        prompt = self._build_prompt(
            "Generate an initial environment proposal based on dependencies.",
            {"dependencies": dependencies},
        )
        return self._request_decision(prompt, {"stage": "initial", "dependencies": dependencies})

    def revise_environment(
        self, previous_attempt: Dict[str, Any], failure: Dict[str, Any]
    ) -> AgentDecision:
        prompt = self._build_prompt(
            "Revise the environment based on the failure summary.",
            {"previous_attempt": previous_attempt, "failure": failure},
        )
        return self._request_decision(
            prompt,
            {"stage": "revise", "previous_attempt": previous_attempt, "failure": failure},
        )

    def decide_next_action(self, state: Dict[str, Any]) -> AgentDecision:
        prompt = self._build_prompt(
            "Decide the next action based on current session state.",
            {"state": state},
        )
        return self._request_decision(prompt, {"stage": "decide", "state": state})

    def select_dependency_files(self, candidates: Dict[str, Any]) -> DependencySelection:
        prompt = self._build_selection_prompt(
            "Select the dependency files to use for environment planning.",
            {"candidates": candidates},
        )
        return self._request_selection(prompt, {"stage": "select", "candidates": candidates})

    def _build_prompt(self, instruction: str, payload: Dict[str, Any]) -> str:
        body = json.dumps(payload, indent=2)
        schema = json.dumps(_PROMPT_SCHEMA, indent=2)
        return "\n\n".join(
            [
                _PROMPT_HEADER,
                f"Instruction: {instruction}",
                "Return JSON matching this schema:",
                schema,
                "Context:",
                body,
            ]
        )

    def _build_selection_prompt(self, instruction: str, payload: Dict[str, Any]) -> str:
        body = json.dumps(payload, indent=2)
        schema = json.dumps(_SELECTION_SCHEMA, indent=2)
        return "\n\n".join(
            [
                _PROMPT_HEADER,
                f"Instruction: {instruction}",
                "Return JSON matching this schema:",
                schema,
                "Context:",
                body,
            ]
        )

    def _request_decision(self, prompt: str, context: Dict[str, Any]) -> AgentDecision:
        raw = self._provider.generate_decision(prompt, context)
        try:
            return AgentDecision.from_json(raw)
        except DecisionError as exc:
            raise AgentPlannerError(f"Invalid agent output: {exc}") from exc

    def _request_selection(self, prompt: str, context: Dict[str, Any]) -> DependencySelection:
        raw = self._provider.generate_decision(prompt, context)
        try:
            return DependencySelection.from_json(raw)
        except DecisionError as exc:
            raise AgentPlannerError(f"Invalid selection output: {exc}") from exc
