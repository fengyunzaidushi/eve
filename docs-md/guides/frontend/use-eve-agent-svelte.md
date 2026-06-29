---
title: "useEveAgent (Svelte)"
description: "从浏览器驱动 eve agent session 的 Svelte 5 binding。"
---

来自 `eve/svelte` 的 `useEveAgent()` 是 Svelte 5 app 中 eve session 的 browser side。调用一次即可获得可发送 turns 的 long-lived session，每个 stream event 都会 project 到 rune-friendly reactive data 中。在 SvelteKit 上，[Vite plugin](./sveltekit) 会接入 routes。[frontend overview](./overview) 覆盖跨 frameworks 共享的 model。

## 基本用法

从 `eve/svelte` 导入，并直接读取 reactive getters。不需要 `$` prefix：

```svelte
<script lang="ts">
  import { useEveAgent } from "eve/svelte";

  const agent = useEveAgent();
</script>

{#each agent.data.messages as message}
  <p>{message.role}: {JSON.stringify(message.parts)}</p>
{/each}
```

## 返回内容

| Property  | Type                                        | Description                                                                 |
| --------- | ------------------------------------------- | --------------------------------------------------------------------------- |
| `data`    | `TData`                                     | Projected state。使用 default reducer 时为 `EveMessageData`（`messages`）。 |
| `status`  | `UseEveAgentStatus`                         | `"ready"`、`"submitted"`、`"streaming"` 或 `"error"`。                      |
| `error`   | `Error \| undefined`                        | 最后一次 transport-level error。                                            |
| `events`  | `readonly HandleMessageStreamEvent[]`       | 此 session 的 raw server events。                                           |
| `session` | `SessionState`                              | session state 的 snapshot。                                                 |
| `send`    | `(input: SendTurnPayload) => Promise<void>` | 发送 text 或 full turn（multi-part、attachments、HITL responses）。         |
| `stop`    | `() => void`                                | Abort in-flight request。                                                   |
| `reset`   | `() => void`                                | 清除 state 并启动新 session。                                               |

这些 state fields 是 reactive getters，因此可以直接从 templates、`$derived` 或 `$effect` 读取。它们不是 stores，因此不要加 `$` prefix。

## 发送 message

```svelte
<script lang="ts">
  import { useEveAgent } from "eve/svelte";

  const agent = useEveAgent();
  let message = $state("");

  async function handleSubmit() {
    const text = message.trim();
    if (!text) return;
    message = "";
    await agent.send({ message: text });
  }
</script>

<form onsubmit={(event) => {
  event.preventDefault();
  void handleSubmit();
}}>
  <input bind:value={message} placeholder="Type a message..." />
  <button type="submit">Send</button>
</form>
```

当 turn 不只是 plain text 时，请使用 `send()`。Attachments 遵循 AI SDK `UserContent` 格式。请把 file data 作为 base64 `data:` URL 发送，以便它能通过 JSON transport：

```ts
const bytes = new Uint8Array(await file.arrayBuffer());
const base64 = btoa(String.fromCodePoint(...bytes));

await agent.send({
  message: [
    { type: "text", text: "Describe this image." },
    { type: "file", data: `data:${file.type};base64,${base64}`, mediaType: file.type },
  ],
});
```

## Human-in-the-loop prompts

tool 用 `needsApproval` opt into approval（[Tools](../../tools)）。触发时，pending request 会挂在 latest message 的 `dynamic-tool` part 上，路径是 `part.toolMetadata?.eve?.inputRequest`。读取它，然后通过同一 session 用 `agent.send({ inputResponses })` 回答：

```ts
import type { EveDynamicToolPart, EveMessagePart } from "eve/svelte";

const isDynamicToolPart = (part: EveMessagePart): part is EveDynamicToolPart =>
  part.type === "dynamic-tool";

const request = agent.data.messages
  .at(-1)
  ?.parts.filter(isDynamicToolPart)
  .map((part) => part.toolMetadata?.eve?.inputRequest)
  .find((value) => value !== undefined);

if (request) {
  await agent.send({
    inputResponses: [{ requestId: request.requestId, optionId: "approve" }],
  });
}
```

find-and-answer flow 在各 framework 中完全相同。[React hook reference](./overview) 包含更长 walkthrough。

## Stop、reset 和 resume

`stop()` 会 abort in-flight stream。`reset()` 会清空 state 并启动 fresh session。若要跨 reload 恢复，请把之前保存的 state 传给 `initialSession`，并用 `onSessionChange` 在 cursor 推进时持久化它：

```ts
const agent = useEveAgent({
  initialSession: savedSessionState,
  initialEvents: savedEvents,
  onSessionChange: (session) => {
    localStorage.setItem("eve-session", JSON.stringify(session));
  },
});
```

## Custom host 和 credentials

把 `host` 指向不同 origin 上的 eve server，并通过 `auth` 或 `headers` 传入 credentials。提供 function 时，它会在每次 request 前重新解析：

```ts
const agent = useEveAgent({
  host: "https://agent.example.com",
  headers: async () => ({
    authorization: `Bearer ${await getAccessToken()}`,
  }),
});
```

## 为每个 turn 附加 page context

`clientContext` 只为下一次 model call 添加 ephemeral context。Strings（或 string array）会变成 user-role context messages；object 会 JSON-serialize 成一条 context message。它会随 message 或 HITL response 一起发送，永远不会自己 dispatch turn，也不会落入 durable session history。请传给 `send()`：

```ts
await agent.send({
  message: "What should I do on this screen?",
  clientContext: { route: "/billing", plan: "pro", seatsUsed: 4 },
});
```

若要给每个 turn 附加相同 context，而不在每个 call site 中传递它，请传入 `prepareSend`。它会在每次 send 前运行，并返回（可能已增强的）turn：

```ts
const agent = useEveAgent({
  prepareSend: (input) => ({
    ...input,
    clientContext: { route: location.pathname },
  }),
});
```

## Lifecycle callbacks

binding 接受几个 per-turn callbacks：

- `onEvent(event)`：每个 eve stream event 到达时触发。
- `onError(error)`：turn 失败时，携带最后一个 `Error` 触发。
- `onFinish(snapshot)`：turn settle 后，携带 final snapshot 触发。
- `onSessionChange(session)`：session cursor 推进时触发。持久化它以便跨 reload 恢复。

```ts
const agent = useEveAgent({
  onEvent: (event) => console.debug(event.type),
  onError: (error) => console.error(error.message),
  onFinish: (snapshot) => console.log(snapshot.status),
});
```

还有两个选项可调整 turn 行为：

- `optimistic`（默认 `true`）：在 eve 用 `message.received` event 确认前，先把 submitted user messages project 到 `data` 中。这些只是面向 reducer 的 projection events；`events` 仍是权威 eve stream。
- `maxReconnectAttempts`（默认 `3`）：每个 turn 的 stream reconnection budget。

## Custom reducer

default reducer 会把 events project 到 `{ messages }`（`EveMessageData`）中。若要让 `data` 具有不同 shape，请传入实现 `EveAgentReducer<TData>` 的 `reducer`：

```ts
import { useEveAgent } from "eve/svelte";
import type { EveAgentReducer } from "eve/svelte";

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

## 接下来阅读

- [SvelteKit](./sveltekit)：Vite plugin setup
- [Frontend overview](./overview)：共享 integration model
- [Sessions, runs & streaming](../../concepts/sessions-runs-and-streaming)
