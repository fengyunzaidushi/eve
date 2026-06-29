---
title: "useEveAgent (Vue)"
description: "从浏览器驱动 eve agent session 的 Vue composable。"
---

来自 `eve/vue` 的 `useEveAgent()` 是 Vue app 与 eve session 通信的方式。它会打开 long-lived session、发送 turns，并把每个 stream event fold 到可在 template 中绑定的 reactive data。Nuxt 会通过 [module](./nuxt) auto-import 它，[frontend overview](./overview) 覆盖共享 model。

## 基本用法

从 `eve/vue` 导入 composable。它的 state 以 `ComputedRef`s 暴露，因此在 templates 中会 unwrapped 读取：

```vue
<script setup lang="ts">
import { useEveAgent } from "eve/vue";

const { data } = useEveAgent();
</script>

<template>
  <div v-for="message in data.messages" :key="message.id">
    <p>{{ message.role }}: {{ message.parts }}</p>
  </div>
</template>
```

## 返回内容

| Property  | Type                                               | Description                                                                 |
| --------- | -------------------------------------------------- | --------------------------------------------------------------------------- |
| `data`    | `ComputedRef<TData>`                               | Projected state。使用 default reducer 时为 `EveMessageData`（`messages`）。 |
| `status`  | `ComputedRef<UseEveAgentStatus>`                   | `"ready"`、`"submitted"`、`"streaming"` 或 `"error"`。                      |
| `error`   | `ComputedRef<Error \| undefined>`                  | 最后一次 transport-level error。                                            |
| `events`  | `ComputedRef<readonly HandleMessageStreamEvent[]>` | 此 session 的 raw server events。                                           |
| `session` | `ComputedRef<SessionState>`                        | session state 的 snapshot。                                                 |
| `send`    | `(input: SendTurnPayload) => Promise<void>`        | 发送 text 或 full turn（multi-part、attachments、HITL responses）。         |
| `stop`    | `() => void`                                       | Abort in-flight request。                                                   |
| `reset`   | `() => void`                                       | 清除 state 并启动新 session。                                               |

前五项是 `ComputedRef`s；其余是 methods。可以解构你需要的任何内容，因为 refs 在解构后仍保持 reactivity。在 `<script>` 中用 `.value` 读取，在 `<template>` 中 unwrapped 读取。

## 发送 message

```vue
<script setup lang="ts">
import { ref } from "vue";
import { useEveAgent } from "eve/vue";

const { send } = useEveAgent();
const message = ref("");

async function handleSubmit() {
  const text = message.value.trim();
  if (!text) return;
  message.value = "";
  await send({ message: text });
}
</script>

<template>
  <form @submit.prevent="handleSubmit">
    <input v-model="message" placeholder="Type a message..." />
    <button type="submit">Send</button>
  </form>
</template>
```

对于 plain text 之外的任何内容，请使用 `send()`。Attachments 遵循 AI SDK `UserContent` 格式。请把 file data 作为 base64 `data:` URL 发送，以便它能通过 JSON transport：

```vue
<script setup lang="ts">
import { useEveAgent } from "eve/vue";

const { send } = useEveAgent();

async function onFileChange(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0];
  if (!file) return;
  const bytes = new Uint8Array(await file.arrayBuffer());
  const base64 = btoa(String.fromCodePoint(...bytes));
  await send({
    message: [
      { type: "text", text: "Describe this image." },
      { type: "file", data: `data:${file.type};base64,${base64}`, mediaType: file.type },
    ],
  });
}
</script>
```

## Human-in-the-loop prompts

tool 用 `needsApproval` opt into approval（[Tools](../../tools)）。触发时，pending request 会作为 latest message 上的 `dynamic-tool` part 出现在 `part.toolMetadata?.eve?.inputRequest`。读取它，然后通过同一 session 用 `send({ inputResponses })` 回答：

```ts
import type { EveDynamicToolPart, EveMessagePart } from "eve/vue";

const { data, send } = useEveAgent();

const isDynamicToolPart = (part: EveMessagePart): part is EveDynamicToolPart =>
  part.type === "dynamic-tool";

const request = data.value.messages
  .at(-1)
  ?.parts.filter(isDynamicToolPart)
  .map((part) => part.toolMetadata?.eve?.inputRequest)
  .find((value) => value !== undefined);

if (request) {
  await send({
    inputResponses: [{ requestId: request.requestId, optionId: "approve" }],
  });
}
```

find-and-answer flow 在每个 framework 中都相同。[React hook reference](./overview) 包含更长 walkthrough。

## Stop、reset 和 resume

`stop()` 会 abort in-flight stream。`reset()` 会清空 state 并启动 fresh session。若要跨 reload 保留，请传入 `initialSession` 恢复已保存 session，并用 `onSessionChange` 在 cursor 移动时持久化它：

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

当你的 eve server 不在同一 origin 时，用 `host` 指向它，并通过 `auth` 或 `headers` 附加 credentials。传入 function 时，它会在每次 request 前重新解析：

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
await send({
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

composable 接受几个 per-turn callbacks：

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
import { useEveAgent } from "eve/vue";
import type { EveAgentReducer } from "eve/vue";

interface ToolLog {
  readonly toolCalls: number;
}

const toolCounter: EveAgentReducer<ToolLog> = {
  initial: () => ({ toolCalls: 0 }),
  reduce: (data, event) =>
    event.type === "actions.requested" ? { toolCalls: data.toolCalls + 1 } : data,
};

const agent = useEveAgent({ reducer: toolCounter });
// agent.data.value is ToolLog
```

`reduce(data, event)` 会同时收到权威 eve stream events 和 client projection events（`client.message.submitted`、`client.message.failed`、`client.input.responded`）。如果你希望 projection 中包含 optimistic 和 HITL state，也请处理 client events。否则，对它们原样返回 `data`。

## 接下来阅读

- [Nuxt](./nuxt)：module setup
- [Frontend overview](./overview)：共享 integration model
- [Sessions, runs & streaming](../../concepts/sessions-runs-and-streaming)
