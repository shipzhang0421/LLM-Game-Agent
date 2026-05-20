# LangChain Agent Version

This directory contains a LangChain-based rewrite of the planner layer for the project.
The original grid-world and Minecraft implementations remain unchanged and usable.

## What Changed

This version upgrades the decision layer to use:

- `ChatPromptTemplate`
- `MessagesPlaceholder`
- LangChain-style tool catalogs for constrained action selection
- structured output via `with_structured_output(...)`
- OpenAI-compatible chat models through `langchain_openai.ChatOpenAI`
- guardrail fallback when the active Python environment cannot fully import the LangChain runtime

## Architecture

The environment and evaluation layers are still reused from `src/game_agent/`.
Only the planner layer is replaced.

```text
observation + memory
  -> LangChain prompt
  -> chat model
  -> structured decision schema
  -> action
  -> environment feedback
```

## Files

- `main.py`: runner for the LangChain grid-world version
- `planner.py`: LangChain planner for the grid-world environment
- `minecraft_planner.py`: LangChain planner for the Minecraft bridge
- `tools.py`: tool definitions representing the allowed action space
- `schemas.py`: structured output schemas
- `memory_adapter.py`: converts action-feedback memory into prompt messages

## Install

```bash
pip install -r langchain_agent/requirements.txt
```

## Run

```bash
python -m langchain_agent.main --scenario standard --episodes 5
```

## Environment Variables

OpenAI-compatible:

```bash
set OPENAI_API_KEY=your_key
set OPENAI_MODEL=gpt-4.1-mini
set OPENAI_BASE_URL=https://your-endpoint/v1
```

DeepSeek-compatible:

```bash
set DEEPSEEK_API_KEY=your_key
set DEEPSEEK_MODEL=deepseek-v4-flash
set DEEPSEEK_BASE_URL=https://api.deepseek.com
```

## Minecraft Bridge Integration

The Minecraft bridge also supports this version.

In `minecraft_agent/.env`, set:

```bash
PLANNER_TYPE=langchain
```

Then start the same bridge:

```bash
node minecraft_agent/bridge/mineflayer_bot.js
```

The Minecraft LangChain flow now includes:

- richer observation payloads with `survival_state`, `resource_summary`, `target_summary`, and `execution_context`
- immediate subgoals such as `restore food loop` or `build wood reserve`
- expanded constrained actions including `collect:food`, `reorient`, and `observe`
- graceful fallback to the guardrail planner when full LangChain imports are unavailable in the local Python environment
