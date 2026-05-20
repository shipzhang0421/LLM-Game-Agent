from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


GridAction = Literal[
    "move:up",
    "move:down",
    "move:left",
    "move:right",
    "gather",
    "eat",
    "rest",
    "craft_shelter",
]


MinecraftAction = Literal[
    "collect:wood",
    "collect:food",
    "explore",
    "reorient",
    "eat",
    "report:status",
    "stop",
    "observe",
]


class GridDecision(BaseModel):
    thought: str = Field(description="Short reasoning summary for the next step.")
    action: GridAction = Field(description="One executable grid-world action.")


class MinecraftDecision(BaseModel):
    thought: str = Field(description="Short reasoning summary for the next step.")
    subgoal: str = Field(description="The immediate survival or resource objective behind the action.")
    action: MinecraftAction = Field(description="One executable Minecraft bridge action.")
