from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.game_agent.llm import OpenAICompatiblePlanner, PlannerOutput, RuleBasedPlanner


class MinecraftRulePlanner:
    """A lightweight planner for the first Minecraft bridge milestone."""

    def plan(self, observation: Dict[str, object], memory: List[str]) -> PlannerOutput:
        nearby_blocks = observation.get("nearby_blocks", {})
        visible_targets = observation.get("visible_targets", {})
        target_summary = observation.get("target_summary", {})
        inventory = observation.get("inventory_summary", {})
        food = int(observation.get("food", 20))
        health = int(observation.get("health", 20))
        wood_count = self._count_matching(
            inventory,
            ("log", "oak_log", "birch_log", "spruce_log", "jungle_log"),
        )
        recent_failures = [entry for entry in memory if "fail" in entry]

        if (food <= 10 or health <= 12) and self._has_food(inventory):
            return PlannerOutput(
                thought="Food is low and edible items are available, so eating is the safest action.",
                action="eat",
            )

        if food <= 6 and not self._has_food(inventory) and target_summary.get("food_source_detected"):
            return PlannerOutput(
                thought="Food is in a risky range and a real food source is visible, so recover the food loop before continuing other work.",
                action="collect:food",
            )

        if wood_count < 8 and self._can_see_wood(nearby_blocks, visible_targets):
            return PlannerOutput(
                thought="Wood is still the main survival resource and a tree is detectable, so collect wood now.",
                action="collect:wood",
            )

        if food <= 6 and self._has_food(inventory):
            return PlannerOutput(
                thought="Food is entering a risky range, so recover before continuing exploration.",
                action="eat",
            )

        if recent_failures and "collect:wood" in recent_failures[-1]:
            return PlannerOutput(
                thought="The last wood collection attempt failed, so refresh the world state before retrying.",
                action="report:status",
            )

        if recent_failures and "explore" in recent_failures[-1]:
            return PlannerOutput(
                thought="Exploration recently stalled, so refresh status and choose a new direction next cycle.",
                action="report:status",
            )

        return PlannerOutput(
            thought="No urgent survival action is needed and no tree is currently in range, so continue exploring.",
            action="explore",
        )

    def _has_food(self, inventory: Dict[str, int]) -> bool:
        food_keywords = ("beef", "porkchop", "bread", "apple", "potato", "salmon", "cod")
        return any(any(word in item for word in food_keywords) for item in inventory)

    def _can_see_wood(self, nearby_blocks: Dict[str, str], visible_targets: Dict[str, object]) -> bool:
        preferred = (
            "log",
            "leaves",
            "oak_log",
            "birch_log",
            "spruce_log",
            "jungle_log",
            "oak_leaves",
            "birch_leaves",
            "spruce_leaves",
            "jungle_leaves",
        )
        for block_name in nearby_blocks.values():
            if block_name in preferred:
                return True
        nearest_tree = visible_targets.get("nearest_tree")
        nearest_leaves = visible_targets.get("nearest_leaves")
        return bool(nearest_tree or nearest_leaves)

    def _count_matching(self, inventory: Dict[str, int], candidates: tuple[str, ...]) -> int:
        total = 0
        for item_name, count in inventory.items():
            if item_name in candidates:
                total += count
        return total


def build_planner():
    planner_type = os.getenv("PLANNER_TYPE", "rule").strip().lower()
    if planner_type == "openai":
        return OpenAICompatiblePlanner()
    if planner_type == "langchain":
        from langchain_agent.minecraft_planner import LangChainMinecraftPlanner

        return LangChainMinecraftPlanner()
    return MinecraftRulePlanner()


def main() -> int:
    planner = build_planner()

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue

        try:
            payload = json.loads(line)
            observation = payload["observation"]
            memory = payload.get("memory", [])
            result = planner.plan(observation=observation, memory=memory)
            response = {"thought": result.thought, "action": result.action}
        except Exception as exc:  # pragma: no cover - bridge safety path
            response = {"error": "Planner failed", "details": str(exc)}

        sys.stdout.write(json.dumps(response, ensure_ascii=True) + "\n")
        sys.stdout.flush()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
