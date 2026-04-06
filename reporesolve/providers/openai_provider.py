"""OpenAI provider implementation."""

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


class OpenAIProvider(BaseProvider):
    def generate_decision(self, prompt: str, context: Dict[str, Any]) -> str:
        if not self.api_key:
            return _mock_decision("OpenAI API key not configured.")

        try:
            from openai import OpenAI  # type: ignore
        except Exception:
            return _mock_decision("OpenAI SDK not installed; returning mock decision.")

        try:
            client = OpenAI(api_key=self.api_key)
            model = self.model or "gpt-5.4"
            response = client.responses.create(model=model, input=prompt)
            text = getattr(response, "output_text", None)
            if not text:
                text = response.output[0].content[0].text  # type: ignore[attr-defined]
            if not text:
                return _mock_decision("OpenAI response missing text output.")
            return text
        except Exception as exc:
            return _mock_decision(f"OpenAI call failed: {exc}")
