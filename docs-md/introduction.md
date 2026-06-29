---
title: "介绍"
description: "eve agent 如何以文件组织、消息到达时会运行什么，以及随着它成长可以添加哪些构建块。"
---

eve 是一个用于在 TypeScript 项目中以普通文件构建 durable agent 的框架。

它不要求你维护一个庞大的配置对象，而是让 agent 的每个部分都有清晰的位置。instructions 放在一个文件里，tools 放在一个文件夹里，channels 放在另一个文件夹里。eve 会发现这套结构，并把它变成一个可以在本地运行、提供 HTTP 服务、连接其他平台，并能跨多个 turn 持续工作的 agent。

<Callout>
  eve 目前处于 beta 阶段，并受 [Vercel beta
  terms](https://vercel.com/docs/release-phases/public-beta-agreement) 约束；在正式可用之前，框架、API、
  文档和行为都可能发生变化。
</Callout>

## eve 项目概览

一个小型 eve app 通常长这样：

```text
my-agent/
├── package.json
└── agent/
    ├── agent.ts
    ├── instructions.md
    ├── tools/
    │   └── get_weather.ts
    ├── skills/
    │   └── plan_a_trip.md
    └── channels/
        └── slack.ts
```

阅读这棵目录树，就能理解大多数 eve 项目：

- `instructions.md` 告诉 agent 它是谁以及应该如何行动。
- [`agent.ts`](./agent-config) 选择 model，并配置 runtime 选项。
- [`tools/`](./tools) 保存 model 可以调用的类型化函数。
- [`skills/`](./skills) 保存较长的流程，只有在有用时 model 才会加载它们。
- [`channels/`](./channels/overview) 把 agent 连接到 HTTP clients、Slack、Discord 以及人们与它对话的其他地方。

一开始只需要 `instructions.md` 和 `agent.ts`。等 agent 需要时，再添加其他文件夹。

## 文件就是接口

eve 是 [filesystem-first](./reference/project-layout) 的。一个文件的位置说明它做什么，它的路径通常也会赋予它名称。例如这个文件：

```text
agent/tools/get_weather.ts
```

会定义一个名为 `get_weather` 的 tool：

```ts
import { defineTool } from "eve/tools";
import { z } from "zod";

export default defineTool({
  description: "Get the weather for a city.",
  inputSchema: z.object({ city: z.string() }),
  async execute({ city }) {
    return { city, condition: "Sunny" };
  },
});
```

没有需要额外同步的独立 registry。添加文件后，eve 会发现它；移动或重命名文件后，它的身份也会随之移动。完整 API 见 [Tools](./tools)。

## 消息到达时会发生什么

无论消息来自 web app、terminal 还是 Slack，运行的都是同一套流程。eve 会把平台输入转换成 message，把 instructions、skills、tools 和 conversation history 提供给 model，执行工作（按需调用 tools 和 subagents），保存 session 并流式输出 events，然后以该平台期望的形式把结果送回去。

这让 agent 行为保持可移植。你的 weather tool 不需要知道问题来自浏览器还是 Slack。

## 默认 durable

eve session 不只是一次 request 和一次 response。它可以：

- 在工作进行时流式输出进度
- 调用 tools 和 subagents
- 暂停以等待 [approval 或人工回答](./tools)
- 在回答到达后恢复
- 在多个 turns 之间保持 durable state

在底层，eve 使用开源 [Workflow SDK](https://workflow-sdk.dev) 让 sessions 具备 durable、可恢复和 crash-safe 的能力。eve 负责处理这些机制，让你的 tools 专注于工作本身。

## 通过添加能力扩展项目

随着 agent 成长，每类关注点仍然有可预测的位置：

| Path                            | 当你需要...                            |
| ------------------------------- | -------------------------------------- |
| [`connections/`](./connections) | 来自外部 MCP servers 的 tools          |
| [`hooks/`](./guides/hooks)      | 响应 lifecycle 和 stream events 的代码 |
| [`sandbox/`](./sandbox)         | 用于文件和命令的受控 workspace         |
| [`subagents/`](./subagents)     | root agent 可以委派给它们的专用 agents |
| [`schedules/`](./schedules)     | 重复或定时工作                         |
| `lib/`                          | 被其他 agent 文件导入的共享代码        |

最终结构在运行前就是可读的。目录会告诉你这个 agent 能做什么。

## 接下来阅读

- [Getting started](./getting-started)：scaffold 并运行你的第一个 agent
- [Tools](./tools)：agent 会调用的类型化 actions
- [Instructions](./instructions)：塑造行为的 always-on system prompt
- [Channels](./channels/overview)：从 Slack、Discord 或 web UI 访问 agent
- [Connections](./connections)：引入来自外部 MCP servers 的 tools
- [Project layout](./reference/project-layout)：`agent/` 下每个可编写的 slot
