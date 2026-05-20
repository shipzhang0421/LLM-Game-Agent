from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from typing import Dict, Tuple

from .scenario import Position, ScenarioConfig, built_in_scenarios




@dataclass
class EnvState:
    position: Position
    hp: int
    hunger: int
    energy: int
    inventory: Dict[str, int] = field(
        default_factory=lambda: {"wood": 0, "stone": 0, "food": 0}
    )
    collected: Dict[str, int] = field(
        default_factory=lambda: {"wood": 0, "stone": 0, "food": 0}
    )
    steps: int = 0
    alive: bool = True
    sheltered: bool = False


class OpenWorldEnv:
    """A compact open-world survival environment for agent reproduction."""

    def __init__(self, seed: int = 0, scenario: ScenarioConfig | None = None) -> None:
        self.random = Random(seed)
        self.scenario = scenario or built_in_scenarios()["standard"]
        self.grid = self.scenario.grid
        self.height = len(self.grid)
        self.width = len(self.grid[0])
        self.start = self.scenario.start
        self.shelter = self.scenario.shelter
        self.state = EnvState(
            position=self.start,
            hp=self.scenario.initial_hp,
            hunger=self.scenario.initial_hunger,
            energy=self.scenario.initial_energy,
        )
        self.goal = self.scenario.goal

    def current_tile(self) -> str:
        x, y = self.state.position
        return self.grid[y][x]

    def neighbors(self) -> Dict[str, Position]:
        x, y = self.state.position
        candidates = {
            "up": (x, y - 1),
            "down": (x, y + 1),
            "left": (x - 1, y),
            "right": (x + 1, y),
        }
        return {
            direction: pos
            for direction, pos in candidates.items()
            if 0 <= pos[0] < self.width and 0 <= pos[1] < self.height
        }

    def describe(self) -> Dict[str, object]:
        nearby = {}
        for direction, pos in self.neighbors().items():
            nearby[direction] = self.grid[pos[1]][pos[0]]

        goal_progress = {
            "wood_needed": max(0, self.goal["wood"] - self.state.collected["wood"]),
            "stone_needed": max(0, self.goal["stone"] - self.state.collected["stone"]),
            "food_needed": max(0, self.goal["food"] - self.state.collected["food"]),
            "at_shelter": self.state.position == self.shelter,
        }

        return {
            "position": self.state.position,
            "tile": self.current_tile(),
            "nearby": nearby,
            "hp": self.state.hp,
            "hunger": self.state.hunger,
            "energy": self.state.energy,
            "inventory": dict(self.state.inventory),
            "collected": dict(self.state.collected),
            "goal_progress": goal_progress,
            "resource_sites": self.scenario.resource_sites,
            "scenario": self.scenario.name,
        }

    def is_goal_achieved(self) -> bool:
        return (
            self.state.collected["wood"] >= self.goal["wood"]
            and self.state.collected["stone"] >= self.goal["stone"]
            and self.state.collected["food"] >= self.goal["food"]
            and self.state.position == self.shelter
        )

    def step(self, action: str) -> Dict[str, object]:
        if not self.state.alive:
            return {"success": False, "feedback": "Agent is already dead."}

        self.state.steps += 1
        self.state.energy = max(0, self.state.energy - 1)
        self.state.hunger = max(0, self.state.hunger - 1)

        if self.state.hunger == 0:
            self.state.hp = max(0, self.state.hp - 1)

        result = {"success": False, "feedback": "", "reward": 0}

        if action.startswith("move:"):
            direction = action.split(":", 1)[1]
            result = self._move(direction)
        elif action == "gather":
            result = self._gather()
        elif action == "eat":
            result = self._eat()
        elif action == "rest":
            result = self._rest()
        elif action == "craft_shelter":
            result = self._craft_shelter()
        else:
            result["feedback"] = f"Unknown action: {action}"

        if self.current_tile() == "danger":
            self.state.hp = max(0, self.state.hp - 2)
            result["feedback"] += " Danger tile caused damage."

        if self.state.hp <= 0:
            self.state.alive = False
            result["feedback"] += " Agent died."

        result["state"] = self.describe()
        result["goal_achieved"] = self.is_goal_achieved()
        return result

    def _move(self, direction: str) -> Dict[str, object]:
        neighbors = self.neighbors()
        if direction not in neighbors:
            return {"success": False, "feedback": f"Cannot move {direction}.", "reward": -1}

        self.state.position = neighbors[direction]
        tile = self.current_tile()
        reward = 1 if tile not in {"danger", "river"} else 0
        return {"success": True, "feedback": f"Moved {direction} to {tile}.", "reward": reward}

    def _gather(self) -> Dict[str, object]:
        tile = self.current_tile()
        if tile == "forest":
            self.state.inventory["wood"] += 1
            self.state.collected["wood"] += 1
            return {"success": True, "feedback": "Gathered 1 wood.", "reward": 2}
        if tile == "quarry":
            self.state.inventory["stone"] += 1
            self.state.collected["stone"] += 1
            return {"success": True, "feedback": "Gathered 1 stone.", "reward": 2}
        if tile == "river":
            self.state.inventory["food"] += 1
            self.state.collected["food"] += 1
            return {"success": True, "feedback": "Caught 1 fish.", "reward": 2}
        return {"success": False, "feedback": "No collectible resource on this tile.", "reward": -1}

    def _eat(self) -> Dict[str, object]:
        if self.state.inventory["food"] <= 0:
            return {"success": False, "feedback": "No food to eat.", "reward": -1}
        self.state.inventory["food"] -= 1
        self.state.hunger = min(8, self.state.hunger + 4)
        self.state.hp = min(10, self.state.hp + 1)
        return {"success": True, "feedback": "Ate food and recovered.", "reward": 2}

    def _rest(self) -> Dict[str, object]:
        self.state.energy = min(8, self.state.energy + 3)
        if self.current_tile() == "shelter" or self.state.sheltered:
            self.state.hp = min(10, self.state.hp + 1)
            return {"success": True, "feedback": "Rested safely and recovered.", "reward": 2}
        return {"success": True, "feedback": "Rested in the wild.", "reward": 0}

    def _craft_shelter(self) -> Dict[str, object]:
        inventory = self.state.inventory
        if inventory["wood"] < 2 or inventory["stone"] < 1:
            return {
                "success": False,
                "feedback": "Not enough resources to craft shelter.",
                "reward": -1,
            }
        inventory["wood"] -= 2
        inventory["stone"] -= 1
        self.state.sheltered = True
        return {"success": True, "feedback": "Crafted a temporary shelter.", "reward": 3}

    def manhattan_distance(self, target: Position) -> int:
        x1, y1 = self.state.position
        x2, y2 = target
        return abs(x1 - x2) + abs(y1 - y2)
