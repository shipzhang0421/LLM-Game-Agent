from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str


def render_tool_catalog(tools: list[ToolSpec]) -> str:
    return "\n".join(f"- {tool.name}: {tool.description}" for tool in tools)


GRID_ACTION_TOOLS = [
    ToolSpec("move_up", "Move one cell upward in the grid-world environment."),
    ToolSpec("move_down", "Move one cell downward in the grid-world environment."),
    ToolSpec("move_left", "Move one cell left in the grid-world environment."),
    ToolSpec("move_right", "Move one cell right in the grid-world environment."),
    ToolSpec("gather", "Collect the resource available on the current grid tile."),
    ToolSpec("eat", "Consume available food to recover hunger and a small amount of HP."),
    ToolSpec("rest", "Rest to recover energy and possibly HP if in a safe shelter."),
    ToolSpec("craft_shelter", "Build a temporary shelter when enough wood and stone are available."),
]

MINECRAFT_ACTION_TOOLS = [
    ToolSpec("collect_wood", "Move toward a detected tree and mine reachable wood blocks."),
    ToolSpec(
        "collect_food",
        "Move toward a reachable food source or gather food from a river-like source when available.",
    ),
    ToolSpec("explore", "Continue scouting the nearby Minecraft world for resources or trees."),
    ToolSpec(
        "reorient",
        "Stop drifting, refresh heading, and rotate to search in a new direction before the next action.",
    ),
    ToolSpec("eat", "Consume an edible item already in inventory."),
    ToolSpec("report_status", "Refresh and persist the latest Minecraft observation and runtime status."),
    ToolSpec("stop", "Stop current movement and cancel any active pathfinding goal."),
    ToolSpec("observe", "Do not move; only refresh local observation and runtime status for the next planning cycle."),
]

GRID_TOOL_TO_ACTION = {
    "move_up": "move:up",
    "move_down": "move:down",
    "move_left": "move:left",
    "move_right": "move:right",
    "gather": "gather",
    "eat": "eat",
    "rest": "rest",
    "craft_shelter": "craft_shelter",
}

MINECRAFT_TOOL_TO_ACTION = {
    "collect_wood": "collect:wood",
    "collect_food": "collect:food",
    "explore": "explore",
    "reorient": "reorient",
    "eat": "eat",
    "report_status": "report:status",
    "stop": "stop",
    "observe": "observe",
}
