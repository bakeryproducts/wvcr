from dataclasses import dataclass, field
from typing import Any, Dict, List

@dataclass
class WorkingState:
    """Mutable bag passed through steps."""
    data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    timeline: List[tuple] = field(default_factory=list)  # (step_name, duration)

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value: Any):
        self.data[key] = value

    def has(self, key: str) -> bool:
        return key in self.data
