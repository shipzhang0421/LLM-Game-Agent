from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .environment import OpenWorldEnv
from .llm import Planner
from .memory import SlidingMemory


@dataclass
class EpisodeResult:
    success: bool
    steps: int
    final_hp: int
    final_hunger: int
    inventory: Dict[str, int]
    collected: Dict[str, int]
    final_position: Tuple[int, int]
    goal_achieved: bool
    repeated_failures: int
    idle_steps: int
    trace: List[Dict[str, object]]


class GameAgent:
    def __init__(self, planner: Planner, memory_size: int = 8) -> None:
        self.planner = planner
        self.memory = SlidingMemory(size=memory_size)

    def run_episode(
        self, env: OpenWorldEnv, max_steps: int = 50, verbose: bool = False
    ) -> EpisodeResult:
        repeated_failures = 0
        idle_steps = 0
        trace: List[Dict[str, object]] = []

        for step_id in range(1, max_steps + 1):
            observation = env.describe()
            memory_context = self.memory.to_prompt_context()
            plan = self.planner.plan(observation=observation, memory=memory_context)
            outcome = env.step(plan.action)
            success = bool(outcome["success"])
            feedback = str(outcome["feedback"])

            if verbose:
                print(f"\n[Step {step_id}]")
                print(f"Observation: {observation}")
                print(f"Thought: {plan.thought}")
                print(f"Action: {plan.action}")
                print(f"Feedback: {feedback}")

            self.memory.add(plan.action, feedback, success)
            trace.append(
                {
                    "step": step_id,
                    "observation": observation,
                    "thought": plan.thought,
                    "action": plan.action,
                    "feedback": feedback,
                    "success": success,
                }
            )

            if not success:
                repeated_failures += 1
                reflection = self.memory.reflect(plan.action, feedback)
                if verbose:
                    print(f"Reflection: {reflection}")

            if plan.action == "rest" or "No collectible" in feedback:
                idle_steps += 1

            if outcome["goal_achieved"]:
                break
            if not env.state.alive:
                break

        return EpisodeResult(
            success=env.state.alive,
            steps=env.state.steps,
            final_hp=env.state.hp,
            final_hunger=env.state.hunger,
            inventory=dict(env.state.inventory),
            collected=dict(env.state.collected),
            final_position=env.state.position,
            goal_achieved=env.is_goal_achieved(),
            repeated_failures=repeated_failures,
            idle_steps=idle_steps,
            trace=trace,
        )
