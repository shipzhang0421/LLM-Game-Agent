from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


Position = Tuple[int, int]
Grid = List[List[str]]


@dataclass(frozen=True)
class ScenarioConfig:
    name: str
    description: str
    grid: Grid
    start: Position
    shelter: Position
    goal: Dict[str, int | bool]
    initial_hp: int = 10
    initial_hunger: int = 8
    initial_energy: int = 8
    resource_sites: Dict[str, List[Position]] = field(default_factory=dict)


def _resource_sites_from_grid(grid: Grid, shelter: Position) -> Dict[str, List[Position]]:
    sites: Dict[str, List[Position]] = {
        "forest": [],
        "quarry": [],
        "river": [],
        "danger": [],
        "shelter": [shelter],
    }
    for y, row in enumerate(grid):
        for x, tile in enumerate(row):
            if tile in sites and tile != "shelter":
                sites[tile].append((x, y))
    return sites


def built_in_scenarios() -> Dict[str, ScenarioConfig]:
    standard_grid = [
        ["plain", "forest", "plain", "river", "plain", "danger"],
        ["plain", "forest", "plain", "river", "plain", "plain"],
        ["plain", "plain", "quarry", "plain", "danger", "plain"],
        ["river", "plain", "quarry", "plain", "forest", "plain"],
        ["plain", "danger", "plain", "plain", "forest", "plain"],
        ["plain", "plain", "plain", "quarry", "plain", "shelter"],
    ]
    standard_shelter = (5, 5)

    harsh_grid = [
        ["plain", "forest", "danger", "river", "plain", "danger"],
        ["plain", "forest", "plain", "river", "plain", "plain"],
        ["danger", "plain", "quarry", "plain", "danger", "plain"],
        ["river", "plain", "quarry", "plain", "forest", "plain"],
        ["plain", "danger", "plain", "danger", "forest", "plain"],
        ["plain", "plain", "plain", "quarry", "plain", "shelter"],
    ]
    harsh_shelter = (5, 5)

    explorer_grid = [
        ["plain", "plain", "forest", "river", "plain", "danger"],
        ["plain", "forest", "plain", "plain", "plain", "plain"],
        ["plain", "plain", "quarry", "danger", "forest", "plain"],
        ["river", "plain", "plain", "plain", "forest", "plain"],
        ["plain", "danger", "plain", "quarry", "plain", "plain"],
        ["plain", "plain", "plain", "plain", "river", "shelter"],
    ]
    explorer_shelter = (5, 5)

    scenarios = [
        ScenarioConfig(
            name="standard",
            description="Balanced open-world survival map for the default reproduction.",
            grid=standard_grid,
            start=(0, 0),
            shelter=standard_shelter,
            goal={"wood": 2, "stone": 2, "food": 2, "reach_shelter": True},
            resource_sites=_resource_sites_from_grid(standard_grid, standard_shelter),
        ),
        ScenarioConfig(
            name="harsh",
            description="Higher-risk map with more danger tiles and lower initial hunger.",
            grid=harsh_grid,
            start=(0, 0),
            shelter=harsh_shelter,
            goal={"wood": 2, "stone": 2, "food": 2, "reach_shelter": True},
            initial_hunger=7,
            resource_sites=_resource_sites_from_grid(harsh_grid, harsh_shelter),
        ),
        ScenarioConfig(
            name="explorer",
            description="Longer travel route that emphasizes navigation and task switching.",
            grid=explorer_grid,
            start=(0, 0),
            shelter=explorer_shelter,
            goal={"wood": 2, "stone": 2, "food": 2, "reach_shelter": True},
            initial_hp=12,
            initial_hunger=9,
            initial_energy=9,
            resource_sites=_resource_sites_from_grid(explorer_grid, explorer_shelter),
        ),
    ]
    return {scenario.name: scenario for scenario in scenarios}
