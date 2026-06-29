---
title: "Connections"
description: "向 model 暴露外部 MCP 和 OpenAPI servers，同时让 model 永远看不到 connection tokens。"
---

connection 会把 agent 接入你不编写的外部 server，可以是 MCP server（Linear、GitHub、warehouse），也可以是任何带 OpenAPI document 的 HTTP API。eve 会处理你原本需要手写的部分：发现 remote tools、把它们暴露给 model，并 broker auth。

Connections 位于 `agent/connections/` 下。runtime name 来自文件名，因此 `agent/connections/linear.ts` 会注册为 `"linear"`。model 永远看不到 connection 的 URL 或 credentials。它通过 built-in `connection__search` 发现 tools，并通过 qualified name 调用它们：`connection__<connection>__<tool>`（例如 `connection__linear__list_issues`）。

## MCP connections

`defineMcpClientConnection` 指向 MCP server。请提供 `url` 和 `description`：

```ts title="agent/connections/linear.ts"
import { defineMcpClientConnection } from "eve/connections";

export default defineMcpClientConnection({
  url: "https://mcp.linear.app/sse",
  description: "Linear workspace: issues, projects, cycles, and comments.",
  auth: {
    getToken: async () => ({ token: process.env.LINEAR_API_TOKEN! }),
  },
});
```

`url` 必须支持 Streamable HTTP 或 SSE。请为 model 编写 `description`，而不是为你自己。它会出现在 `connection__search` 中，model 会用它决定查询哪个 connection。

### Static-token auth

`getToken` 返回 `TokenResult`（`{ token, expiresAt? }`），eve 会在每个 request 上把它作为 `Authorization: Bearer <token>` 发送。由于它会在每次 connection attempt 时运行，你可以从任何保存 secrets 的位置 mint fresh token，包括 env var、secrets manager、internal vault 或你自己的 OAuth exchange。如果 token 有已知 TTL，请设置 `expiresAt`（自 epoch 起的毫秒数），eve 会提前刷新，而不是等待 `401`。

当 `getToken` 是唯一 auth 时，`principalType` 默认是 `"app"`：一个跨所有 sessions keyed 的 shared credential。当每个 end-user 携带自己的 token 时，请切换到 `principalType: "user"`。

eve 会按 step 解析并缓存 connection tokens；它们永远不会进入 conversation history，也不会到达 model。

### No auth

对于不需要 token 的 servers（例如 development 期间的 localhost server 或 public server），可以完全省略 `auth`：

```ts
export default defineMcpClientConnection({
  url: "http://localhost:3001/mcp",
  description: "Local dev server.",
});
```

建议仅对有意公开、仅限本地，或在 eve 之外已受保护的 services 使用 no-auth connections。不要对敏感 third-party services 使用 no-auth connections。

### Headers

当 server 需要非 Bearer 方案（API-key header）或额外配置时，请使用 `headers`。Headers 会叠加在 `auth` 之上：

```ts
export default defineMcpClientConnection({
  url: "https://example.com/mcp",
  description: "Example service.",
  headers: { "X-Api-Key": process.env.EXAMPLE_API_KEY! },
});
```

### Tool filters

若要缩小 model 可见的 remote tools，请在 `tools.allow` 和 `tools.block` 中恰好设置一个。被过滤掉的 tools 不会出现在 `connection__search` 中：

```ts
export default defineMcpClientConnection({
  url: "https://mcp.linear.app/sse",
  description: "Linear: read-only.",
  auth: { getToken: async () => ({ token: process.env.LINEAR_API_TOKEN! }) },
  tools: { allow: ["search_issues", "get_issue"] },
});
```

### Per-connection approval

若要把 connection 提供的每个 tool 都放到 human 后面，请使用来自 `eve/tools/approval` 的 helpers：

```ts
import { once } from "eve/tools/approval";

export default defineMcpClientConnection({
  url: "https://mcp.linear.app/sse",
  description: "Linear workspace.",
  auth: { getToken: async () => ({ token: process.env.LINEAR_API_TOKEN! }) },
  approval: once(),
});
```

`never()` 允许每个 call 通过，`once()` 在 session 中第一次请求 approval，`always()` 每次都请求。pause 和 resume 使用 [Tools](./tools) 中介绍的同一套 human-in-the-loop flow。

对于可以创建、修改、删除、传输、购买、发消息或访问 sensitive data 的 connection tools，请使用 approval、tool allow-lists，或其他适合该 action 的 safeguards。

## OpenAPI connections

`defineOpenAPIConnection` 会把任何 OpenAPI 3.x document 转成 connection tools，每个 operation 一个。传入 eve 在 runtime fetch 的 HTTPS URL，或 inline parsed object：

```ts title="agent/connections/petstore.ts"
import { defineOpenAPIConnection } from "eve/connections";

export default defineOpenAPIConnection({
  spec: "https://petstore3.swagger.io/api/v3/openapi.json",
  description: "Pet store inventory and orders.",
  auth: { getToken: async () => ({ token: process.env.PETSTORE_TOKEN! }) },
});
```

每个 operation 都会变成 `connection__<connection>__<operationId>`（例如 `connection__petstore__getInventory`）。当 operation 没有 `operationId` 时，eve 会派生一个确定性的 `<method>_<sanitized-path>` 名称。

`auth`、`headers` 和 `approval` 的工作方式与 MCP 完全相同。OpenAPI 有两个专属字段：

| Field        | Purpose                                                                                                                          |
| ------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| `baseUrl`    | operation paths 解析所基于的 Base URL。可选；默认使用 document 中第一个可用的 `servers` entry。                                  |
| `operations` | 以 `operationId` 为 key 的 filter（`allow` 或 `block`）。对应 MCP connections 上的 `tools`，但命名的是 operations 而不是 tools。 |

## Interactive OAuth via Vercel Connect

当 server 使用 OAuth，并且你希望每个 end-user 通过自己的浏览器登录时，请用 [Vercel Connect](https://vercel.com/docs/connect) 开启 interactive authorization。来自 `@vercel/connect/eve` 的 `connect()` helper 会处理 consent、encrypted token storage 和 refresh，然后把所有内容接入 eve 的 authorization flow：

```ts title="agent/connections/linear.ts"
import { connect } from "@vercel/connect/eve";
import { defineMcpClientConnection } from "eve/connections";

export default defineMcpClientConnection({
  url: "https://mcp.linear.app/sse",
  description: "Linear workspace: issues, projects, cycles, and comments.",
  auth: connect("linear"),
});
```

`"linear"` 是你注册 Connect client 时选择的 UID。Connect-managed OAuth 默认是 user-scoped，因此 runtime 会在每次 tool call 前解析 per-user token。完整设置（Connect client provisioning、project linking、runtime consent flow）见 [Auth & route protection](./guides/auth-and-route-protection)。

## Self-hosted interactive OAuth

若要运行自己的 OAuth，请使用来自 `eve/connections` 的 `defineInteractiveAuthorization`。它采用三方法形式，不需要 Vercel Connect。eve 会 mint callback URL，在 framework-owned webhook 上 park（durably suspend）turn，并在 token 返回后恢复。Interactive auth 始终是 `principalType: "user"`，factory 会为你固定这一点。

```ts title="agent/connections/linear.ts"
import {
  ConnectionAuthorizationRequiredError,
  defineInteractiveAuthorization,
  defineMcpClientConnection,
} from "eve/connections";

export default defineMcpClientConnection({
  url: "https://mcp.linear.app/sse",
  description: "Linear workspace.",
  auth: defineInteractiveAuthorization<{ verifier: string }>({
    // Probed before every tool call. Return a token to run the tool;
    // throw `Required` to start the consent flow.
    getToken: async ({ principal }) => {
      const token = await lookupCachedToken(principal);
      if (!token) throw new ConnectionAuthorizationRequiredError("linear");
      return { token };
    },
    // Runs in a durable step. Return the user-facing `challenge` and
    // an optional `resume` value the runtime journals across the park.
    startAuthorization: async ({ callbackUrl }) => {
      const verifier = makePkceVerifier();
      return {
        challenge: { url: buildAuthorizeUrl(callbackUrl, verifier) },
        resume: { verifier },
      };
    },
    // Runs when the provider redirects to the callback URL. `resume` is
    // typed as `{ verifier: string } | undefined`; `callback.params`
    // holds the IdP's returned query/body params.
    completeAuthorization: async ({ resume, callback }) => {
      const token = await exchangeCode(resume!.verifier, callback.params.code!);
      return { token };
    },
  }),
});
```

`getToken` 会在每次 tool call 前运行。`startAuthorization` 和 `completeAuthorization` 必须同时提供或同时不提供：只提供其中一个会得到 definition error。`challenge` 会原样附带在 `authorization.required` event 上。它的字段：

| Field          | Purpose                                                                              |
| -------------- | ------------------------------------------------------------------------------------ |
| `url`          | redirect 或 device flows 的 authorize URL。                                          |
| `userCode`     | device flows 使用的 device code。                                                    |
| `instructions` | 没有 URL 时的 call to action。                                                       |
| `displayName`  | channels 在 sign-in affordance 上显示的人类可读 provider name（例如 "Salesforce"）。 |

当 provider 在 server-side 保存 flow state 时，可以省略 `resume`，这样就没有内容需要跨越 step boundary。

`displayName` 仅用于展示。connection 的 path-derived name 仍用于 keyed authorization scope、token cache 和 callback URL。你也可以在 `auth` definition 本身上设置 `displayName`（例如 `auth: { ...connect("sfdc"), displayName: "Salesforce" }`）；该 definition-level 值优先于 strategy 写入 challenge 的值。当两者都未设置时，channels 会 fallback 到对 connection name 做 title-casing。

### Signaling authorization state

两个 error classes 会驱动 consent flow。可从 `getToken` 或 `completeAuthorization` 中 throw 它们；两者都从 `eve/connections` 导出。

- `ConnectionAuthorizationRequiredError(connectionName)`：用户必须 authorize。从 `getToken` 中 throw 它会发出 `authorization.required` 并启动 flow。
- `ConnectionAuthorizationFailedError(connectionName, { reason?, retryable? })`：authorization failed。`reason` 是稳定的 machine-readable code（例如 `"access_denied"`），会出现在 `authorization.completed` event 和 failed tool result 上。`retryable` 默认为 `true`；对于 user denial 这类 terminal cases，请设为 `false`，让 runtime 停止重新提示。

```ts
import { ConnectionAuthorizationFailedError } from "eve/connections";

throw new ConnectionAuthorizationFailedError("linear", {
  reason: "access_denied",
  retryable: false,
});
```

若要 narrow caught error，请使用 `isConnectionAuthorizationRequiredError(err)` 和 `isConnectionAuthorizationFailedError(err)`。它们按 `err.name` 匹配，因此能避开 bundling 后 `instanceof` 可能遇到的 class-identity split。

### Handling a revoked token mid-call

`getToken` 只会在 tool call _之前_ 运行，因此如果 grant 在 tool mid-flight 时被撤销，首先会在你的 `execute` 中表现为 downstream `401`。在这里普通 throw 只会成为 tool error，因此 model 会看到失败，而 cached bearer 会保留下来。请改为把 provider `401` 映射到 `ctx.requireAuth()`（或重新 throw `ConnectionAuthorizationRequiredError`）。随后 eve 会从 per-step cache 中驱逐被拒绝的 token，并用 fresh token 重新运行 consent flow，就像 connection 的 server 拒绝 bearer 时一样。

```ts title="agent/tools/list_issues.ts"
import { defineTool } from "eve/tools";
import { z } from "zod";

export default defineTool({
  description: "List open Linear issues.",
  inputSchema: z.object({}),
  async execute(_input, ctx) {
    const { token } = await ctx.getToken();
    const res = await fetch("https://api.linear.app/graphql", {
      headers: { authorization: `Bearer ${token}` },
    });
    // The grant was revoked since getToken ran: re-challenge instead of
    // returning a dead-token error to the model.
    if (res.status === 401) ctx.requireAuth();
    return await res.json();
  },
});
```

### Authorization and approval together

tool 可以同时要求 sign-in（`auth`）和 human approval。model 的 approval gate 会在 tool 的 `execute` 前运行，因此用户看到的顺序是 **先 approve，再 sign in**。eve 会在 approval 被授予的瞬间把它记录到 session state 上，并且该记录会在 sign-in park 后保留，因此 authorization 后 turn 恢复时，tool 不会再次经过 approval。你会得到一次 approval 和一次 sign-in，而不是 double prompt。

## 接下来阅读

- [Integrations](/integrations)：在一个 gallery 中浏览 eve 随附的每个 channel 和 connection。
- [Tools](./tools)：authored tools 与 connection-provided tools 并存；同样适用 approval helpers。
- [Auth & route protection](./guides/auth-and-route-protection)：使用 Vercel Connect 的完整 interactive-OAuth flow。
- [Security model](./concepts/security-model)：connection credentials 如何保持在 model 触及范围之外。
