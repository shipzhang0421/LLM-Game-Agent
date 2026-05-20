# Minecraft Agent Bridge

This directory is a separate Minecraft integration version of the project.
The existing grid-world demo in the repository root is intentionally left unchanged.

## What This Version Does

This version connects the existing Python planner to a real Minecraft Java server by using:

- `Mineflayer` for game connection and action execution
- a line-delimited JSON protocol over `stdin/stdout`
- the existing Python planners from `src/game_agent/llm.py`

## Directory Layout

```text
minecraft_agent/
  README.md
  package.json
  .env.example
  bridge/
    mineflayer_bot.js
    protocol.md
  python/
    planner_bridge.py
```

## High-Level Flow

1. `mineflayer_bot.js` connects to a Minecraft Java server.
2. The bot extracts a structured observation.
3. The observation is sent to `planner_bridge.py`.
4. Python runs the planner and returns `thought + action`.
5. Node executes the action in Minecraft and returns the result.

## Supported Actions in This Version

- `move:forward`
- `move:back`
- `move:left`
- `move:right`
- `jump`
- `look:north`
- `look:south`
- `look:east`
- `look:west`
- `mine:block`
- `collect:block`
- `eat`
- `chat:<message>`
- `observe`
- `stop`
- `explore`
- `collect:wood`
- `collect:food`
- `reorient`
- `report:status`

## Prerequisites

- Minecraft Java Edition
- A local or private server
- Node.js 18+
- Python 3.9+

## Install

```bash
cd minecraft_agent
npm install
```

## Configure

Copy `.env.example` and fill in your settings:

```bash
copy .env.example .env
```

Main settings:

- `MC_HOST`
- `MC_PORT`
- `MC_USERNAME`
- `MC_VERSION`
- `PLANNER_TYPE=rule`, `openai`, or `langchain`

If you use a real model:

- `DEEPSEEK_API_KEY`
- `DEEPSEEK_MODEL`
- `DEEPSEEK_BASE_URL`

## Run

```bash
node bridge/mineflayer_bot.js
```

## LangChain-Style Flow

When `PLANNER_TYPE=langchain`, the bridge now uses a more agent-like execution loop:

1. Node builds a richer observation that includes:
   - visible trees and food-source hints
   - resource counts and edible inventory count
   - survival-state classification
   - recent failures and last action context
2. Python planner chooses an immediate subgoal such as:
   - restore food loop
   - build wood reserve
   - refresh search heading
3. The bridge executes one constrained action and writes the result into memory.
4. Runtime status and memory tails are persisted for inspection.

If the local LangChain runtime is unavailable in the active Python environment, the planner degrades gracefully to the same LangChain-style guardrail policy instead of failing hard.

## First Runnable Behavior

This first runnable version is aimed at a narrow but real loop:

1. connect to a Minecraft Java server
2. observe nearby blocks and inventory
3. detect a nearby tree
4. detect nearby food-source cues when hunger becomes risky
5. path toward the tree or food source
6. prioritize mature crops, then passive food mobs, then water as a search anchor
7. harvest crops or hunt passive mobs, then actively sweep nearby food drops
8. eat available food when food or health becomes risky
9. continuously write status snapshots and event logs

## Runtime Files

After launch, the bridge writes runtime files here:

- `minecraft_agent/runtime/status.json`
- `minecraft_agent/runtime/events.jsonl`

These are useful for debugging and later building a UI monitor.

## Current Scope and Limits

- Best suited for flat or lightly obstructed spawn areas
- Assumes there are reachable logs within local exploration range
- Does not yet craft tools, sleep, fight mobs, or recover from deep navigation failures
- Intended as the first real-environment milestone, not the final Minecraft agent

## Notes

- This version is a starting bridge, not a full Voyager-style Minecraft agent yet.
- It is designed to keep the planning logic in Python and the environment control in Node.
- The first stable milestone is: connect, observe, move, mine one block, and eat food.
