"""Agent planner for structured decision making."""

from __future__ import annotations

import json
from typing import Any, Dict

from .schema import AgentDecision, DecisionError, fallback_decision
from ..providers.base import BaseProvider


_PROMPT_HEADER = (
    "You are RepoResolve Agent. You must output STRICT JSON only. "
    "No markdown, no commentary."
)

_PROMPT_SCHEMA = {
    "action": "revise_environment | retry | stop | explain",
    "reason": "string",
    "changes": "list",
    "retry": "bool",
    "confidence": "float between 0 and 1",
}


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

    def _request_decision(self, prompt: str, context: Dict[str, Any]) -> AgentDecision:
        try:
            raw = self._provider.generate_decision(prompt, context)
            return AgentDecision.from_json(raw)
        except DecisionError as exc:
            return fallback_decision(f"Invalid agent output: {exc}")
        except Exception as exc:  # pragma: no cover - defensive
            return fallback_decision(f"Provider error: {exc}")
