from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Protocol, Tuple
from urllib import request


@dataclass
class PlannerOutput:
    thought: str
    action: str
    raw_response: str | None = None


class Planner(Protocol):
    def plan(self, observation: Dict[str, object], memory: List[str]) -> PlannerOutput:
        ...


class RuleBasedPlanner:
    """
    A deterministic stand-in for an LLM planner.

    It mimics an LLM by consuming structured observation and memory,
    then emitting a thought and a next action.
    """

    def plan(self, observation: Dict[str, object], memory: List[str]) -> PlannerOutput:
        inventory = observation["inventory"]
        goal_progress = observation["goal_progress"]
        tile = observation["tile"]
        nearby = observation["nearby"]
        hunger = observation["hunger"]
        hp = observation["hp"]
        position = observation["position"]
        resource_sites = observation["resource_sites"]
        goals_complete = (
            goal_progress["wood_needed"] == 0
            and goal_progress["stone_needed"] == 0
            and goal_progress["food_needed"] == 0
        )

        if goals_complete and position != tuple(resource_sites["shelter"][0]):
            if hunger <= 1 and inventory["food"] > 0:
                return PlannerOutput(
                    thought="Collection goals are finished, but one emergency meal improves the chance of reaching shelter.",
                    action="eat",
                )
            action = self._move_towards_target(
                current=position,
                nearby=nearby,
                targets=resource_sites["shelter"],
            )
            return PlannerOutput(
                thought="All collection goals are complete, so the agent should immediately return to the final shelter.",
                action=action,
            )

        if hunger <= 2 and inventory["food"] > 0:
            return PlannerOutput(
                thought="Hunger is critical. Consuming food now increases survival probability.",
                action="eat",
            )

        if hunger <= 2 and inventory["food"] == 0:
            if tile == "river":
                return PlannerOutput(
                    thought="Hunger is urgent and a river is available, so gathering food is the safest recovery step.",
                    action="gather",
                )
            action = self._move_towards_target(
                current=position,
                nearby=nearby,
                targets=resource_sites["river"],
            )
            return PlannerOutput(
                thought="Hunger is urgent with no food in inventory, so the route is redirected to the nearest river.",
                action=action,
            )

        if hp <= 3 and tile == "danger":
            action = self._move_to_safer_tile(nearby)
            return PlannerOutput(
                thought="HP is low and current tile is dangerous. Immediate escape has priority.",
                action=action,
            )

        if tile == "forest" and goal_progress["wood_needed"] > 0:
            return PlannerOutput(
                thought="Current tile provides wood and wood is still needed for long-term survival.",
                action="gather",
            )

        if tile == "quarry" and goal_progress["stone_needed"] > 0:
            return PlannerOutput(
                thought="Current tile provides stone, which is still required by the plan.",
                action="gather",
            )

        if tile == "river" and goal_progress["food_needed"] > 0:
            return PlannerOutput(
                thought="Food stock is below target, so gathering food here is efficient.",
                action="gather",
            )

        if (
            inventory["wood"] > 2
            and inventory["stone"] > 2
            and observation["tile"] != "shelter"
            and "craft_shelter" not in self._recent_actions(memory)
        ):
            return PlannerOutput(
                thought="Resources are sufficient for a temporary shelter, improving fault tolerance.",
                action="craft_shelter",
            )

        if observation["energy"] <= 1 and tile == "shelter" and hp < 10:
            return PlannerOutput(
                thought="The final shelter allows safe recovery, so resting here is low-risk.",
                action="rest",
            )

        target_tile = self._next_resource_target(goal_progress)
        if tile == target_tile:
            return PlannerOutput(
                thought=f"The current tile already matches the next resource target `{target_tile}`, so gathering is optimal.",
                action="gather",
            )
        action = self._move_towards_target(
            current=position,
            nearby=nearby,
            targets=resource_sites[target_tile],
            memory=memory,
        )
        return PlannerOutput(
            thought=f"Next shortage is `{target_tile}`-type resource, so exploration is guided toward that area.",
            action=action,
        )

    def _recent_actions(self, memory: List[str]) -> List[str]:
        actions = []
        for item in memory:
            if " -> " in item:
                actions.append(item.split(" -> ", 1)[0])
        return actions

    def _recent_failed_moves(self, memory: List[str]) -> set[str]:
        failed = set()
        for item in memory:
            if " -> fail:" in item:
                failed.add(item.split(" -> ", 1)[0])
        return {action for action in failed if action.startswith("move:")}

    def _next_resource_target(self, goal_progress: Dict[str, object]) -> str:
        if goal_progress["wood_needed"] > 0:
            return "forest"
        if goal_progress["stone_needed"] > 0:
            return "quarry"
        return "river"

    def _move_towards_target(
        self,
        current: Tuple[int, int],
        nearby: Dict[str, str],
        targets: List[Tuple[int, int]],
        memory: List[str] | None = None,
    ) -> str:
        memory = memory or []
        failed = self._recent_failed_moves(memory[-3:])
        best_direction = None
        best_score = None

        for direction, tile in nearby.items():
            candidate = f"move:{direction}"
            if candidate in failed:
                continue
            next_pos = self._next_position(current, direction)
            score = min(self._manhattan(next_pos, target) for target in targets)
            penalty = 3 if tile == "danger" else 0
            total_score = score + penalty
            if best_score is None or total_score < best_score:
                best_score = total_score
                best_direction = direction

        if best_direction is not None:
            return f"move:{best_direction}"
        return self._move_to_safer_tile(nearby)

    def _move_to_safer_tile(self, nearby: Dict[str, str]) -> str:
        for direction, tile in nearby.items():
            if tile != "danger":
                return f"move:{direction}"
        return f"move:{next(iter(nearby.keys()))}"

    def _manhattan(self, a: Tuple[int, int], b: Tuple[int, int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def _next_position(self, current: Tuple[int, int], direction: str) -> Tuple[int, int]:
        x, y = current
        mapping = {
            "up": (x, y - 1),
            "down": (x, y + 1),
            "left": (x - 1, y),
            "right": (x + 1, y),
        }
        return mapping[direction]


class OpenAICompatiblePlanner:
    """
    Planner that calls an OpenAI-compatible Chat Completions endpoint.

    Required environment variables:
    - OPENAI_API_KEY
    - OPENAI_MODEL

    Optional:
    - OPENAI_BASE_URL, default: https://api.openai.com/v1
    - OPENAI_TIMEOUT

    DeepSeek convenience fallbacks:
    - DEEPSEEK_API_KEY
    - DEEPSEEK_MODEL
    - DEEPSEEK_BASE_URL
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.2,
    ) -> None:
        self.model = model or os.getenv("OPENAI_MODEL") or os.getenv("DEEPSEEK_MODEL")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = (
            base_url
            or os.getenv("OPENAI_BASE_URL")
            or os.getenv("DEEPSEEK_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/")
        self.temperature = temperature
        self.timeout = int(os.getenv("OPENAI_TIMEOUT", "60"))
        if not self.model or not self.api_key:
            raise ValueError(
                "OPENAI_MODEL/OPENAI_API_KEY or DEEPSEEK_MODEL/DEEPSEEK_API_KEY are required for the openai planner."
            )

    def plan(self, observation: Dict[str, object], memory: List[str]) -> PlannerOutput:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a game decision agent for an open-world survival task. "
                    "Return strict JSON with keys thought and action. "
                    "Valid actions are move:up, move:down, move:left, move:right, gather, eat, rest, craft_shelter."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "observation": observation,
                        "memory": memory,
                        "instruction": "Choose the next safest long-horizon action.",
                    },
                    ensure_ascii=True,
                ),
            },
        ]
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }
        raw = self._post_json(f"{self.base_url}/chat/completions", payload)
        content = raw["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return PlannerOutput(
            thought=str(parsed["thought"]),
            action=str(parsed["action"]),
            raw_response=content,
        )

    def _post_json(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))
