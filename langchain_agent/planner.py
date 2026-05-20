from __future__ import annotations

import os
from typing import Dict, List

from src.game_agent.llm import Planner, PlannerOutput

from .memory_adapter import build_memory_messages
from .schemas import GridDecision
from .tools import GRID_ACTION_TOOLS, render_tool_catalog


def _require_langchain():
    try:
        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
        from langchain_openai import ChatOpenAI
    except ImportError:
        return None

    return ChatPromptTemplate, MessagesPlaceholder, ChatOpenAI


class LangChainGridPlanner(Planner):
    """Grid-world planner built from LangChain prompt, tools, and structured output."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.2,
    ) -> None:
        langchain_runtime = _require_langchain()

        self.model = model or os.getenv("OPENAI_MODEL") or os.getenv("DEEPSEEK_MODEL")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = (
            base_url
            or os.getenv("OPENAI_BASE_URL")
            or os.getenv("DEEPSEEK_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/")
        if not self.model or not self.api_key:
            raise ValueError(
                "OPENAI_MODEL/OPENAI_API_KEY or DEEPSEEK_MODEL/DEEPSEEK_API_KEY are required for LangChain planner."
            )

        self.chain = None
        if langchain_runtime is not None:
            ChatPromptTemplate, MessagesPlaceholder, ChatOpenAI = langchain_runtime
            tool_catalog = render_tool_catalog(GRID_ACTION_TOOLS)
            self.prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "You are an open-world survival game planner. "
                        "Choose exactly one executable action from the tool catalog. "
                        "Prioritize survival first, then task completion, then efficiency.\n\n"
                        "Hard environment rules:\n"
                        "1. `gather` only works on the current tile.\n"
                        "2. `forest -> gather wood`.\n"
                        "3. `quarry -> gather stone`.\n"
                        "4. `river -> gather food`.\n"
                        "5. If hunger <= 2 and inventory.food > 0, use `eat` immediately.\n"
                        "6. If hunger <= 2 and inventory.food == 0, move toward a river; "
                        "if already on a river, use `gather` immediately.\n"
                        "7. If hp is low and the current tile is dangerous, leave danger first.\n"
                        "8. If all wood/stone/food goals are finished, go to shelter instead of farming more resources.\n"
                        "9. Never move away from a river when hunger is 0 and food is still needed.\n"
                        "10. When the current tile already provides a still-needed resource, prefer `gather` over movement.\n\n"
                        "Tool catalog:\n{tool_catalog}",
                    ),
                    (
                        "human",
                        "Example observation:\n"
                        "{{'tile': 'river', 'hunger': 1, 'inventory': {{'food': 0}}, "
                        "'goal_progress': {{'food_needed': 2, 'wood_needed': 0, 'stone_needed': 0, 'at_shelter': False}}}}\n"
                        "What should you do?",
                    ),
                    (
                        "ai",
                        '{{"thought":"Hunger is critical, food is still needed, and the current river tile is the only tile that can produce food, so gather immediately.","action":"gather"}}',
                    ),
                    (
                        "human",
                        "Example observation:\n"
                        "{{'tile': 'forest', 'hunger': 6, 'inventory': {{'food': 0}}, "
                        "'goal_progress': {{'food_needed': 2, 'wood_needed': 1, 'stone_needed': 2, 'at_shelter': False}}}}\n"
                        "What should you do?",
                    ),
                    (
                        "ai",
                        '{{"thought":"The current forest tile provides wood and wood is still needed, so gathering is better than moving away.","action":"gather"}}',
                    ),
                    (
                        "human",
                        "Example observation:\n"
                        "{{'tile': 'plain', 'hunger': 2, 'inventory': {{'food': 1}}, "
                        "'goal_progress': {{'food_needed': 1, 'wood_needed': 0, 'stone_needed': 1, 'at_shelter': False}}}}\n"
                        "What should you do?",
                    ),
                    (
                        "ai",
                        '{{"thought":"Hunger is critical and food is already available in inventory, so eating now is the safest move.","action":"eat"}}',
                    ),
                    MessagesPlaceholder("memory_messages", optional=True),
                    (
                        "human",
                        "Current observation:\n{observation}\n\n"
                        "Decision checklist:\n"
                        "- First check whether survival rules force `eat` or `gather`.\n"
                        "- Then check whether the current tile already satisfies a still-needed resource.\n"
                        "- Only move when the current tile cannot directly solve the highest-priority need.\n\n"
                        "Return a structured decision with a concise thought and one action.",
                    ),
                ]
            ).partial(tool_catalog=tool_catalog)

            self.llm = ChatOpenAI(
                model=self.model,
                api_key=self.api_key,
                base_url=self.base_url,
                temperature=temperature,
                timeout=int(os.getenv("OPENAI_TIMEOUT", "60")),
            )
            self.chain = self.prompt | self.llm.with_structured_output(
                GridDecision,
                method="function_calling",
            )

    def plan(self, observation: Dict[str, object], memory: List[str]) -> PlannerOutput:
        guarded = self._guardrail_plan(observation, memory)
        if guarded is not None:
            return guarded

        if self.chain is None:
            return PlannerOutput(
                thought="Guardrail-only fallback: LangChain runtime is unavailable, so the deterministic survival policy is used.",
                action=guarded.action,
            )

        result: GridDecision = self.chain.invoke(
            {
                "observation": observation,
                "memory_messages": build_memory_messages(memory),
            }
        )
        return PlannerOutput(thought=result.thought, action=result.action)

    def _guardrail_plan(
        self,
        observation: Dict[str, object],
        memory: List[str],
    ) -> PlannerOutput | None:
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
                    thought="Guardrail: collection goals are finished, but one emergency meal maximizes the chance of reaching shelter.",
                    action="eat",
                )
            return PlannerOutput(
                thought="Guardrail: all collection goals are complete, so return to shelter immediately.",
                action=self._move_towards_target(position, nearby, resource_sites["shelter"], memory),
            )

        if hunger <= 2 and inventory["food"] > 0:
            return PlannerOutput(
                thought="Guardrail: hunger is critical and food is available, so eat immediately.",
                action="eat",
            )

        if hunger <= 2 and inventory["food"] == 0:
            if tile == "river":
                return PlannerOutput(
                    thought="Guardrail: hunger is critical and the current river tile can generate food, so gather immediately.",
                    action="gather",
                )
            return PlannerOutput(
                thought="Guardrail: hunger is critical with no food in inventory, so move toward the nearest river.",
                action=self._move_towards_target(position, nearby, resource_sites["river"], memory),
            )

        if hp <= 3 and tile == "danger":
            return PlannerOutput(
                thought="Guardrail: HP is low on a danger tile, so escape first.",
                action=self._move_to_safer_tile(nearby),
            )

        if tile == "forest" and goal_progress["wood_needed"] > 0:
            return PlannerOutput(
                thought="Guardrail: the current forest tile directly provides still-needed wood, so gather now.",
                action="gather",
            )

        if tile == "quarry" and goal_progress["stone_needed"] > 0:
            return PlannerOutput(
                thought="Guardrail: the current quarry tile directly provides still-needed stone, so gather now.",
                action="gather",
            )

        if tile == "river" and goal_progress["food_needed"] > 0:
            return PlannerOutput(
                thought="Guardrail: the current river tile directly provides still-needed food, so gather now.",
                action="gather",
            )

        if observation["energy"] <= 1 and tile == "shelter" and hp < 10:
            return PlannerOutput(
                thought="Guardrail: shelter allows safe recovery, so rest here.",
                action="rest",
            )

        target_tile = self._next_resource_target(goal_progress)
        if tile == target_tile:
            return PlannerOutput(
                thought=(
                    f"Guardrail: the current tile already matches the next resource target "
                    f"`{target_tile}`, so gathering is optimal."
                ),
                action="gather",
            )

        return PlannerOutput(
            thought=(
                f"Guardrail: the next shortage is `{target_tile}`, so move toward the nearest "
                f"{target_tile} tile while avoiding recent failed directions and danger when possible."
            ),
            action=self._move_towards_target(position, nearby, resource_sites[target_tile], memory),
        )

    def _recent_failed_moves(self, memory: List[str]) -> set[str]:
        failed = set()
        for item in memory:
            if " -> fail:" in item:
                failed.add(item.split(" -> ", 1)[0])
        return {action for action in failed if action.startswith("move:")}

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

    def _next_resource_target(self, goal_progress: Dict[str, object]) -> str:
        if goal_progress["wood_needed"] > 0:
            return "forest"
        if goal_progress["stone_needed"] > 0:
            return "quarry"
        return "river"

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
