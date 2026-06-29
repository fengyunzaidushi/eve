---
title: "概览"
description: "使用 useEveAgent 为 eve agent 添加 browser chat UI。"
---

frontend helpers 会在 eve agent 之上放置 browser chat 或 agent UI。`useEveAgent()` 会打开 durable session、发送 turns、把 reply stream 回来，并把 raw event stream 转成可直接渲染的 state。React 是 reference implementation；[Vue](./use-eve-agent-vue) 和 [Svelte](./use-eve-agent-svelte) 提供同样 surface。

## Integration model

browser UI 是 agent HTTP routes（[eve channel](../../channels/overview)）的 client。有两层负责接入：

- **framework integration** 会把 eve routes 挂载到你的 app origin 上，因此浏览器无需跨 CORS boundary，也无需读取 env var 来找到 agent。选择你的集成：[Next.js](./nextjs)（`withEve`）、[Nuxt](./nuxt)（`eve/nuxt` module）或 [SvelteKit](./sveltekit)（`eveSvelteKit` Vite plugin）。在任何其他 stack 上，hook 会直接访问 same-origin `/eve/v1/*` routes，或由你传入显式 `host`。
- **hook**（`useEveAgent`）保存 session state、streaming、errors 和 composer status。它默认使用 same-origin eve routes，例如 `/eve/v1/session`。

下面的 per-framework 页面会逐步说明 wiring：[Next.js](./nextjs)、[Nuxt](./nuxt) 和 [SvelteKit](./sveltekit)。

对于不需要 framework UI state 的 scripts、server-to-server calls、evals、tests 或 custom clients，请直接使用 [TypeScript SDK](../client/overview)。

## Basic chat (React)

hook 位于 `eve/react`。渲染 `data.messages`，用 `status` gate composer，并用 `send` 发送 text：

```tsx
"use client";

import { useEveAgent } from "eve/react";

export function Chat() {
  const agent = useEveAgent();
  const isBusy = agent.status === "submitted" || agent.status === "streaming";

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        const message = String(form.get("message") ?? "").trim();
        if (message.length > 0) {
          void agent.send({ message });
        }
      }}
    >
      {agent.data.messages.map((message) => (
        <article key={message.id}>
          <header>{message.role}</header>
          {message.parts.map((part, index) =>
            part.type === "text" ? <p key={index}>{part.text}</p> : null,
          )}
        </article>
      ))}
      <input name="message" disabled={isBusy} />
      <button disabled={isBusy} type="submit">
        Send
      </button>
    </form>
  );
}
```

## 返回的 state

`useEveAgent()` 返回当前 UI state 和 commands：

| Field     | 含义                                                                         |
| --------- | ---------------------------------------------------------------------------- |
| `data`    | reducer 生成的 projected UI state。默认是 `{ messages }`。                   |
| `status`  | `"ready"`、`"submitted"`、`"streaming"` 或 `"error"`。驱动 composer。        |
| `error`   | 最后一次 thrown 的 `Error`，如果有。                                         |
| `events`  | 此 session 的 raw eve stream events。                                        |
| `session` | 可序列化 session cursor（`sessionId`、`continuationToken`、`streamIndex`）。 |
| `send`    | 发送 text 或完整 turn payload（multi-part messages、HITL responses）。       |
| `stop`    | Abort active request。                                                       |
| `reset`   | 清除 local events、data、errors 和 local session cursor。                    |

大多数 chat UIs 只需要 `data.messages` 和 `status`。若要渲染 default reducer 未暴露的 lower-level activity，例如 tool calls 和 reasoning deltas，可降到 `events`。

`data.messages` 是遵循 AI SDK `UIMessage` convention 的 `EveMessage[]`，因此可以直接放入任何接受 `UIMessage[]` 的 AI SDK UI primitive。Parts 包括 user text、assistant text、reasoning、tool calls、tool results 和 input requests。

## Sending 和 streaming

向 `send()` 传入 object，可发送 text、multi-part messages、attachments、HITL responses 和 per-turn context：

```tsx
await agent.send({ message: "Summarize this session." });

await agent.send({
  message: [
    { type: "text", text: "What is in this file?" },
    {
      type: "file",
      data: fileDataUrl, // base64 data URL
      mediaType: "application/pdf",
      filename: "report.pdf",
    },
  ],
});
```

Assistant text、reasoning、tool calls 和 tool results 会在到达时 stream 到 `data` 中，`status` 会从 `ready` 变为 `submitted`，再变为 `streaming`，然后回到初始状态。调用 `stop()` 可 abort active request，调用 `reset()` 可清除 local state，让下一次 send 启动 fresh durable session。

## Human-in-the-loop prompts

Tools 通过 `needsApproval` opt into approval，model 也可以用 `ask_question` 提问。server-side model 见 [Human-in-the-loop](../../tools/human-in-the-loop)。无论哪种方式，stream 都会发出 `input.requested` event，pending request 会挂在 latest message 的 `dynamic-tool` part 上，路径是 `part.toolMetadata?.eve?.inputRequest`。读取它，然后用 `send()` 通过同一 session 回答：

```tsx
const request = agent.data.messages
  .at(-1)
  ?.parts.find((part) => part.type === "dynamic-tool" && part.toolMetadata?.eve?.inputRequest)
  ?.toolMetadata?.eve?.inputRequest;

if (request) {
  await agent.send({
    inputResponses: [{ requestId: request.requestId, optionId: "approve" }],
  });
}
```

`request.prompt` 和 `request.options` 会提供渲染 approve/deny UI 所需内容。default reducer 会立即把 part 标记为 responded，然后在 eve stream resumed result 后再次更新它。

## 为每个 turn 附加 page context

`clientContext` 只为下一次 model call 添加 ephemeral context。Strings（或 string array）会变成 user-role context messages；object 会 JSON-serialize 成一条 context message。它会随 message 或 HITL response 一起发送，因此永远不会自己 dispatch turn，也不会落入 durable session history。请直接传给 `send()`：

```tsx
await agent.send({
  message: "What should I do on this screen?",
  clientContext: { route: "/billing", plan: "pro", seatsUsed: 4 },
});
```

若要给每个 turn 附加相同 context，而不在每个 call site 中传递它，请使用 `prepareSend`。它会在每次 send 前运行，并返回（可能已增强的）turn：

```tsx
const agent = useEveAgent({
  prepareSend: (input) => ({
    ...input,
    clientContext: { route: location.pathname },
  }),
});
```

## Lifecycle callbacks

除了 `onSessionChange`，hook 还接受几个 per-turn callbacks：

- `onEvent(event)`：每个 eve stream event 到达时触发。
- `onError(error)`：turn 失败时，携带最后一个 `Error` 触发。
- `onFinish(snapshot)`：turn settle 后，携带 final `{ data, status, session, ... }` snapshot 触发。

```tsx
const agent = useEveAgent({
  onEvent: (event) => console.debug(event.type),
  onError: (error) => toast.error(error.message),
  onFinish: (snapshot) => console.log(snapshot.status),
});
```

还有两个选项可调整 turn 行为：

- `optimistic`（默认 `true`）：在 eve 用 `message.received` event 确认前，先把 submitted user messages project 到 `data` 中。这些只是面向 reducer 的 projection events。`events` 仍是权威 eve stream。
- `maxReconnectAttempts`（默认 `3`）：每个 turn 的 stream reconnection budget。

## Custom reducer

default reducer 会把 events project 到 `{ messages }`（`EveMessageData`）中。当你希望 `data` 有不同 shape 时，请传入实现 `EveAgentReducer<TData>` 的 `reducer`：

```tsx
import { useEveAgent } from "eve/react";
import type { EveAgentReducer } from "eve/react";

interface ToolLog {
  readonly toolCalls: number;
}

const toolCounter: EveAgentReducer<ToolLog> = {
  initial: () => ({ toolCalls: 0 }),
  reduce: (data, event) =>
    event.type === "actions.requested" ? { toolCalls: data.toolCalls + 1 } : data,
};

const agent = useEveAgent({ reducer: toolCounter });
// agent.data is ToolLog
```

`reduce(data, event)` 会同时收到权威 eve stream events 和 client projection events（`client.message.submitted`、`client.message.failed`、`client.input.responded`）。如果你希望 projection 中包含 optimistic 和 HITL state，也请处理 client events。否则，对它们原样返回 `data`。

## Resumable sessions

browser conversation 会 durable 地存在 server 上。持久化 `session` cursor，即可在 reload 后继续：

```tsx
const [initialSession] = useState(() => {
  const raw = localStorage.getItem("eve-session");
  return raw ? JSON.parse(raw) : undefined;
});

const agent = useEveAgent({
  initialSession,
  onSessionChange(session) {
    localStorage.setItem("eve-session", JSON.stringify(session));
  },
});
```

请存储完整 `session` object（`sessionId`、`continuationToken`、`streamIndex`），不要只存单个字段。

## Custom hosts 和 headers

当 eve server 不是 same-origin 时传入 `host`；当 channel 需要 credentials 时传入 `auth` 或 `headers`。Function values 会在每次 HTTP request 前重新解析，包括 reconnects：

```tsx
const agent = useEveAgent({
  host: "https://agent.example.com",
  auth: {
    bearer: async () => await getAccessToken(),
  },
});
```

## Per-framework integration

| Framework | Integration                          | Hook                                             |
| --------- | ------------------------------------ | ------------------------------------------------ |
| Next.js   | [`withEve`](./nextjs)                | [`useEveAgent` (React)](#basic-chat-react)       |
| Nuxt      | [`eve/nuxt` module](./nuxt)          | [`useEveAgent` (Vue)](./use-eve-agent-vue)       |
| SvelteKit | [`eveSvelteKit` plugin](./sveltekit) | [`useEveAgent` (Svelte)](./use-eve-agent-svelte) |
| Any React | same-origin or `host`                | [`useEveAgent` (React)](#basic-chat-react)       |

## 接下来阅读

- [Sessions, runs & streaming](../../concepts/sessions-runs-and-streaming)：event stream 和 session cursor
- [Channels](../../channels/overview)：hook 通信的 HTTP routes
- [TypeScript SDK](../client/overview)：frontend hooks 底层的 lower-level client
- [Next.js](./nextjs)：把 eve 接入 Next.js app 的 step-by-step setup
