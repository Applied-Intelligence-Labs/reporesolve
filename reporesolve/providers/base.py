"""Provider interface for agent decisions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseProvider(ABC):
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        self.api_key = api_key
        self.model = model

    @abstractmethod
    def generate_decision(self, prompt: str, context: Dict[str, Any]) -> str:
        """Return a JSON string matching the AgentDecision schema."""
        raise NotImplementedError
