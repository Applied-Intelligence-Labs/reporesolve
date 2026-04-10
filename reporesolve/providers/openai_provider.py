"""OpenAI provider implementation."""

from __future__ import annotations

from typing import Any, Dict

from .base import (
    BaseProvider,
    ProviderConfigurationError,
    ProviderExecutionError,
    ProviderUnavailableError,
)


class OpenAIProvider(BaseProvider):
    def validate_configuration(self) -> None:
        if not self.api_key:
            raise ProviderConfigurationError("OpenAI API key not configured.")

        try:
            from openai import OpenAI  # type: ignore  # noqa: F401
        except Exception as exc:
            raise ProviderUnavailableError(
                "OpenAI SDK is not installed. Install the `openai` package to use the OpenAI provider."
            ) from exc

    def generate_decision(self, prompt: str, context: Dict[str, Any]) -> str:
        self.validate_configuration()

        from openai import OpenAI  # type: ignore

        try:
            client = OpenAI(api_key=self.api_key)
            model = self.model or "gpt-5.4"
            response = client.responses.create(model=model, input=prompt)
            text = getattr(response, "output_text", None)
            if not text:
                text = response.output[0].content[0].text  # type: ignore[attr-defined]
            if not text:
                raise ProviderExecutionError("OpenAI response missing text output.")
            return text
        except Exception as exc:
            if isinstance(exc, ProviderExecutionError):
                raise
            raise ProviderExecutionError(f"OpenAI call failed: {exc}") from exc
