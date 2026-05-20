const path = require("path");
const fs = require("fs");
const { spawn } = require("child_process");
const mineflayer = require("mineflayer");
const { pathfinder, Movements, goals } = require("mineflayer-pathfinder");
require("dotenv").config({ path: path.resolve(__dirname, "..", ".env") });

const PROJECT_ROOT = path.resolve(__dirname, "..", "..");
const PYTHON_BRIDGE = path.resolve(__dirname, "..", "python", "planner_bridge.py");
const PYTHON_EXECUTABLE = process.env.PYTHON_EXECUTABLE || "python";
const RUNTIME_DIR = path.resolve(__dirname, "..", "runtime");
const STATUS_FILE = path.resolve(RUNTIME_DIR, "status.json");
const EVENTS_FILE = path.resolve(RUNTIME_DIR, "events.jsonl");
const TREE_BLOCKS = new Set([
  "log",
  "oak_log",
  "birch_log",
  "spruce_log",
  "jungle_log",
  "acacia_log",
  "dark_oak_log"
]);
const LEAF_BLOCKS = new Set([
  "leaves",
  "oak_leaves",
  "birch_leaves",
  "spruce_leaves",
  "jungle_leaves",
  "acacia_leaves",
  "dark_oak_leaves"
]);
const TREE_HINT_BLOCKS = new Set([...TREE_BLOCKS, ...LEAF_BLOCKS]);
const CROP_BLOCKS = new Set(["wheat", "potatoes", "carrots"]);
const PASSIVE_FOOD_MOBS = new Set(["cow", "pig", "chicken", "sheep", "rabbit"]);
const WATER_BLOCKS = new Set(["water", "flowing_water"]);

const memory = [];
let tickCounter = 0;
let pending = false;
let pyBuffer = "";
let defaultMoves = null;
let exploreTurnIndex = 0;
let lastExploreSignature = null;
let repeatedExploreCount = 0;
let lastAction = null;
let lastActionSuccess = null;

ensureRuntimeDir();

const bot = mineflayer.createBot({
  host: process.env.MC_HOST || "127.0.0.1",
  port: Number(process.env.MC_PORT || "25565"),
  username: process.env.MC_USERNAME || "llm-agent",
  password: process.env.MC_PASSWORD || undefined,
  auth: process.env.MC_AUTH || "offline",
  version: process.env.MC_VERSION || false
});
bot.loadPlugin(pathfinder);

const planner = spawn(PYTHON_EXECUTABLE, [PYTHON_BRIDGE], {
  cwd: PROJECT_ROOT,
  env: {
    ...process.env,
    PYTHONIOENCODING: "utf-8"
  },
  stdio: ["pipe", "pipe", "pipe"]
});

planner.stdout.setEncoding("utf8");
planner.stderr.setEncoding("utf8");

planner.stdout.on("data", (chunk) => {
  pyBuffer += chunk;
  let newlineIndex = pyBuffer.indexOf("\n");
  while (newlineIndex >= 0) {
    const line = pyBuffer.slice(0, newlineIndex).trim();
    pyBuffer = pyBuffer.slice(newlineIndex + 1);
    if (line) {
      handlePlannerResponse(line).catch((error) => {
        console.error("[planner-response-error]", error);
        pending = false;
      });
    }
    newlineIndex = pyBuffer.indexOf("\n");
  }
});

planner.stderr.on("data", (chunk) => {
  console.error("[python-stderr]", chunk.trim());
});

planner.on("exit", (code) => {
  console.error("[python-exit]", code);
});

bot.once("spawn", () => {
  defaultMoves = new Movements(bot);
  bot.pathfinder.setMovements(defaultMoves);
  console.log("[minecraft] bot spawned");
  recordEvent("spawn", { username: bot.username });
});

bot.on("error", (error) => {
  console.error("[minecraft-error]", error.message);
  recordEvent("bot_error", { message: error.message });
});

bot.on("end", () => {
  console.log("[minecraft] disconnected");
  writeStatus({ state: "disconnected" });
});

bot.on("health", () => {
  writeStatus(buildStatusPayload("health_update"));
});

bot.on("playerCollect", (collector, itemDrop) => {
  if (!bot.entity || collector !== bot.entity) {
    return;
  }
  recordEvent("item_collect", {
    itemEntityId: itemDrop ? itemDrop.id : null
  });
});

bot.on("physicsTick", async () => {
  if (!bot.entity || pending) {
    return;
  }

  tickCounter += 1;
  if (tickCounter % 20 !== 0) {
    return;
  }

  pending = true;
  try {
    const observation = buildObservation();
    const request = {
      type: "plan",
      tick: tickCounter,
      observation,
      memory: memory.slice(-8)
    };
    writeStatus(buildStatusPayload("planning", observation));
    planner.stdin.write(JSON.stringify(request) + "\n");
  } catch (error) {
    pending = false;
    console.error("[observation-error]", error);
    recordEvent("observation_error", { message: error.message });
  }
});

function buildObservation() {
  const frontBlock = blockAtOffset(0, 0, 1);
  const belowBlock = blockAtOffset(0, -1, 0);
  const aboveBlock = blockAtOffset(0, 1, 0);
  const heldItem = bot.heldItem ? bot.heldItem.name : null;
  const nearestTree = findNearestBlock(TREE_BLOCKS, 64);
  const nearestLeaves = findNearestBlock(LEAF_BLOCKS, 64);
  const nearestFood = findNearestFoodSource();
  const inventorySummary = summarizeInventory();
  const recentFailures = memory.filter((entry) => entry.includes(" -> fail:")).slice(-4);
  const woodCount = countInventoryMatching(inventorySummary, [
    "log",
    "oak_log",
    "birch_log",
    "spruce_log",
    "jungle_log",
    "acacia_log",
    "dark_oak_log"
  ]);
  const edibleCount = countEdibleItems(inventorySummary);

  return {
    health: bot.health,
    food: bot.food,
    yaw: bot.entity.yaw,
    time_of_day: bot.time.timeOfDay,
    held_item: heldItem,
    position: {
      x: round(bot.entity.position.x),
      y: round(bot.entity.position.y),
      z: round(bot.entity.position.z)
    },
    inventory_summary: inventorySummary,
    resource_summary: {
      wood_count: woodCount,
      edible_count: edibleCount
    },
    nearby_blocks: {
      front: frontBlock ? frontBlock.name : null,
      below: belowBlock ? belowBlock.name : null,
      above: aboveBlock ? aboveBlock.name : null
    },
    visible_targets: {
      nearest_tree: nearestTree
        ? {
            name: nearestTree.name,
            distance: distanceTo(nearestTree.position)
          }
        : null,
      nearest_leaves: nearestLeaves
        ? {
            name: nearestLeaves.name,
            distance: distanceTo(nearestLeaves.position)
          }
        : null,
      nearest_food_source: nearestFood
        ? {
            name: nearestFood.name,
            distance: distanceTo(nearestFood.position),
            source_type: nearestFood.sourceType
          }
        : null
    },
    target_summary: {
      tree_detected: Boolean(nearestTree || nearestLeaves),
      food_source_detected: Boolean(nearestFood),
      food_source_type: nearestFood ? nearestFood.sourceType : null,
      reachable_frontier_open: isForwardTraversable(frontBlock)
    },
    survival_state: {
      status: classifySurvivalState(bot.health, bot.food),
      needs_attention: bot.food <= 8 || bot.health <= 12
    },
    execution_context: {
      tick: tickCounter,
      repeated_failures: recentFailures.length,
      recent_failures: recentFailures,
      explore_stuck: isExploreStuck(),
      last_action: lastAction,
      last_action_success: lastActionSuccess
    },
    goal: "Gather wood and survive"
  };
}

async function handlePlannerResponse(line) {
  let response;
  try {
    response = JSON.parse(line);
  } catch (error) {
    console.error("[planner-json-error]", line);
    pending = false;
    return;
  }

  if (response.error) {
    console.error("[planner-error]", response.details || response.error);
    pending = false;
    return;
  }

  const action = String(response.action || "observe");
  const thought = String(response.thought || "");
  const result = await executeAction(action);
  lastAction = action;
  lastActionSuccess = result.success;
  memory.push(`${action} -> ${result.success ? "success" : "fail"}: ${result.feedback}`);

  console.log("[plan]", JSON.stringify({ thought, action, feedback: result.feedback }));
  recordEvent("planner_step", { thought, action, feedback: result.feedback, success: result.success });
  writeStatus(buildStatusPayload("action_complete"));
  pending = false;
}

async function executeAction(action) {
  try {
    if (action === "observe") {
      return { success: true, feedback: "Observation refreshed." };
    }

    if (action === "stop") {
      stopMovement();
      bot.pathfinder.setGoal(null);
      return { success: true, feedback: "Movement stopped." };
    }

    if (action === "report:status") {
      writeStatus(buildStatusPayload("status_report"));
      return { success: true, feedback: "Status report refreshed." };
    }

    if (action === "reorient") {
      stopMovement();
      await turnExploreHeading();
      writeStatus(buildStatusPayload("reoriented"));
      return { success: true, feedback: "Heading rotated to search a new direction." };
    }

    if (action === "explore") {
      const success = await handleExplore();
      return success
        ? { success: true, feedback: "Exploration step completed." }
        : { success: false, feedback: "Exploration failed to find a traversable move." };
    }

    if (action === "collect:wood") {
      const success = await handleCollectWood();
      return success
        ? { success: true, feedback: "Collected nearby wood." }
        : { success: false, feedback: "No reachable wood target found." };
    }

    if (action === "collect:food") {
      const success = await handleCollectFood();
      return success
        ? { success: true, feedback: "Collected or recovered food supply." }
        : { success: false, feedback: "No reachable food source or edible item found." };
    }

    if (action.startsWith("chat:")) {
      const message = action.slice("chat:".length);
      bot.chat(message);
      return { success: true, feedback: `Sent chat message: ${message}` };
    }

    if (action.startsWith("look:")) {
      await handleLook(action.slice("look:".length));
      return { success: true, feedback: `Looked ${action.slice("look:".length)}.` };
    }

    if (action.startsWith("move:")) {
      await handleMove(action.slice("move:".length));
      return { success: true, feedback: `Moved ${action.slice("move:".length)}.` };
    }

    if (action === "jump") {
      await pulseControl("jump", 350);
      return { success: true, feedback: "Jumped once." };
    }

    if (action === "mine:block" || action === "collect:block") {
      const success = await handleMineNearest();
      return success
        ? { success: true, feedback: "Mined target block." }
        : { success: false, feedback: "No suitable nearby block to mine." };
    }

    if (action === "eat") {
      const success = await handleEat();
      return success
        ? { success: true, feedback: "Ate available food." }
        : { success: false, feedback: "No edible item available." };
    }

    return { success: false, feedback: `Unsupported action: ${action}` };
  } catch (error) {
    return { success: false, feedback: `Action failed: ${error.message}` };
  }
}

async function handleMove(direction) {
  const allowed = ["forward", "back", "left", "right"];
  if (!allowed.includes(direction)) {
    throw new Error(`Unknown movement direction: ${direction}`);
  }
  await pulseControl(direction, 500);
}

async function handleLook(direction) {
  const yawMap = {
    south: 0,
    west: Math.PI / 2,
    north: Math.PI,
    east: -Math.PI / 2
  };
  if (!(direction in yawMap)) {
    throw new Error(`Unknown look direction: ${direction}`);
  }
  await bot.look(yawMap[direction], 0, true);
}

async function handleMineNearest() {
  const targets = new Set([...TREE_BLOCKS, "stone", "coal_ore"]);
  const block = bot.findBlock({
    maxDistance: 4,
    matching: (candidate) => candidate && targets.has(candidate.name)
  });
  if (!block) {
    return false;
  }
  await bot.lookAt(block.position.offset(0.5, 0.5, 0.5), true);
  await bot.dig(block, true);
  return true;
}

async function handleCollectWood() {
  const target = findNearestTreeTarget(64);
  if (!target) {
    return false;
  }

  if (distanceTo(target.position) <= 4.5) {
    await mineTreeCluster(target);
    return true;
  }

  const adjacent = nearestStandableNeighbor(target);
  if (adjacent) {
    const goal = new goals.GoalNear(adjacent.x, adjacent.y, adjacent.z, 1);
    await bot.pathfinder.goto(goal);
    await bot.lookAt(target.position.offset(0.5, 0.5, 0.5), true);
    await mineTreeCluster(target);
    return true;
  }

  await bot.pathfinder.goto(new goals.GoalNear(target.position.x, target.position.y, target.position.z, 2));
  await mineTreeCluster(target);
  return true;
}

async function handleEat() {
  const item = bot.inventory.items().find((entry) => entry && entry.foodPoints);
  if (!item) {
    return false;
  }
  await bot.equip(item, "hand");
  await bot.consume();
  return true;
}

async function pulseControl(control, durationMs) {
  bot.pathfinder.setGoal(null);
  stopMovement();
  bot.setControlState(control, true);
  await sleep(durationMs);
  bot.setControlState(control, false);
}

function stopMovement() {
  ["forward", "back", "left", "right", "jump", "sprint"].forEach((key) => {
    bot.setControlState(key, false);
  });
}

function blockAtOffset(dx, dy, dz) {
  if (!bot.entity) {
    return null;
  }
  const origin = bot.entity.position.floored();
  return bot.blockAt(origin.offset(dx, dy, dz));
}

function summarizeInventory() {
  const summary = {};
  for (const item of bot.inventory.items()) {
    summary[item.name] = (summary[item.name] || 0) + item.count;
  }
  return summary;
}

async function handleExplore() {
  const nearestTree = findNearestTreeTarget(64);
  if (nearestTree) {
    const adjacent = nearestStandableNeighbor(nearestTree);
    if (adjacent) {
      await bot.pathfinder.goto(new goals.GoalNear(adjacent.x, adjacent.y, adjacent.z, 1));
      return true;
    }
  }

  if (isExploreStuck()) {
    await turnExploreHeading();
  }

  const forwardBlock = blockAtOffset(0, 0, 1);
  if (forwardBlock && forwardBlock.name !== "water" && forwardBlock.name !== "lava") {
    await pulseControl("forward", 700);
    updateExploreSignature();
    return true;
  }

  await turnExploreHeading();
  await pulseControl("forward", 450);
  updateExploreSignature();
  return true;
}

async function handleCollectFood() {
  const edibleBefore = countEdibleItems(summarizeInventory());
  if (await handleEat()) {
    return true;
  }

  const foodTarget = findNearestFoodSource();
  if (!foodTarget) {
    return false;
  }

  if (foodTarget.sourceType === "crop") {
    return harvestCropTarget(foodTarget.block, edibleBefore);
  }

  if (foodTarget.sourceType === "animal") {
    return huntFoodMob(foodTarget.entity, edibleBefore);
  }

  if (distanceTo(foodTarget.position) <= 4.5) {
    const nearbyDropsCollected = await collectNearbyFoodDrops(3);
    if (nearbyDropsCollected || edibleInventoryIncreased(edibleBefore)) {
      return true;
    }
  }

  const adjacent = nearestStandableNeighbor(foodTarget.block || { position: foodTarget.position });
  if (adjacent) {
    await bot.pathfinder.goto(new goals.GoalNear(adjacent.x, adjacent.y, adjacent.z, 1));
    const collected = await collectNearbyFoodDrops(2);
    return collected || edibleInventoryIncreased(edibleBefore);
  }

  await bot.pathfinder.goto(new goals.GoalNear(foodTarget.position.x, foodTarget.position.y, foodTarget.position.z, 2));
  const collected = await collectNearbyFoodDrops(2);
  return collected || edibleInventoryIncreased(edibleBefore);
}

async function harvestCropTarget(block, edibleBefore) {
  if (!block) {
    return false;
  }

  const liveBlock = bot.blockAt(block.position);
  if (!liveBlock) {
    return false;
  }

  if (distanceTo(liveBlock.position) > 4.5) {
    const adjacent = nearestStandableNeighbor(liveBlock);
    if (adjacent) {
      await bot.pathfinder.goto(new goals.GoalNear(adjacent.x, adjacent.y, adjacent.z, 1));
    }
  }

  await bot.lookAt(liveBlock.position.offset(0.5, 0.5, 0.5), true);
  await bot.dig(liveBlock, true);
  await sleep(400);
  await collectNearbyItemDrops(6, () => true, 3);

  if (edibleInventoryIncreased(edibleBefore)) {
    return true;
  }

  const replantedSeed = findNearestMatureCrop(10);
  if (replantedSeed && replantedSeed.position.equals(liveBlock.position)) {
    return false;
  }

  const secondPass = await collectNearbyItemDrops(6, () => true, 2);
  return secondPass || edibleInventoryIncreased(edibleBefore);
}

async function huntFoodMob(entity, edibleBefore) {
  if (!entity || !entity.position) {
    return false;
  }

  const entityHeight = entity.height || 1;
  for (let attempt = 0; attempt < 4; attempt += 1) {
    if (!entity.isValid) {
      break;
    }
    await bot.pathfinder.goto(new goals.GoalNear(entity.position.x, entity.position.y, entity.position.z, 1));
    await bot.lookAt(entity.position.offset(0, entityHeight, 0), true);
    bot.attack(entity);
    await sleep(500);
  }

  await collectNearbyFoodDrops(4);
  if (edibleInventoryIncreased(edibleBefore)) {
    return true;
  }

  const backupDropSweep = await collectNearbyItemDrops(10, (drop) => {
    const itemName = resolveDroppedItemName(drop);
    return itemName ? isFoodItemName(itemName) : true;
  }, 3);
  return backupDropSweep || edibleInventoryIncreased(edibleBefore);
}

async function mineTreeCluster(seedBlock) {
  const stack = [seedBlock];
  const visited = new Set();

  while (stack.length > 0) {
    const block = stack.pop();
    if (!block) {
      continue;
    }

    const key = block.position.toString();
    if (visited.has(key)) {
      continue;
    }
    visited.add(key);

    const liveBlock = bot.blockAt(block.position);
    if (!liveBlock || !TREE_BLOCKS.has(liveBlock.name)) {
      continue;
    }

    if (distanceTo(liveBlock.position) > 4.5) {
      const adjacent = nearestStandableNeighbor(liveBlock);
      if (adjacent) {
        await bot.pathfinder.goto(new goals.GoalNear(adjacent.x, adjacent.y, adjacent.z, 1));
      }
    }

    await bot.lookAt(liveBlock.position.offset(0.5, 0.5, 0.5), true);
    await bot.dig(liveBlock, true);
    await sleep(250);

    for (const neighbor of cubeNeighbors(liveBlock.position)) {
      const nextBlock = bot.blockAt(neighbor);
      if (nextBlock && TREE_BLOCKS.has(nextBlock.name)) {
        stack.push(nextBlock);
      }
    }
  }
}

function nearestStandableNeighbor(block) {
  const candidates = [
    block.position.offset(1, 0, 0),
    block.position.offset(-1, 0, 0),
    block.position.offset(0, 0, 1),
    block.position.offset(0, 0, -1)
  ];

  let best = null;
  let bestDistance = Infinity;

  for (const pos of candidates) {
    const feet = bot.blockAt(pos);
    const head = bot.blockAt(pos.offset(0, 1, 0));
    const below = bot.blockAt(pos.offset(0, -1, 0));
    const passableFeet = !feet || feet.name === "air" || feet.boundingBox === "empty";
    const passableHead = !head || head.name === "air" || head.boundingBox === "empty";
    const solidBelow = below && below.boundingBox === "block";
    if (!passableFeet || !passableHead || !solidBelow) {
      continue;
    }

    const dist = distanceTo(pos);
    if (dist < bestDistance) {
      bestDistance = dist;
      best = pos;
    }
  }

  return best;
}

function findNearestBlock(targets, maxDistance) {
  return bot.findBlock({
    maxDistance,
    matching: (candidate) => candidate && targets.has(candidate.name)
  });
}

function findNearestFoodSource() {
  const cropTarget = findNearestMatureCrop(48);
  const animalTarget = findNearestFoodMob(32);
  const waterTarget = bot.findBlock({
    maxDistance: 48,
    matching: (candidate) => candidate && WATER_BLOCKS.has(candidate.name)
  });

  const candidates = [];
  if (cropTarget) {
    candidates.push({
      sourceType: "crop",
      name: cropTarget.name,
      position: cropTarget.position,
      block: cropTarget,
      score: distanceTo(cropTarget.position)
    });
  }
  if (animalTarget) {
    candidates.push({
      sourceType: "animal",
      name: animalTarget.name,
      position: animalTarget.position,
      entity: animalTarget,
      score: distanceTo(animalTarget.position) + 1
    });
  }
  if (waterTarget) {
    candidates.push({
      sourceType: "water",
      name: waterTarget.name,
      position: waterTarget.position,
      block: waterTarget,
      score: distanceTo(waterTarget.position) + 4
    });
  }

  candidates.sort((a, b) => a.score - b.score);
  return candidates[0] || null;
}

function findNearestTreeTarget(maxDistance) {
  const directLog = findNearestBlock(TREE_BLOCKS, maxDistance);
  if (directLog) {
    return directLog;
  }

  const leaves = findNearestBlock(LEAF_BLOCKS, maxDistance);
  if (!leaves) {
    return null;
  }

  const base = leaves.position;
  for (let dy = 0; dy <= 6; dy += 1) {
    for (let dx = -3; dx <= 3; dx += 1) {
      for (let dz = -3; dz <= 3; dz += 1) {
        const candidate = bot.blockAt(base.offset(dx, -dy, dz));
        if (candidate && TREE_BLOCKS.has(candidate.name)) {
          return candidate;
        }
      }
    }
  }

  return leaves;
}

function cubeNeighbors(position) {
  const offsets = [
    [1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]
  ];
  return offsets.map(([dx, dy, dz]) => position.offset(dx, dy, dz));
}

function distanceTo(position) {
  if (!bot.entity) {
    return null;
  }
  return round(bot.entity.position.distanceTo(position));
}

async function turnExploreHeading() {
  const headings = [0, -Math.PI / 2, Math.PI, Math.PI / 2];
  exploreTurnIndex = (exploreTurnIndex + 1) % headings.length;
  await bot.look(headings[exploreTurnIndex], 0, true);
}

function updateExploreSignature() {
  if (!bot.entity) {
    return;
  }
  const pos = bot.entity.position;
  const signature = `${Math.round(pos.x)}:${Math.round(pos.y)}:${Math.round(pos.z)}`;
  if (signature === lastExploreSignature) {
    repeatedExploreCount += 1;
  } else {
    repeatedExploreCount = 0;
    lastExploreSignature = signature;
  }
}

function isExploreStuck() {
  return repeatedExploreCount >= 2;
}

function findNearestMatureCrop(maxDistance) {
  return bot.findBlock({
    maxDistance,
    matching: (candidate) => candidate && isMatureCrop(candidate)
  });
}

function findNearestFoodMob(maxDistance) {
  return bot.nearestEntity((entity) => {
    if (!entity || !entity.position || entity.type !== "mob") {
      return false;
    }
    if (!PASSIVE_FOOD_MOBS.has(entity.name)) {
      return false;
    }
    return bot.entity.position.distanceTo(entity.position) <= maxDistance;
  });
}

function isMatureCrop(block) {
  if (!block || !CROP_BLOCKS.has(block.name)) {
    return false;
  }
  return block.metadata >= 7;
}

async function collectNearbyFoodDrops(maxAttempts = 2) {
  return collectNearbyItemDrops(6, (entity) => {
    const itemName = resolveDroppedItemName(entity);
    if (!itemName) {
      return false;
    }
    return isFoodItemName(itemName);
  }, maxAttempts);
}

async function collectNearbyItemDrops(maxDistance, filterFn, maxAttempts = 2) {
  let collected = false;
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const target = bot.nearestEntity((entity) => {
      if (!entity || entity.name !== "item" || !entity.position) {
        return false;
      }
      if (bot.entity.position.distanceTo(entity.position) > maxDistance) {
        return false;
      }
      return filterFn ? filterFn(entity) : true;
    });

    if (!target) {
      break;
    }

    await bot.pathfinder.goto(new goals.GoalNear(target.position.x, target.position.y, target.position.z, 1));
    await sleep(300);
    collected = true;
  }
  return collected;
}

function resolveDroppedItemName(entity) {
  if (!entity || !entity.metadata) {
    return null;
  }
  const metadataEntry = entity.metadata.find((entry) => entry && typeof entry === "object" && "itemId" in entry);
  if (metadataEntry && metadataEntry.nbtData && metadataEntry.nbtData.value && metadataEntry.nbtData.value.id) {
    return String(metadataEntry.nbtData.value.id.value || "");
  }
  return null;
}

function isFoodItemName(name) {
  const foodKeywords = ["beef", "porkchop", "bread", "apple", "potato", "salmon", "cod", "fish", "chicken", "mutton", "rabbit"];
  return foodKeywords.some((keyword) => name.includes(keyword));
}

function countInventoryMatching(summary, candidates) {
  let total = 0;
  for (const [name, count] of Object.entries(summary)) {
    if (candidates.includes(name)) {
      total += count;
    }
  }
  return total;
}

function countEdibleItems(summary) {
  const foodKeywords = ["beef", "porkchop", "bread", "apple", "potato", "salmon", "cod", "fish", "chicken"];
  let total = 0;
  for (const [name, count] of Object.entries(summary)) {
    if (foodKeywords.some((keyword) => name.includes(keyword))) {
      total += count;
    }
  }
  return total;
}

function edibleInventoryIncreased(beforeCount) {
  return countEdibleItems(summarizeInventory()) > beforeCount;
}

function classifySurvivalState(health, food) {
  if (health <= 8 || food <= 6) {
    return "unstable";
  }
  if (health <= 14 || food <= 10) {
    return "watch";
  }
  return "stable";
}

function isForwardTraversable(frontBlock) {
  return !frontBlock || (frontBlock.name !== "lava" && frontBlock.boundingBox !== "block");
}

function buildStatusPayload(state, observation) {
  const snapshot = observation || (bot.entity ? buildObservation() : null);
  return {
    state,
    tick: tickCounter,
    connected: Boolean(bot.player),
    username: bot.username,
    timestamp: new Date().toISOString(),
    observation: snapshot,
    memory_tail: memory.slice(-8)
  };
}

function ensureRuntimeDir() {
  fs.mkdirSync(RUNTIME_DIR, { recursive: true });
}

function writeStatus(payload) {
  fs.writeFileSync(STATUS_FILE, JSON.stringify(payload, null, 2), "utf8");
}

function recordEvent(type, payload) {
  const line = JSON.stringify({
    type,
    timestamp: new Date().toISOString(),
    payload
  });
  fs.appendFileSync(EVENTS_FILE, line + "\n", "utf8");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function round(value) {
  return Math.round(value * 100) / 100;
}
