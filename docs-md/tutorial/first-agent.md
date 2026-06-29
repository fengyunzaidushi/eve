---
title: "你的第一个 Agent"
description: "Build an Agent 教程第 1 部分。Scaffold analytics assistant，赋予它 analyst persona，运行它并提出问题。"
---

Build an Agent 教程会端到端构建一个 app：data analytics assistant。你用自然语言提问，在接下来的九个步骤中，它会学会查询 warehouse、在 sandbox 中运行 analysis、记住团队的 metric definitions，并在没有询问的情况下拒绝超出你的 query budget。

第 1 步先让它能对话。scaffold 捆绑了一个小型 sample dataset，因此你的第一个问题无需任何设置就能运行。

## 前置条件

- Node 24 或更新版本，以及 npm。
- 一个 model credential。scaffold 的默认 model 会通过 [Vercel AI Gateway](../getting-started)，因此你需要 `AI_GATEWAY_API_KEY`（或通过 `vercel link` 获取的 `VERCEL_OIDC_TOKEN`）。像 `anthropic("claude-opus-4.8")` 这样的 direct provider model 则需要该 provider 的 AI SDK package 和 key，此处是 `@ai-sdk/anthropic` 和 `ANTHROPIC_API_KEY`。

如果你以前没有运行过 eve，请先完成 [Getting Started](../getting-started)。如果没有 credential，下面的“运行 agent”会在 runtime 尝试访问 model 时失败；dev TUI 的 `/model` 流程会引导你粘贴 key 或 link project。

## 创建 agent scaffold

```bash
npx eve@latest init analytics-assistant
cd analytics-assistant
```

该命令会写入使用 eve 默认 model 和 built-in HTTP API channel（`agent/channels/eve.ts`）
的 starter agent，安装 dependencies，初始化 Git，并启动 development server。继续下面的编辑前，
请先停止 server。它不会创建 Vercel project，也不会 deploy。`init` 会创建
`analytics-assistant/` 目录，因此运行后续命令前请先 `cd` 进去。

## 设置 model

`agent/agent.ts` 保存 model 和 config。请为 analysis work 使用能力足够的 model：

```ts
import { defineAgent } from "eve";

export default defineAgent({
  model: "anthropic/claude-opus-4.8",
});
```

## 赋予 analyst persona

`agent/instructions.md` 是 always-on system prompt。把 starter text 替换为 data analyst 的长期身份：

```md
You are a senior data analyst. You answer questions about the team's data.

- Prefer exact numbers to hand-waving. If you can compute it, compute it.
- State the assumptions behind any number you report (date range, filters, grain).
- Use the tools available to you rather than guessing. If you cannot answer from
  the data, say so plainly.
```

Instructions 是身份和长期规则。On-demand procedures 属于 skills（第 7 步），actions 属于 tools（第 3 步）。见 [Instructions](../instructions)。

## 运行 agent

```bash
npm run dev
```

`init` scaffold 会写入一个 `dev` script，用于从项目的 `node_modules` 运行 `eve dev` binary。local runtime 会启动，dev TUI 会打开。先问一个它可以用通用知识回答的问题：

```text
What's a good way to measure week-over-week retention?
```

你会得到一个遵循 analyst persona 的回复。它还看不到你的数据（第 3 步会添加）。先看一下底层发生了什么。

→ 下一步：[How it runs](./how-it-runs)

了解更多：[Getting Started](../getting-started) · [Instructions](../instructions)
