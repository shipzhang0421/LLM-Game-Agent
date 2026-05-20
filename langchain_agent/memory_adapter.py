from __future__ import annotations

from typing import Iterable, List


def build_memory_messages(memory_lines: Iterable[str]):
    from langchain_core.messages import AIMessage

    messages: List[AIMessage] = []
    for line in memory_lines:
        messages.append(AIMessage(content=f"Previous execution trace: {line}"))
    return messages
