from __future__ import annotations

import os
from typing import Dict, List

from src.game_agent.llm import PlannerOutput

from .memory_adapter import build_memory_messages
from .schemas import MinecraftDecision
from .tools import MINECRAFT_ACTION_TOOLS, render_tool_catalog


def _require_langchain():
    try:
        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
        from langchain_openai import ChatOpenAI
    except ImportError:
        return None

    return ChatPromptTemplate, MessagesPlaceholder, ChatOpenAI


class LangChainMinecraftPlanner:
    """LangChain-based planner for the Minecraft bridge."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.1,
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
        self.chain = None
        if not self.model or not self.api_key:
            raise ValueError(
                "OPENAI_MODEL/OPENAI_API_KEY or DEEPSEEK_MODEL/DEEPSEEK_API_KEY are required for LangChain planner."
            )

        if langchain_runtime is None:
            return

        ChatPromptTemplate, MessagesPlaceholder, ChatOpenAI = langchain_runtime

        tool_catalog = render_tool_catalog(MINECRAFT_ACTION_TOOLS)
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a Minecraft survival agent. "
                    "Choose exactly one tool action from the catalog. "
                    "Prioritize staying alive, then maintaining a stable resource loop, then exploration.\n\n"
                    "Hard rules:\n"
                    "1. If food <= 8 and edible food exists, use `eat`.\n"
                    "2. If food <= 6 and no edible food exists, prefer `collect:food` when a food source is detectable.\n"
                    "3. Mature crops and passive food mobs are stronger food signals than open water alone.\n"
                    "4. If wood logs in inventory are below 8 and a tree is detectable, prefer `collect:wood`.\n"
                    "5. If recent memory shows repeated failure for the same action, avoid blindly repeating it.\n"
                    "6. Use `reorient` or `report:status` when the world state seems stale or exploration is looping.\n"
                    "7. Use `observe` when the best next step is to refresh perception without moving.\n\n"
                    "Tool catalog:\n{tool_catalog}",
                ),
                (
                    "human",
                    "Example observation:\n"
                    "{{'food': 5, 'inventory_summary': {{}}, 'target_summary': {{'tree_detected': True, 'food_source_detected': True}}}}\n"
                    "What should you do?",
                ),
                (
                    "ai",
                    '{"thought":"Food is already in a risky range and there is no edible item in inventory, so restoring the food loop is more urgent than wood collection.","subgoal":"recover food supply","action":"collect:food"}',
                ),
                (
                    "human",
                    "Example observation:\n"
                    "{{'food': 14, 'inventory_summary': {{'log': 1}}, 'target_summary': {{'tree_detected': True, 'food_source_detected': False}}}}\n"
                    "What should you do?",
                ),
                (
                    "ai",
                    '{"thought":"Survival is stable and wood stock is still low while a tree is visible, so collect wood now.","subgoal":"build wood reserve","action":"collect:wood"}',
                ),
                MessagesPlaceholder("memory_messages", optional=True),
                (
                    "human",
                    "Current Minecraft observation:\n{observation}\n\n"
                    "Return a concise thought, a short subgoal, and one executable action.",
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
            MinecraftDecision,
            method="function_calling",
        )

    def plan(self, observation: Dict[str, object], memory: List[str]) -> PlannerOutput:
        guarded = self._guardrail_plan(observation, memory)
        if guarded is not None:
            return guarded

        if self.chain is None:
            return self._fallback_plan(observation, memory)

        result: MinecraftDecision = self.chain.invoke(
            {
                "observation": observation,
                "memory_messages": build_memory_messages(memory),
            }
        )
        return PlannerOutput(
            thought=f"{result.subgoal}: {result.thought}",
            action=result.action,
        )

    def _fallback_plan(self, observation: Dict[str, object], memory: List[str]) -> PlannerOutput:
        target_summary = observation.get("target_summary", {})
        execution = observation.get("execution_context", {})

        if target_summary.get("food_source_detected") and int(observation.get("food", 20)) <= 6:
            return PlannerOutput(
                thought="recover food supply: LangChain runtime is unavailable, so the fallback planner prioritizes the visible food source.",
                action="collect:food",
            )

        if target_summary.get("tree_detected"):
            return PlannerOutput(
                thought="build wood reserve: LangChain runtime is unavailable, so the fallback planner uses visible tree cues.",
                action="collect:wood",
            )

        if execution.get("explore_stuck"):
            return PlannerOutput(
                thought="refresh search heading: exploration appears stuck, so rotate before moving again.",
                action="reorient",
            )

        return PlannerOutput(
            thought="refresh local world model: LangChain runtime is unavailable, so continue with a safe exploration default.",
            action="explore",
        )

    def _guardrail_plan(self, observation: Dict[str, object], memory: List[str]) -> PlannerOutput | None:
        inventory = observation.get("inventory_summary", {})
        visible_targets = observation.get("visible_targets", {})
        target_summary = observation.get("target_summary", {})
        survival = observation.get("survival_state", {})
        execution = observation.get("execution_context", {})
        resource_summary = observation.get("resource_summary", {})

        food = int(observation.get("food", 20))
        health = int(observation.get("health", 20))
        wood_logs = int(resource_summary.get("wood_count", 0)) or self._count_matching(
            inventory,
            ("log", "oak_log", "birch_log", "spruce_log", "jungle_log", "acacia_log", "dark_oak_log"),
        )
        repeated_failures = int(execution.get("repeated_failures", 0))
        last_action = str(execution.get("last_action", ""))
        food_source_type = target_summary.get("food_source_type")

        if (food <= 8 or health <= 12) and self._has_food(inventory):
            return PlannerOutput(
                thought="stabilize hunger: food is low enough that consuming available food is safer than continuing the current task.",
                action="eat",
            )

        if food <= 6 and not self._has_food(inventory):
            if target_summary.get("food_source_detected"):
                source_phrase = {
                    "crop": "mature crops are available nearby",
                    "animal": "a passive food mob is within reach",
                    "water": "water is the only current food-search anchor",
                }.get(food_source_type, "a food source is detectable")
                return PlannerOutput(
                    thought=f"restore food loop: hunger is trending dangerous and {source_phrase}, so collect food before resuming other goals.",
                    action="collect:food",
                )
            if repeated_failures >= 2 and last_action in {"explore", "collect:food"}:
                return PlannerOutput(
                    thought="refresh search: food is urgent but recent attempts stalled, so reorient before trying again.",
                    action="reorient",
                )
            return PlannerOutput(
                thought="search for food: no edible reserve is available, so exploration should bias toward finding a food source.",
                action="explore",
            )

        if wood_logs < 8 and target_summary.get("tree_detected"):
            if repeated_failures >= 2 and last_action == "collect:wood":
                return PlannerOutput(
                    thought="refresh wood route: a tree exists but collection recently failed repeatedly, so refresh heading before retrying.",
                    action="reorient",
                )
            return PlannerOutput(
                thought="build wood reserve: visible trees make wood collection the highest-value next action.",
                action="collect:wood",
            )

        if repeated_failures >= 2 and last_action in {"explore", "collect:wood", "collect:food"}:
            return PlannerOutput(
                thought="break local loop: repeated failures suggest stale local state, so request a status refresh.",
                action="report:status",
            )

        if survival.get("needs_attention"):
            return PlannerOutput(
                thought="refresh perception: survival metrics are drifting, so observe once before committing to another move.",
                action="observe",
            )

        return None

    def _has_food(self, inventory: Dict[str, int]) -> bool:
        food_keywords = ("beef", "porkchop", "bread", "apple", "potato", "salmon", "cod", "fish", "chicken")
        return any(any(word in item for word in food_keywords) for item in inventory)

    def _count_matching(self, inventory: Dict[str, int], candidates: tuple[str, ...]) -> int:
        total = 0
        for item_name, count in inventory.items():
            if item_name in candidates:
                total += count
        return total
