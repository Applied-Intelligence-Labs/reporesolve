"""Agent memory placeholder for future decision history."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .schema import AgentDecision


@dataclass
class AgentMemory:
    decisions: List[AgentDecision] = field(default_factory=list)

    def record(self, decision: AgentDecision) -> None:
        self.decisions.append(decision)
