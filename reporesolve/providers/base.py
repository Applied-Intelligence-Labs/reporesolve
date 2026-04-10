"""Provider interface for agent decisions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ProviderError(RuntimeError):
    """Base class for provider-related failures."""


class ProviderConfigurationError(ProviderError):
    """Raised when provider configuration is missing or invalid."""


class ProviderUnavailableError(ProviderError):
    """Raised when the selected provider SDK is unavailable."""


class ProviderExecutionError(ProviderError):
    """Raised when the provider call fails or returns unusable output."""


class BaseProvider(ABC):
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        self.api_key = api_key
        self.model = model

    @abstractmethod
    def validate_configuration(self) -> None:
        """Validate that the provider is configured and available."""
        raise NotImplementedError

    @abstractmethod
    def generate_decision(self, prompt: str, context: Dict[str, Any]) -> str:
        """Return a JSON string matching the AgentDecision schema."""
        raise NotImplementedError
