from __future__ import annotations
from typing import Protocol, Set
from abc import ABC, abstractmethod

class StepError(RuntimeError):
    def __init__(self, message: str, recoverable: bool = False):
        super().__init__(message)
        self.recoverable = recoverable

class Step(ABC):
    name: str = "unnamed"
    requires: Set[str] = set()
    provides: Set[str] = set()
    optional: bool = False  # pipeline can drop if flagged

    @abstractmethod
    def execute(self, state, ctx):
        """Mutate state; raise StepError on failure."""

    def enabled(self, ctx, state) -> bool:
        """Override to dynamically enable/disable (e.g., clipboard flag)."""
        return True
