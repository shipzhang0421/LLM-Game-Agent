# LLM Game Agent 面试材料包

这个目录包含了项目 `面向开放世界游戏的大模型决策智能体（LLM Game Agent）研发` 的完整中文面试材料，适合用于：

- 简历项目深挖
- 技术面试讲解
- 复盘项目设计思路
- 答辩式展示

## 文件说明

- `llm_game_agent_report.md`
  项目超详细报告。内容覆盖项目背景、Agent 基础知识、系统架构、核心方法、关键代码、调试过程、评测体系、Minecraft 接入、LangChain 风格重构，以及面试时如何讲述这个项目。

- `interview_qa.md`
  更新后的面试高频追问题库与标准回答。覆盖项目理解、Agent 原理、Grid-world、Minecraft、LangChain、评测、边界问题与诚实回答方式。

- `architecture_and_flow.md`
  面试讲解图与执行链路说明。包含 Mermaid 架构图、执行流程图、Minecraft 资源循环图，以及每张图配套的讲解口径。

## 推荐使用方式

- 如果你只有 `2-3 分钟`
  先看 `llm_game_agent_report.md` 里的项目定位、核心问题和 3 分钟讲解版本。

- 如果你有 `5-10 分钟`
  用 `architecture_and_flow.md` 按图讲解，效果最好。

- 如果你预计会被深挖
  重点熟悉 `interview_qa.md`，尤其是 Minecraft 接入、记忆机制、评测指标和 LangChain 部分。

## 建议讲述顺序

1. 先讲问题背景
   大模型在开放世界任务中容易出现目标遗忘、决策发散和逻辑死循环。
2. 再讲核心闭环
   `Observation -> Thought -> Action -> Feedback -> Memory`
3. 然后讲系统演进
   Grid-world 复现版 -> Minecraft 真实环境版 -> LangChain 风格重构版
4. 最后强调你真正做的工作
   状态建模、动作约束、记忆设计、失败反思、评测体系和真实环境接入
