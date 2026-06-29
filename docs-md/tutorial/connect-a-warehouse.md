---
title: "连接 Warehouse"
description: "Build an Agent 教程第 4 部分。让每个用户通过 Vercel Connect 上的 OAuth MCP 连接自己的 warehouse。"
---

sample dataset 已经让 analytics assistant 跑起来了，但它只是替身。现在把 agent 指向真实 warehouse，并让每个用户通过浏览器登录来连接自己的 warehouse。这正是 connection 的用途。它是 model 通过 tools 访问的 MCP server，auth 由 eve 为你驱动。

这一步依赖 Vercel Connect，它目前处于 private beta。没有 Connect 访问权限？保留第 3 步的 sample dataset，并阅读本步骤了解 connection model。第 5 到第 9 步可以基于 sample dataset 工作，因此没有 warehouse 也能完成教程。

文件名会设置 runtime name。把文件放在 `agent/connections/warehouse.ts`，它会注册为 `"warehouse"`，其 tools 会以 `connection__warehouse__<tool>` 的形式暴露。

## 声明 connection

warehouse 通过 OAuth 背后的 generic SQL MCP 暴露能力。将来自 `@vercel/connect/eve` 的 `connect()` 作为 auth 传入，Vercel Connect 会处理 OAuth flow、存储 tokens，并为你刷新它们：

```ts title="agent/connections/warehouse.ts"
import { connect } from "@vercel/connect/eve";
import { defineMcpClientConnection } from "eve/connections";

export default defineMcpClientConnection({
  url: "https://mcp.your-warehouse.example/sse",
  description: "The team's data warehouse: run read-only SQL and list tables and columns.",
  auth: connect("warehouse"),
});
```

`"warehouse"` 是你注册 Connect client 时选择的 UID。默认情况下，此 OAuth 是 user-scoped 的。每个 end-user 会在自己的浏览器中授权，eve 会在每次 tool call 前解析该用户的 token。

在你的账号启用 Connect 后，接入它：

1. 安装 package：`npm install @vercel/connect`。
2. 创建 Connect client：`vercel connect create <type> --name warehouse`。
3. 将 client link 到你的 project。
4. 运行 `vercel link` 和 `vercel env pull`，让 `VERCEL_OIDC_TOKEN` 在本地可用。

完整 reference 见 [Connections](../connections)。

## 用户会看到什么

提出一个需要 warehouse 的问题：

```text
How many enterprise customers signed up last month?
```

第一次时，model 会选择一个 warehouse tool，但此时还没有 token，因此 turn 会 park，channel 会显示 “Sign in” affordance。你在浏览器中授权，OAuth callback 完成后，turn 会从那个 step 精确恢复（来自 [Step 2](./how-it-runs) 的 durable parking），然后运行 query。session 中后续 calls 会复用缓存的 per-user token，因此不会再提示。

## Token 永远不会到达 model

在每次请求 MCP server 之前，eve 会解析 bearer，并以 `Authorization: Bearer <token>` 发送。model 只会看到 tool names、descriptions 和 results。credential 始终不在它能触及的范围内。

如果你想要更多控制，可以用 approval gate 住 connection（`approval: once()`），或缩小 model 能看到的 tools（`tools.allow`）。见 [Connections](../connections)。

→ 下一步：[Run analysis](./run-analysis)

了解更多：[Connections](../connections) · [Auth and route protection](../guides/auth-and-route-protection)
