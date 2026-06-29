---
title: "Custom Channels"
description: "编写带有 routes、events、metadata、continuation tokens 和 file uploads 的 custom HTTP 与 WebSocket channels。"
---

当 eve 没有为你的 surface 随附 channel 时，你可以构建一个。Custom channels 会暴露 HTTP 或 WebSocket endpoints，解析 incoming requests，启动或恢复 sessions，观察 runtime events，并负责把 delivery 送回你的平台。

## 文件位置和身份

Custom channels 位于 root agent 的 `agent/channels/` 中。Local subagents 目前不声明 channels。

channel 文件主名会成为 channel id，因此 `agent/channels/internal-webhook.ts` 会被寻址为 `internal-webhook`。请把 channel definition 作为 module 的 default export 导出。

## Define a channel

```ts
import { defineChannel, GET, POST } from "eve/channels";

export default defineChannel({
  routes: [
    POST("/message", async (req, { send }) => {
      const body = await req.json();
      const session = await send(body.message, {
        auth: null,
        continuationToken: body.token,
      });

      return Response.json({ sessionId: session.id });
    }),
    GET("/sessions/:sessionId/stream", async (_req, { getSession, params }) => {
      const session = getSession(params.sessionId);
      const stream = await session.getEventStream();

      return new Response(stream, {
        headers: { "content-type": "application/x-ndjson; charset=utf-8" },
      });
    }),
  ],
  events: {
    "message.completed"(event, channel, ctx) {
      // deliver completed messages back to the surface that owns this channel
    },
  },
});
```

使用 `POST()` 和 `GET()` helpers 声明 routes。每个 route handler 都会收到 raw `Request` 和一个 helpers object：

- `send(message, { auth, continuationToken, state? })` 启动或恢复 session。返回 `Session`。
- `getSession(sessionId)` 查找已有 session。返回的 `Session` 暴露 `getEventStream({ startIndex? })` 用于 streaming。
- `receive(channel, ...)` 把 inbound work 交给另一个 channel，用于 cross-channel hand-off。
- `params` 保存从 path pattern 中提取的 route parameters。
- `waitUntil(promise)` 为 background work 延长 request lifetime。
- `requestIp` 是 client IP；当 host 无法提供时为 `null`。

类似 `"message.completed"` 的 event handlers 声明在 `events` key 下。它们会收到 `(eventData, channel, ctx)`，其中 `eventData` 是 event payload，`channel` 携带 platform handles 和 session continuation operations，`ctx` 是 eve `SessionContext`。每种 channel kind 都共享这个签名。唯一例外是 `session.failed`，它只接收 `(eventData, channel)`，没有 `ctx`。

## WebSocket routes

当 custom channel 需要 WebSocket endpoint 时，请使用 `WS()`。route handler 会针对每个 upgrade request 运行一次，并返回该 connection 的 lifecycle hooks：

```ts
import { defineChannel, WS } from "eve/channels";

export default defineChannel({
  routes: [
    WS("/voice/ws", async (_req, { send }) => ({
      async message(_peer, message) {
        await send(message.text(), {
          auth: null,
          continuationToken: "voice-demo",
        });
      },
    })),
  ],
});
```

`WS()` handlers 会收到与 HTTP route handlers 相同的 helpers：`send`、`getSession`、`receive`、`params`、`waitUntil` 和 `requestIp`。返回的 hooks 是 eve-owned structural types，兼容 Nitro/H3 websocket routing，包括 `upgrade`、`open`、`message`、`close` 和 `error`。

### Node upgrade server escape hatch

当你拥有 websocket 行为时，优先使用上面的 `WS()` lifecycle hooks。eve 也暴露 `createWebSocketUpgradeServer()`，用于更窄的场景：某个 third-party SDK 或 framework 期望用 `server.on("upgrade", ...)` 直接绑定到 Node `http.Server`。

```ts
import { defineChannel, WS, createWebSocketUpgradeServer } from "eve/channels";

const bridge = createWebSocketUpgradeServer();

thirdPartySdk.attach(bridge.server);

export default defineChannel({
  routes: [WS("/vendor/ws", bridge.route)],
});
```

bridge server 不会监听自己的 port。它只接收匹配 eve route 的 upgrade events，并且只在 Nitro 暴露 raw Node upgrade request、socket 和 head 的 hosts 上可用。请把它视为适配带 server-binding APIs 的 libraries 的 compatibility adapter，而不是在 eve 中构建 websocket channels 的主要方式。

## Cross-channel hand-off

Route handlers 可以通过 `args.receive(channel, ...)` 在不同 channel 上启动 session。当一个 channel 上的 inbound request 应把 conversation 转到另一个 channel 时使用它，例如 incident webhook 打开 Slack investigation thread。

```ts
import { defineChannel, POST } from "eve/channels";
import slack from "./slack.js";

export default defineChannel({
  routes: [
    POST("/incident", async (req, args) => {
      const incident = await req.json();

      args.waitUntil(
        args.receive(slack, {
          message: `Investigate ${incident.reference}: ${incident.title}`,
          target: { channelId: "C0123ABC" },
          auth: {
            authenticator: "incidentio",
            principalType: "service",
            principalId: incident.actor.id,
            attributes: { reference: incident.reference, severity: incident.severity },
          },
        }),
      );

      return new Response("ok");
    }),
  ],
});
```

语义：

- target channel 的 authored `receive(input, { send })` hook 拥有 continuation-token format 和 initial state。Callers 只提供 `{ message, target, auth }`。
- `auth` 会流入 `session.auth.initiator`，这样 target 的 event handlers 和 agent 的 tools 可以读取谁启动了 session。
- 调用 `args.receive(...)` 不会同时在当前 channel 上启动 session。inbound channel 的 response 就是 route handler 显式返回的内容。
- 第一个参数是 target channel module 的 default export。请直接从 `agent/channels/<name>.ts` 导入它。Identity 按 reference 匹配。

## Channel metadata

channel 可以把 adapter state 的一个子集投影为 metadata，供 instrumentation resolvers、dynamic tool resolvers 以及 dynamic skill 或 instruction resolvers 使用。在 channel config 上定义 `metadata(state)` function：

```ts
import { defineChannel, POST } from "eve/channels";

export default defineChannel({
  state: {
    topic: null as string | null,
    contextMessages: [] as string[],
    internalCounter: 0,
  },

  metadata(state) {
    return {
      topic: state.topic,
      contextMessages: state.contextMessages,
    };
  },

  routes: [
    POST("/start", async (req, { send }) => {
      const body = await req.json();
      await send(body.message, {
        auth: null,
        continuationToken: body.token,
        state: { topic: body.topic, contextMessages: body.context, internalCounter: 0 },
      });

      return new Response("ok");
    }),
  ],
  events: {
    "turn.started"(eventData, channel) {
      channel.state.internalCounter += 1;
    },
  },
});
```

每当 channel event handlers 运行后 adapter state 发生变化时，projection 都会重新求值。Dynamic tool resolvers 通过 `ctx.channel.metadata` 读取它，并用 `isChannel` narrow。完整 consumption pattern 见 [Dynamic capabilities](../guides/dynamic-capabilities)。

当 parent agent dispatch subagent 时，framework 会把 parent 的 channel metadata projection 转发给 child。同一个 `metadata(state)` projector 也服务于 instrumentation metadata resolvers。

## Continuation tokens

channel route 中每次调用 `send(message, { auth, continuationToken, state? })`，都会用 channel-local raw token 寻址一个 session。framework 会在把 token 交给 runtime 前，在其前面加上从 `agent/channels/` 下文件主名派生出的 channel name。

```ts
import { slackContinuationToken } from "eve/channels/slack";
import { twilioContinuationToken } from "eve/channels/twilio";

slackContinuationToken("C0123ABC", "1800000000.001234"); // "C0123ABC:1800000000.001234"
twilioContinuationToken("+15551234567", "+15557654321"); // "+15551234567:+15557654321"
```

Custom channels 需要编写自己的函数来 join identity fields。framework 不会为你派生任何内容；channel 拥有自己的 token format。

当用于寻址 session 的 identity 直到稍后才知道时，channel 可以调用 `session.setContinuationToken(...)` 来 re-key parked session。传入 channel-local raw token；runtime 会保留当前 channel namespace。

`context(state, session)` config option 会构建传给每个 event handler 的 per-step `channel` argument。它接收 channel 的 live adapter `state` 和 `SessionHandle`，并返回 channel-owned context（thread handles、API clients、late-bound callbacks）。framework 会注入 [`ChannelSessionOps`](#define-a-channel)，并把结果作为每个 handler 的第二个位置参数传入。闭包捕获 `session` 让 factory 可以注册稍后 re-key session 的 callbacks。通过返回 context 做出的 state mutations 会写回 adapter state。

```ts
import { defineChannel } from "eve/channels";

import { mintRef } from "./refs.js";

defineChannel<{ ref: string | null }>({
  state: { ref: null },
  context(state, session) {
    return {
      state,
      registerAnchor(ref: string) {
        state.ref = ref;
        session.setContinuationToken(ref);
      },
    };
  },
  events: {
    "message.completed"(eventData, channel) {
      if (!channel.state.ref) channel.registerAnchor(mintRef());
    },
  },
  routes: [
    /* ... */
  ],
});
```

workflow runtime 会在下一个 step boundary dispose 当前 park hook，并在新 token 上注册新的 hook。已经寻址到旧 token 的 inbound deliveries 会被 drop，因此请协调 senders 使用新 token。

## File uploads

`send()` 接受 `string | UserContent`。若要包含 file attachments，请传入混合 text 和 file parts 的 `UserContent` array：

```ts
await send(
  [
    { type: "text", text: body.message },
    { type: "file", data: imageBytes, mediaType: "image/png" },
  ],
  { auth, continuationToken },
);
```

对于 Slack 这类文件位于 authenticated URLs 后面的平台，请把 `URL` object 放进 `FilePart.data`，并在 channel config 上声明 `fetchFile`：

```ts
defineChannel({
  fetchFile(url) {
    if (!url.startsWith("https://files.slack.com/")) return null;
    return fetch(url, { headers: { authorization: `Bearer ${token}` } })
      .then((r) => r.arrayBuffer())
      .then((b) => ({ bytes: Buffer.from(b) }));
  },

  routes: [
    POST("/webhook", async (req, { send }) => {
      await send(
        [
          { type: "text", text: message.text },
          ...message.attachments.map((a) => ({
            type: "file" as const,
            data: new URL(a.url),
            mediaType: a.mediaType,
          })),
        ],
        { auth, continuationToken, state },
      );
    }),
  ],
});
```

`URL` object 会以 string 形式跨过 queue boundary，并在 workflow step 内重新构造。staging pipeline 会用序列化为 string 的 URL（URL 的 `href`）调用 `fetchFile`，这就是示例用 `url.startsWith(...)` 匹配的原因。返回 bytes 可把文件 stage 到 sandbox，返回 `null` 则让 URL 直接传给 model provider。

framework 会处理把 bytes stage 到 sandbox、强制执行 upload policy、为 model call hydrate files，以及在 queue serialization 后重新构造 `URL` objects。

## 接下来阅读

- [Channels overview](./overview)
- [Dynamic capabilities](../guides/dynamic-capabilities)
- [Auth & route protection](../guides/auth-and-route-protection)
