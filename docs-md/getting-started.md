---
title: "快速开始"
description: "安装 eve，scaffold 第一个 agent，为它添加 tool，并在本地运行。"
---

eve 是一个面向 durable agents 的 filesystem-first 框架。你在 `agent/` 下编写 capabilities，eve 负责运行 model loop、持久化每个 session，并通过 HTTP 和 platform channels 提供 agent 服务。你将 scaffold 一个 app，添加一个 tool，在本地运行它，然后通过 HTTP 创建、流式读取并继续一个 session。

<Callout>
  eve 目前处于 beta 阶段，并受 [Vercel beta
  terms](https://vercel.com/docs/release-phases/public-beta-agreement) 约束；在正式可用之前，框架、API、
  文档和行为都可能发生变化。
</Callout>

## 前置条件

- Node 24 或更新版本
- npm（随 Node 捆绑）
- 一个 model credential（见下文）

scaffold 的默认 model 是 `anthropic/claude-sonnet-4.6`，它会通过 Vercel AI Gateway 路由。运行 agent 前，请设置以下其中一项：

- gateway model id 需要 `AI_GATEWAY_API_KEY`，或通过 `vercel link` 获取的 `VERCEL_OIDC_TOKEN`。
- direct provider model 使用该 provider 的 AI SDK package 和 API key。例如，来自 `@ai-sdk/anthropic` 的 `anthropic("claude-...")` 需要 `ANTHROPIC_API_KEY`。

你有责任为自己的数据和 use case 选择合适的 model、provider 和 channel，并遵守每个 provider 的条款（按 model 列出）和数据处理要求。

如果跳过这一步，dev TUI 会标记缺失的 credential，并通过 `/model` 命令引导你粘贴 key 或 link project。

## 快速开始

`npx` 可以在不预先安装 eve 的情况下运行 `eve init`：

```bash
npx eve@latest init my-agent
```

该命令会：

- 使用当前 workspace 或 launcher package manager 创建子目录，并使用 eve 的默认 model
- 安装 dependencies 并初始化 Git
- 启动 development server，并打开交互式 [terminal UI](./guides/dev-tui)

输入一条消息，观察 model loop 运行。传入 `--channel-web-nextjs` 可以添加 Web Chat application。无论是否添加它，每个 app 都会随附 built-in HTTP channel（`agent/channels/eve.ts`）。

`eve init` 会占用 terminal，因此在编辑生成的 agent 前，请用 Ctrl+C 停止它并取回 shell。该命令不会创建 Vercel project，也不会 deploy。

要把 eve 添加到已有项目，请在已经有 `package.json` 且还没有 `agent/` 文件的目录中运行 `eve init .`。eve 会补齐缺失的 `eve`、`ai` 和 `zod` dependencies，而不会触碰项目拥有的其他内容。eve dependency 和 Node engine 来自同一个 release。eve 会把 `engines.node` 固定到该 release 支持的最低 major（例如 `24.x`）。只有当现有范围允许的所有版本都仍在该 major 内时，它才会保留该范围；否则会替换范围并打印 warning。

## 手动安装

如果不用 `eve init`，而是手动把 eve 接入已有 app，请先在 `package.json` 中声明兼容的 Node runtime：

```json
{
  "engines": {
    "node": "24.x"
  }
}
```

然后安装 dependencies，并编写 runtime 需要的两个文件。`eve init` scaffold 会为你添加 `ai` 和 `zod`；手动方式需要安装全部三个：

```bash
npm install eve@latest ai zod
```

### 项目文件

最小 agent 由两个文件组成；需要 tools 时再添加。

`agent/instructions.md` 是 always-on system prompt：

```md
You are a concise assistant. Use tools when they are available.
```

`agent/agent.ts` 保存 runtime config：

```ts
import { defineAgent } from "eve";

export default defineAgent({
  model: "anthropic/claude-sonnet-4.6",
});
```

在使用真实客户数据前，请确认所选 model provider 的条款、路由路径和 retention settings 适合这些数据。

即使只有这些内容，agent 也已经可以做真实工作。default harness 开箱提供 file、shell、web 和 delegation tools。完整集合以及如何覆盖或禁用其中任意项，见 [Default harness](./concepts/default-harness)。

### 添加第一个 tool

文件名会成为 model 看到的 tool 名称，并且必须是 snake_case ASCII。创建 `agent/tools/get_weather.ts`：

```ts
import { defineTool } from "eve/tools";
import { z } from "zod";

// The model sees this tool as `get_weather`, from the filename.
export default defineTool({
  description: "Get the current weather for a city.",
  inputSchema: z.object({ city: z.string().min(1) }),
  async execute({ city }) {
    return { city, condition: "Sunny", temperatureF: 72 };
  },
});
```

Tools 会在你的 app runtime 中运行，并拥有完整的 `process.env`，而不是在 [sandbox](./sandbox) 中运行。更多内容见 [Tools](./tools)。

## 运行 app

scaffold 生成的 app 带有 `dev` script，因此可以在 app 根目录运行：

```bash
npm run dev
```

手动路径不会编写 `dev` script。请改用 `npx` 运行 binary：

```bash
npx eve dev
```

eve binary 还提供其他命令（每条命令前加 `npx`，或添加匹配的 package.json script）：

- `eve info`：显示 active routes 和 compiled artifacts
- `eve build`：把 agent 编译到 `.eve/`，并构建 host output
- `eve start`：提供 built output 服务
- `eve dev`：启动 local runtime，并打开交互式 [terminal UI](./guides/dev-tui)

在 dev TUI 中输入一条消息，观察它按顺序发生。先是 `get_weather` call，然后是它的结果，最后是 reply。

同一个 CLI 也可以指向 deployment。`npx eve dev https://your-app.vercel.app` 会驱动已部署的 app，适合用于 preview 和 production smoke tests。见 [Deployment](./guides/deployment)。

## 发送消息

每个 eve app 都暴露同一套稳定 HTTP API。启动一个 durable session：

```bash
curl -X POST http://127.0.0.1:3000/eve/v1/session \
  -H 'content-type: application/json' \
  -d '{"message":"What is the weather in Brooklyn?"}'
```

response 会返回两个你会复用的内容：

- JSON body 中的 `continuationToken`，用于恢复这个 conversation
- 标识要 stream 的 run 的 `x-eve-session-id` header

## 流式读取 session

连接到 session stream：

```bash
curl http://127.0.0.1:3000/eve/v1/session/<sessionId>/stream
```

stream 是 NDJSON，以 `application/x-ndjson; charset=utf-8` 提供。对于这次 run，你会看到几个 lifecycle events：

- `session.started`
- `actions.requested` (the `get_weather` call)
- `action.result`
- `message.completed` (the reply)
- `session.completed`

`reasoning.appended` 和 `message.appended` 是可选的 live-streaming events。无法展示 incremental output 的 clients 可以忽略它们，并依赖 `reasoning.completed` 和 `message.completed`。

注意：在你的 application 中显示、存储或传输 reasoning events 时，请考虑 privacy、confidentiality 和 user-experience 影响。

完整集合覆盖更多 lifecycle、human-in-the-loop 和 authorization events，包括 `input.requested`、`turn.failed`、`authorization.required` 和 `authorization.completed`。每个 event 及其 data shape 见 [Sessions, runs and streaming](./concepts/sessions-runs-and-streaming)。

## 发送 follow-up 消息

当 session 正在等待下一条 user message 时，使用 token 发送 follow-up：

```bash
curl -X POST http://127.0.0.1:3000/eve/v1/session/<sessionId> \
  -H 'content-type: application/json' \
  -d '{"continuationToken":"<token>","message":"Now do Queens."}'
```

完整 contract 见 [Sessions, runs and streaming](./concepts/sessions-runs-and-streaming)。

## 使用 coding agent 设置

如果由 coding agent（Claude Code、Cursor 等）执行设置，请把这个 prompt 交给它：

<CopyPrompt text="Set up an eve agent for the user. eve is a filesystem-first TypeScript framework for durable agents, published as the npm package eve. Read its docs: once eve is installed they are bundled in the package at node_modules/eve/docs; before eve is installed, read the published Introduction and Getting Started pages. If the project has no eve app, scaffold one with `npx eve@latest init <name>`; add `--channel-web-nextjs` only when the user wants Web Chat. The init command installs dependencies, initializes Git, and starts the dev server, so run it in a controllable process and stop it with Ctrl+C before editing. To add eve to an existing app, run `eve init .`, or install the dependencies by hand with `npm install eve@latest ai zod` (init adds ai and zod; the by-hand path needs all three). Make sure agent/agent.ts and agent/instructions.md exist, then add a first typed tool at agent/tools/get_weather.ts using defineTool from eve/tools with a Zod inputSchema and an inline execute. Start the dev server again, then exercise the HTTP API: create a session with POST /eve/v1/session, attach to GET /eve/v1/session/:id/stream, and send a follow-up with the returned continuationToken. Verify with the project's typecheck, adapt model and provider choices to the project, and do not commit unless the user asks.">
  Set up an eve agent: read the eve docs (bundled at node_modules/eve/docs once eve is
  installed), scaffold with `npx eve@latest init <name>` (or `npm install eve@latest ai zod` in an existing app), add
  a typed tool at agent/tools/get_weather.ts, run it with `npm run dev`, then create a session, stream
  it, and send a follow-up.
</CopyPrompt>

一旦 `eve` 成为 dependency，该 package 会捆绑完整 docs，因此 agent 可以在本地读取 `node_modules/eve/docs/`，不需要联网获取。

设置完成后，如果要添加 platform channel，请在交互式 terminal 中运行 `eve channels add slack`。init flags 已在 [快速开始](#快速开始) 中说明。

## 接下来阅读

- [Instructions](./instructions) 和 [Tools](./tools)：核心 building blocks
- [Channels](./channels/overview)：从 Slack、Discord 或 web UI 访问 agent
- [Frontend](./guides/frontend/overview)：使用 `useEveAgent` 构建 browser chat
- [TypeScript SDK](./guides/client/overview)：从 scripts 或 server-side code 调用 agent
- [Sessions, runs and streaming](./concepts/sessions-runs-and-streaming)：durable session model
- [Build an agent](./tutorial/first-agent)：完整端到端 walkthrough
