"""Anthropic provider implementation."""

from __future__ import annotations

from typing import Any, Dict

from .base import (
    BaseProvider,
    ProviderConfigurationError,
    ProviderExecutionError,
    ProviderUnavailableError,
)


class AnthropicProvider(BaseProvider):
    def validate_configuration(self) -> None:
        if not self.api_key:
            raise ProviderConfigurationError("Anthropic API key not configured.")

        try:
            import anthropic  # type: ignore  # noqa: F401
        except Exception as exc:
            raise ProviderUnavailableError(
                "Anthropic SDK is not installed. Install the `anthropic` package to use the Anthropic provider."
            ) from exc

    def generate_decision(self, prompt: str, context: Dict[str, Any]) -> str:
        self.validate_configuration()

        import anthropic  # type: ignore

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
                raise ProviderExecutionError("Anthropic response missing text output.")
            return text
        except Exception as exc:
            if isinstance(exc, ProviderExecutionError):
                raise
            raise ProviderExecutionError(f"Anthropic call failed: {exc}") from exc
