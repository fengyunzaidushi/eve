---
title: "eve"
description: "agent 的默认 HTTP API，覆盖 session routes、auth 和 customization。"
---

eve channel 是 framework 的默认 HTTP API。terminal UI、[`useEveAgent`](../guides/frontend/overview)、`curl` 以及任何 SDK client 在启动 sessions、发送 messages 和 stream events 时都会与它通信。`eveChannel()` 会把 canonical session routes 挂载到 `/eve/v1/session*` 下，并且即使 `agent/channels/eve.ts` 不存在，它们也默认启用。

当某些东西需要通过 HTTP 访问你的 agent 时，请使用它，包括 local tooling、browser frontend、terminal UI 或其他 API client。大多数 apps 永远不需要编写这个文件。只有在需要覆盖 defaults 时才添加 `agent/channels/eve.ts`，通常是覆盖 route auth policy。

```ts title="agent/channels/eve.ts"
import { eveChannel } from "eve/channels/eve";
import { localDev, vercelOidc } from "eve/channels/auth";

export default eveChannel({
  auth: [localDev(), vercelOidc()],
});
```

## Routes

该 channel 暴露用于创建 sessions、发送 follow-ups 和 stream events 的 routes：

- `GET /eve/v1/health`
- `POST /eve/v1/session` (start a session)
- `POST /eve/v1/session/:sessionId` (send a follow-up)
- `GET /eve/v1/session/:sessionId/stream` (stream events, NDJSON)

用最小 body 启动 session。response 会返回 `sessionId` 和可复用于 follow-ups 的 `continuationToken`：

```bash
curl -X POST https://<deployment>/eve/v1/session \
  -H "Content-Type: application/json" \
  -d '{"message":"What is the weather in Paris?"}'
# {"continuationToken":"eve:7f3c...","ok":true,"sessionId":"ses_01h..."}
```

把该 session 的 events 作为 newline-delimited JSON（`application/x-ndjson; charset=utf-8`）stream 出来，每行一个 event object：

```bash
curl -N https://<deployment>/eve/v1/session/ses_01h.../stream
# {"type":"turn.started",...}
# {"type":"text.delta","delta":"It is "}
# {"type":"message.completed",...}
```

完整 request 和 stream flow（包括完整 event set）见 [Sessions, runs & streaming](../concepts/sessions-runs-and-streaming)。

## Authentication

`auth` 选项决定谁可以调用这些 routes。built-in helpers 覆盖 development 和 trusted infrastructure：

- `localDev()` 在 local development 期间接受 requests。
- `vercelOidc()` 允许 local CLI 访问已部署 agent，也允许团队中的其他 internal deployments 调用它。

两者都不会在 production 中允许 browser users 或 external clients。对于 public app，请把 channel 接入你自己的 auth（Clerk、Auth.js、你自己的 OIDC/JWT verification、API-key verifier，或任何 custom `AuthFn`）。Vercel OIDC 是可选的；只有当 Vercel-issued deployment tokens 是你 trust model 的一部分时才使用它。

`eve init` 会 scaffold 一个带 production placeholder 的 `agent/channels/eve.ts`，让你在上线前替换它。生成的 channel 允许 Vercel OIDC 和 localhost，并包含 `placeholderAuth()`；在你把它换成真实 auth 前，它会在 production 中返回面向设置的 401。删除该文件后，eve 会回退到 `[localDev(), vercelOidc()]`，这仍然不会在 production 中允许 browser users。

完整 auth model 和 helper list 见 [Auth & route protection](../guides/auth-and-route-protection)。

## Customization

使用 `onMessage` 在 agent 看到 user message 前添加 request-specific context，并使用 `events` 观察该 channel 创建的 sessions 产生的 stream events：

```ts title="agent/channels/eve.ts"
import { eveChannel, defaultEveAuth } from "eve/channels/eve";
import { localDev, vercelOidc } from "eve/channels/auth";

export default eveChannel({
  auth: [localDev(), vercelOidc()],
  onMessage(ctx, message) {
    const callerId = ctx.eve.caller?.principalId ?? "anonymous";
    return {
      auth: defaultEveAuth(ctx),
      context: [`HTTP caller ${callerId} sent: ${message}`],
    };
  },
  events: {
    "message.completed"(eventData, channel, ctx) {
      console.log("eve response completed", {
        continuationToken: channel.continuationToken,
        sessionId: ctx.session.id,
      });
    },
  },
});
```

## Clients

此 API 的浏览器侧内容位于 [Frontend](../guides/frontend/overview) docs，其中 `useEveAgent` 会从 React UI 驱动 eve channel。

对于 scripts、server-to-server calls、evals、tests 和 custom clients，请使用 [TypeScript SDK](../guides/client/overview)。它会包装 session routes、continuation token、stream cursor 和 reconnect loop。

## 接下来阅读

- [Frontend](../guides/frontend/overview)：用 `useEveAgent` 从 browser UI 驱动 eve channel
- [TypeScript SDK](../guides/client/overview)：从 TypeScript 调用 eve channel
- [Auth & route protection](../guides/auth-and-route-protection)：route auth policy
- [Sessions, runs & streaming](../concepts/sessions-runs-and-streaming)：该 channel 暴露的 routes
