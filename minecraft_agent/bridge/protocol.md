# Bridge Protocol

The Node process and Python process communicate through line-delimited JSON.

## Request

```json
{
  "type": "plan",
  "tick": 12,
  "observation": {
    "health": 20,
    "food": 18,
    "position": {"x": 10, "y": 64, "z": -3},
    "yaw": 90,
    "time_of_day": 6000,
    "held_item": "oak_log",
    "inventory_summary": {"oak_log": 3, "dirt": 12},
    "nearby_blocks": {
      "front": "grass_block",
      "below": "grass_block",
      "above": "air"
    },
    "goal": "Gather wood and survive"
  },
  "memory": [
    "move:forward -> success: advanced one block"
  ]
}
```

## Response

```json
{
  "thought": "A tree block is nearby and wood is still useful, so collect it.",
  "action": "mine:block"
}
```

## Error Response

```json
{
  "error": "Planner failed",
  "details": "..."
}
```
