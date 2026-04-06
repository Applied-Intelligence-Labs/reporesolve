"""Anthropic provider implementation."""

from __future__ import annotations

import json
from typing import Any, Dict

from .base import BaseProvider


def _mock_decision(reason: str) -> str:
    return json.dumps(
        {
            "action": "explain",
            "reason": reason,
            "changes": [],
            "retry": False,
            "confidence": 0.0,
        }
    )


class AnthropicProvider(BaseProvider):
    def generate_decision(self, prompt: str, context: Dict[str, Any]) -> str:
        if not self.api_key:
            return _mock_decision("Anthropic API key not configured.")

        try:
            import anthropic  # type: ignore
        except Exception:
            return _mock_decision("Anthropic SDK not installed; returning mock decision.")

        try:
            client = anthropic.Anthropic(api_key=self.api_key)
            model = self.model or "claude-sonnet-4-6"
            message = client.messages.create(
                model=model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            text = None
            if hasattr(message, "content") and message.content:
                text = message.content[0].text
            if not text:
                return _mock_decision("Anthropic response missing text output.")
            return text
        except Exception as exc:
            return _mock_decision(f"Anthropic call failed: {exc}")
