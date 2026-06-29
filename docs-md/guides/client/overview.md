---
title: "TypeScript SDK 概览"
description: "使用 Client、sessions、auth 和 health checks 从 TypeScript 调用 eve agent。"
---

`eve/client` entrypoint 是 eve 默认 HTTP API 的 typed client。可在 scripts、server-to-server integrations、tests、evals、backend jobs，或任何希望使用 session protocol 但不想手写 POST 和 NDJSON（newline-delimited JSON）stream loop 的 custom UIs 中使用它。

对于 browser chat UIs，请从 [`useEveAgent`](../frontend/overview) 开始。wire-level 细节见 [Sessions, runs & streaming](../../concepts/sessions-runs-and-streaming)。client 位于二者之间：比 frontend hooks 更底层，比 raw HTTP 更高层。

## 创建 client

`Client` 会绑定一个 host、auth policy、header policy 和 stream reconnection budget：

```ts
import { Client } from "eve/client";

const client = new Client({
  host: "http://127.0.0.1:3000",
});
```

`host` 是 eve routes 挂载所在的 origin。在 same-origin browser integration 中，它通常是 `""`；scripts 和 backend services 通常填写完整 URL。

## 检查 health

当 script 需要在创建 session 前尽早失败时，请使用 `health()`：

```ts
const health = await client.health();
console.log(health.status, health.workflowId);
```

非 2xx responses 会 throw `ClientError`，其中携带 HTTP `status` 和 response `body`。

## Authentication

当 [eve channel](../../channels/eve) route 需要 credentials 时，请传入 `auth`：

```ts
const client = new Client({
  host: "https://agent.example.com",
  auth: {
    bearer: async () => await getAccessToken(),
  },
});
```

Bearer values 和 Basic auth passwords 可以是 strings 或 functions。Functions 会在每次 HTTP call 前运行，包括 stream reconnects：

```ts
const client = new Client({
  host: "https://agent.example.com",
  auth: {
    basic: {
      username: "agent-client",
      password: async () => await getRotatingSecret(),
    },
  },
});
```

对于 bypass tokens 或 tenant hints 等 route-specific credentials，请使用 `headers`。与 `auth` 一样，它可以是 static 或 dynamic：

```ts
const client = new Client({
  host: "https://agent.example.com",
  headers: async () => ({
    "x-vercel-protection-bypass": await getBypassToken(),
  }),
});
```

Per-request headers 可以附加到单个 turn：

```ts
const response = await session.send({
  message: "Run the check.",
  headers: { "x-request-id": requestId },
});

await response.result();
```

## Sessions

为每个 conversation 创建一个 `ClientSession`：

```ts
const session = client.session();
```

client 可以同时拥有多个 sessions。每个 session 都会 tracking 自己的 `sessionId`、`continuationToken` 和 stream cursor：

```ts
const alice = client.session();
const bob = client.session();

const aliceResponse = await alice.send("Summarize account A.");
await aliceResponse.result();

const bobResponse = await bob.send("Summarize account B.");
await bobResponse.result();
```

后续页面覆盖 session lifecycle：

- [Messages](./messages)：发送 turns 并收集 results
- [Continuations](./continuations)：持久化并恢复 sessions
- [Streaming](./streaming)：在 events 到达时渲染它们
- [Output schema](./output-schema)：请求 structured results

## 接下来阅读

- [eve channel](../../channels/eve)：此 client 调用的 HTTP API
- [Sessions, runs & streaming](../../concepts/sessions-runs-and-streaming)：raw HTTP contract
- [Frontend](../frontend/overview)：使用 `useEveAgent` 的 browser UI
