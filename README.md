# LLM Game Agent 复现与升级版

这是对简历项目“面向开放世界游戏的大模型决策智能体(LLM Game Agent)研发”的一个可运行复现版本，并在最小 demo 基础上继续升级为更接近正式项目的形态，重点还原以下三部分能力：

- `Observation -> Thought -> Action` 的 ReAct 决策闭环
- 基于“动作-反馈”对的滑动短记忆与失败反思
- 面向开放世界任务的批量评测体系
- 可切换 `rule / openai-compatible` planner
- 多场景批量实验与 JSON 报告导出

## 项目结构

```text
src/game_agent/
  agent.py         # ReAct Agent 主循环
  environment.py   # 开放世界网格环境
  evaluator.py     # 批量评测
  llm.py           # 可插拔策略器，支持规则版与 OpenAI 兼容接口
  memory.py        # 动作-反馈短记忆
  scenario.py      # 场景配置
main.py            # 运行入口
```

## 运行方式

```bash
python main.py
```

或指定参数：

```bash
python main.py --planner rule --scenario standard --episodes 20 --max-steps 50
```

你会看到：

- 单局 demo 的逐步推理日志
- 批量评测结果
- `outputs/latest_report.json` 实验报告

## OpenAI 兼容接口

如果你要接真实大模型，可使用：

```bash
set OPENAI_API_KEY=your_key
set OPENAI_MODEL=gpt-4.1-mini
python main.py --planner openai
```

也支持自定义兼容网关：

```bash
set OPENAI_BASE_URL=https://your-endpoint/v1
```

### DeepSeek 直连

这个项目的 `openai` planner 也支持 DeepSeek 的 OpenAI 兼容接口。可直接这样运行：

```bash
set DEEPSEEK_API_KEY=your_key
set DEEPSEEK_MODEL=deepseek-v4-flash
set DEEPSEEK_BASE_URL=https://api.deepseek.com
python main.py --planner openai
```

如果你的网络较慢，也可以调高超时：

```bash
set OPENAI_TIMEOUT=120
```

## 设计说明

### 1. 游戏环境感知

环境是一个简化开放世界：

- 地图包含 `plain / forest / quarry / river / shelter / danger`
- Agent 需要管理 `hunger / energy / hp / inventory / position`
- 目标不是单点通关，而是长线生存与资源规划

### 2. ReAct 决策闭环

每一步都执行：

1. 从环境提取结构化 Observation
2. 结合短记忆生成 Thought
3. 输出 Action
4. 根据环境反馈进行反思和纠偏

### 3. 短记忆与反思

记忆窗口保存最近的“动作-反馈”对，用于避免：

- 重复无效动作
- 在危险区原地打转
- 遗忘中期目标

如果动作失败，Agent 会生成一条 `reflection`，后续决策优先规避同类错误。

### 4. 多场景评测

内置三个场景：

- `standard`：标准开放世界生存图
- `harsh`：危险区更多，强调容错
- `explorer`：路径更长，强调导航与任务切换

### 5. 评测指标

批量评测输出：

- `survival_rate`：存活率
- `goal_rate`：完成生存目标比例
- `resource_utilization`：资源获取效率
- `path_efficiency`：有效移动占比
- `logic_coherence`：避免重复失败与空转的比例

## 说明

这个版本是“项目能力复现 + 工程升级版”，不是某个商用游戏的逆向接入版本，因此使用了可控的自建环境来稳定复现智能体工作流、记忆机制和评测逻辑。它已经具备进一步扩展到：

- 真实 LLM API 接入
- 更复杂地图生成
- Prompt ablation 对比实验
- 面试展示用实验报告
