from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


@dataclass
class SessionState:
    # TODO: Replace repos with structured objects in Phase 3.
    repos: List[str] = field(default_factory=list)
    main_repo: str = ""
    working_name: str = "working-repo"
    mode: Literal["guided", "auto", "review"] = "guided"
    provider: Literal["openai", "anthropic"] = "openai"
    model: str = ""
    api_key: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)
