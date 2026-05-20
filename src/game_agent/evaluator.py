from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .agent import GameAgent
from .environment import OpenWorldEnv
from .llm import Planner, RuleBasedPlanner
from .scenario import ScenarioConfig, built_in_scenarios


def batch_evaluate(
    episodes: int = 20,
    max_steps: int = 50,
    planner: Planner | None = None,
    scenario_names: List[str] | None = None,
    report_file: str | None = None,
) -> Dict[str, object]:
    planner = planner or RuleBasedPlanner()
    scenarios = built_in_scenarios()
    selected_names = scenario_names or list(scenarios.keys())

    scenario_reports = []
    global_survival = 0
    global_goal = 0
    global_steps = 0
    global_resources = 0
    global_failures = 0
    global_idle = 0

    for scenario_name in selected_names:
        scenario = scenarios[scenario_name]
        metrics = _evaluate_single_scenario(
            scenario=scenario,
            episodes=episodes,
            max_steps=max_steps,
            planner=planner,
        )
        scenario_reports.append(metrics)
        global_survival += metrics["survival_count"]
        global_goal += metrics["goal_count"]
        global_steps += metrics["total_steps"]
        global_resources += metrics["total_resources"]
        global_failures += metrics["total_failures"]
        global_idle += metrics["total_idle"]

    total_episodes = episodes * len(selected_names)
    report = {
        "episodes_per_scenario": episodes,
        "scenario_count": len(selected_names),
        "survival_rate": round(global_survival / total_episodes, 3),
        "goal_rate": round(global_goal / total_episodes, 3),
        "avg_steps": round(global_steps / total_episodes, 2),
        "resource_utilization": round(global_resources / max(1, global_steps), 3),
        "path_efficiency": round(1 - (global_idle / max(1, global_steps)), 3),
        "logic_coherence": round(1 - (global_failures / max(1, global_steps)), 3),
        "scenarios": scenario_reports,
    }

    if report_file:
        path = Path(report_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report["report_file"] = str(path)

    return report


def _evaluate_single_scenario(
    scenario: ScenarioConfig,
    episodes: int,
    max_steps: int,
    planner: Planner,
) -> Dict[str, object]:
    survival_count = 0
    goal_count = 0
    total_steps = 0
    total_resources = 0
    total_failures = 0
    total_idle = 0

    for seed in range(episodes):
        env = OpenWorldEnv(seed=seed, scenario=scenario)
        agent = GameAgent(planner=planner, memory_size=8)
        result = agent.run_episode(env=env, max_steps=max_steps, verbose=False)

        survival_count += int(result.success)
        goal_count += int(result.goal_achieved)
        total_steps += result.steps
        total_resources += sum(result.collected.values())
        total_failures += result.repeated_failures
        total_idle += result.idle_steps

    return {
        "name": scenario.name,
        "description": scenario.description,
        "episodes": episodes,
        "survival_rate": round(survival_count / episodes, 3),
        "goal_rate": round(goal_count / episodes, 3),
        "avg_steps": round(total_steps / episodes, 2),
        "resource_utilization": round(total_resources / max(1, total_steps), 3),
        "path_efficiency": round(1 - (total_idle / max(1, total_steps)), 3),
        "logic_coherence": round(1 - (total_failures / max(1, total_steps)), 3),
        "survival_count": survival_count,
        "goal_count": goal_count,
        "total_steps": total_steps,
        "total_resources": total_resources,
        "total_failures": total_failures,
        "total_idle": total_idle,
    }
