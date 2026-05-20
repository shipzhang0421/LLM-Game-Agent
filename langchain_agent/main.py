from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.game_agent.agent import GameAgent
from src.game_agent.environment import OpenWorldEnv
from src.game_agent.evaluator import batch_evaluate
from src.game_agent.scenario import built_in_scenarios

from .planner import LangChainGridPlanner


def run_demo(planner: LangChainGridPlanner, scenario_name: str, max_steps: int) -> None:
    scenario = built_in_scenarios()[scenario_name]
    env = OpenWorldEnv(seed=7, scenario=scenario)
    agent = GameAgent(planner=planner, memory_size=8)
    result = agent.run_episode(env=env, max_steps=max_steps, verbose=True)

    print("\n=== LangChain Demo Summary ===")
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
    planner: LangChainGridPlanner,
    scenario_names: list[str],
    episodes: int,
    max_steps: int,
    report_file: str | None,
) -> None:
    print("\n=== LangChain Batch Evaluation ===")
    report = batch_evaluate(
        episodes=episodes,
        max_steps=max_steps,
        planner=planner,
        scenario_names=scenario_names,
        report_file=report_file,
    )
    headline = {key: value for key, value in report.items() if key not in {"scenarios"}}
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
    parser = argparse.ArgumentParser(description="LangChain-based LLM Game Agent runner")
    parser.add_argument("--scenario", choices=list(built_in_scenarios().keys()), default="standard")
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--max-steps", type=int, default=50)
    parser.add_argument("--report-file", default="outputs/langchain_report.json")
    parser.add_argument("--skip-demo", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    planner = LangChainGridPlanner()
    if not args.skip_demo:
        run_demo(planner=planner, scenario_name=args.scenario, max_steps=args.max_steps)
    run_evaluation(
        planner=planner,
        scenario_names=list(built_in_scenarios().keys()),
        episodes=args.episodes,
        max_steps=args.max_steps,
        report_file=args.report_file,
    )
