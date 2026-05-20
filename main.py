from __future__ import annotations

import argparse
import json

from src.game_agent.agent import GameAgent
from src.game_agent.environment import OpenWorldEnv
from src.game_agent.evaluator import batch_evaluate
from src.game_agent.llm import OpenAICompatiblePlanner, Planner, RuleBasedPlanner
from src.game_agent.scenario import built_in_scenarios


def build_planner(planner_name: str) -> Planner:
    if planner_name == "rule":
        return RuleBasedPlanner()
    if planner_name == "openai":
        return OpenAICompatiblePlanner()
    raise ValueError(f"Unsupported planner: {planner_name}")


def run_demo(planner: Planner, scenario_name: str, max_steps: int) -> None:
    scenario = built_in_scenarios()[scenario_name]
    env = OpenWorldEnv(seed=7, scenario=scenario)
    agent = GameAgent(planner=planner, memory_size=8)
    result = agent.run_episode(env=env, max_steps=max_steps, verbose=True)

    print("\n=== Demo Summary ===")
    print(f"scenario: {scenario_name}")
    print(f"success: {result.success}")
    print(f"steps: {result.steps}")
    print(f"hp: {result.final_hp}")
    print(f"hunger: {result.final_hunger}")
    print(f"inventory: {result.inventory}")
    print(f"collected: {result.collected}")
    print(f"final_position: {result.final_position}")
    print(f"goal_achieved: {result.goal_achieved}")


def run_evaluation(
    planner: Planner,
    scenario_names: list[str],
    episodes: int,
    max_steps: int,
    report_file: str | None,
) -> None:
    print("\n=== Batch Evaluation ===")
    report = batch_evaluate(
        episodes=episodes,
        max_steps=max_steps,
        planner=planner,
        scenario_names=scenario_names,
        report_file=report_file,
    )
    headline = {
        key: value
        for key, value in report.items()
        if key not in {"scenarios"}
    }
    print(json.dumps(headline, ensure_ascii=False, indent=2))
    print("scenario_breakdown:")
    for item in report["scenarios"]:
        compact = {
            "name": item["name"],
            "survival_rate": item["survival_rate"],
            "goal_rate": item["goal_rate"],
            "avg_steps": item["avg_steps"],
        }
        print(json.dumps(compact, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LLM Game Agent reproduction runner")
    parser.add_argument("--planner", choices=["rule", "openai"], default="rule")
    parser.add_argument("--scenario", choices=list(built_in_scenarios().keys()), default="standard")
    parser.add_argument("--episodes", type=int, default=20)
    parser.add_argument("--max-steps", type=int, default=50)
    parser.add_argument("--report-file", default="outputs/latest_report.json")
    parser.add_argument("--skip-demo", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    planner = build_planner(args.planner)
    if not args.skip_demo:
        run_demo(planner=planner, scenario_name=args.scenario, max_steps=args.max_steps)
    run_evaluation(
        planner=planner,
        scenario_names=list(built_in_scenarios().keys()),
        episodes=args.episodes,
        max_steps=args.max_steps,
        report_file=args.report_file,
    )
