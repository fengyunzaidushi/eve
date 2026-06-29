# eve 公开文档

这个 folder 面向把 eve 作为 framework 使用的 app authors。

如果你想了解如何用 eve 构建 agents，请从这里开始。

重要命名说明：

- framework 叫 eve。
- 当前 published package name 是 `eve`。
- CLI binary 是 `eve`。

## 法律与 safeguard

eve 目前是 preview，受 Vercel beta terms 约束；framework、APIs、documentation 和 behavior 在 general availability 前都可能变化。

作为 deployer，你有责任确保你的 agent 符合适用法律。

你负责配置适合自己 use case 的 approval policies、tool restrictions、connection scopes、route/session authorization、sandbox controls、telemetry exports 和其他 safeguards。

在将 eve 用于非公开、敏感、受监管或生产数据之前，请审查 agent 可用的 default tools、custom tools、MCP tools、shell/file/web tools、connected services、subagents、schedules 和 external actions。

对于敏感、不可逆、受监管、金融、医疗、就业、住房、法律、安全影响、用户影响或带外部副作用的 actions，请要求 human approval 或其他 safeguards。

除非你配置更严格的 controls，否则 eve agents 可能以宽松设置运行，包括省略 approval 时无需 human approval 的 tool execution，以及不是 deny-all 的 sandbox network egress。不要只依赖 model behavior 来防止敏感或不可逆 actions。

大小写约定：

- 对页面 `title` frontmatter 和 `meta.json` section titles 使用 Title Case（Fumadocs 会把页面 `title` 同时渲染为 sidebar entry 和 `<h1>`，所以一种 casing 覆盖两处），例如 `Execution Model & Durability`、`Dynamic Capabilities`、`Build an Agent`。
- 对页内 headings（`##` 及以下）使用 sentence case。只大写第一个词以及 proper nouns/acronyms，例如 `Next.js`、`SvelteKit`、`Slack`、`GitHub`、`CLI`、`TypeScript API`、`agent.ts`。

## 先读这些

按这个顺序阅读：

1. [Introduction](./introduction.md)
2. [Getting Started](./getting-started.md)
3. [Project Layout](./reference/project-layout.md)
4. [`agent.ts`](./agent-config.md)
5. [TypeScript API](./reference/typescript-api.md)
6. [Context Control](./concepts/context-control.md)
7. [Skills](./skills.md)
8. [Tools](./tools/overview.md)
9. [Connections](./connections.md)
10. [Sandboxes](./sandbox.md)
11. [Channels](./channels/overview.md)
12. [Session Context](./reference/typescript-api.md)
13. [Sessions And Streaming](./concepts/sessions-runs-and-streaming.md)
14. [TypeScript SDK](./clients/typescript-sdk/overview.md)
15. [Subagents](./subagents.md)
16. [Schedules](./schedules.md)
17. [Evals](./evals/overview.md)
18. [Auth And Route Protection](./develop/auth-and-route-protection.md)
19. [Vercel Deployment](./develop/deployment.md)
20. [CLI, Build, And Debugging](./reference/cli.md)

## 公开心智模型

eve 是 filesystem-first framework，用于 durable backend agents。

你把 agent author 为磁盘上的 files：

- `instructions.md` 或 `instructions.ts` 中的 instructions
- `skills/` 中的可选 procedures
- `tools/` 中的 typed integrations
- `connections/` 中的 external MCP servers
- `sandbox/` 中的 per-agent sandbox override
- `channels/` 中的 messaging integrations
- `lib/` 中的 shared authored code
- `subagents/` 中的 specialist child agents
- `schedules/` 中的 recurring jobs
- `agent.ts` 中的 additive runtime config

然后 eve 会提供：

- 稳定的 HTTP message route
- 可选的 channel webhook routes
- 可重连的 session stream
- 跨 turns 的 durable session state
- 带 shared runtime workspace 的 per-agent sandbox
- 通过 `ctx` 访问的 typed runtime helpers（`ctx.session`、`ctx.getSandbox()`、`ctx.getSkill()`）

## Runtime shape

public surface 保持 filesystem-first，但理解下面的 implementation model 仍然有帮助：

- channels 会 normalize inbound transport input，并定义 `continuationToken`
- harness 执行一个 AI work unit，并决定 continue、wait 还是 finish
- runtime 会持久化 session state、stream events，并拥有 workflow orchestration

因此 eve 暴露两个 identifiers：

- `continuationToken` 用于下一条 user message
- `sessionId` 用于 streaming 和 inspection

## 如何使用这些 docs

- 从 authored filesystem shape 和 `agent.ts` 开始。
- 然后按这个顺序添加 runtime surfaces：skills、tools、workspace、sandbox、channels。
- 接着学习 durable runtime model：HITL、session context、sessions、streaming 和 continuation-token follow-ups。
- 最后添加 advanced features：subagents、schedules、route protection、deployment。

## repo 中的配套材料

- 面向 weather 的 smoke/dev fixture：[`../../apps/fixtures/weather-fixture`](../../apps/fixtures/weather-fixture)
- Public API 的权威来源：[`../../packages/eve/src/public/index.ts`](../../packages/eve/src/public/index.ts)
