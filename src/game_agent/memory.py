from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional


@dataclass
class MemoryEntry:
    action: str
    feedback: str
    success: bool


class SlidingMemory:
    def __init__(self, size: int = 8) -> None:
        self.entries: Deque[MemoryEntry] = deque(maxlen=size)
        self.last_reflection: Optional[str] = None

    def add(self, action: str, feedback: str, success: bool) -> None:
        self.entries.append(MemoryEntry(action=action, feedback=feedback, success=success))

    def reflect(self, action: str, feedback: str) -> str:
        reflection = f"Avoid repeating `{action}` because: {feedback}"
        self.last_reflection = reflection
        return reflection

    def recent_failures(self) -> List[str]:
        return [entry.action for entry in self.entries if not entry.success]

    def to_prompt_context(self) -> List[str]:
        lines = []
        for item in self.entries:
            status = "success" if item.success else "fail"
            lines.append(f"{item.action} -> {status}: {item.feedback}")
        if self.last_reflection:
            lines.append(f"reflection: {self.last_reflection}")
        return lines
