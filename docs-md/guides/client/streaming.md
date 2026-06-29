---
title: "Streaming"
description: "实时消费 eve client stream events，按 event index 重连，并 aggregate turn results。"
---

每次 `ClientSession.send()` call 都会 post turn，然后读取 session 的 NDJSON（newline-delimited JSON）event stream。`MessageResponse` 提供两种消费 stream 的方式：用 `result()` aggregate，或实时 iterate。

## Aggregate turn

当你只需要 final turn summary 时，请使用 `result()`：

```ts
const response = await session.send("Summarize the latest forecast.");
const result = await response.result();

console.log(result.status);
console.log(result.message);
console.log(result.events.length);
```

这会消费 stream，直到当前 turn boundary：

- `session.waiting`
- `session.completed`
- `session.failed`

## 实时 stream events

当你想渲染 progress 时，请使用 `for await...of`：

```ts
const response = await session.send("Draft a plan and show your work.");

for await (const event of response) {
  if (event.type === "message.appended") {
    process.stdout.write(event.data.messageDelta);
  }

  if (event.type === "message.completed" && event.data.finishReason !== "tool-calls") {
    console.log("\nfinal:", event.data.message);
  }
}
```

`message.appended` 和 `reasoning.appended` 是 incremental delta events。它们的 completed forms，即 `message.completed` 和 `reasoning.completed`，是不渲染 deltas 的 clients 的兼容路径。

## 处理 event types

当你需要 exhaustiveness 或 helpers 时，从 `eve/client` 导入 event types：

```ts
import type { HandleMessageStreamEvent } from "eve/client";
import { isCurrentTurnBoundaryEvent } from "eve/client";

function handleEvent(event: HandleMessageStreamEvent) {
  if (isCurrentTurnBoundaryEvent(event)) {
    console.log("turn settled:", event.type);
  }
}
```

最常见的 UI events 是：

| Event                | Use                                                          |
| -------------------- | ------------------------------------------------------------ |
| `message.received`   | 确认 user message 已落地。                                   |
| `reasoning.appended` | 当 model 提供 reasoning deltas 时渲染它们。                  |
| `message.appended`   | 渲染 assistant text deltas。                                 |
| `actions.requested`  | 展示 model 请求的 tool calls。                               |
| `action.result`      | 展示 tool call results。                                     |
| `input.requested`    | 为 approval 或 question answer 暂停 UI。                     |
| `result.completed`   | 从 [output schema](./output-schema) 读取 structured output。 |
| `session.waiting`    | 为下一个 turn 启用 composer。                                |
| `session.completed`  | 标记 conversation terminal。                                 |
| `session.failed`     | 标记 conversation failed。                                   |

完整 event table 见 [Sessions, runs & streaming](../../concepts/sessions-runs-and-streaming)。

## Reconnection

client 会在 transient stream disconnects 后重连。它会从当前 session 中已消费的 events 数量处恢复：

```ts
const client = new Client({
  host: "https://agent.example.com",
  maxReconnectAttempts: 5,
});
```

`maxReconnectAttempts` 按 turn 计。默认值是 `3`。

## Open a stream manually

当你已经有 session cursor，并且只需要 attach 到已有 stream 时，请使用 `session.stream()`：

```ts
const session = client.session({
  continuationToken: "eve:6c8b1f2e-3d4a-4b9c-8e21-9f0a1b2c3d4e",
  sessionId: "wrun_01ARYZ6S41TSV4RRFFQ69G5FAV",
  streamIndex: 10,
});

for await (const event of session.stream()) {
  console.log(event.type);
}
```

传入 `startIndex` 可覆盖已存储 cursor：

```ts
for await (const event of session.stream({ startIndex: 0 })) {
  console.log(event.type);
}
```

如果 session 没有 `sessionId`，`stream()` 会 throw，因为第一次 send 前没有可 attach 的 stream。

## Abort request

传入 `AbortSignal` 可以取消 POST 或 stream。请在 awaiting `send()` 前设置 timeout，让它同时覆盖 POST 和 stream：

```ts
const controller = new AbortController();
const timeout = setTimeout(() => controller.abort(), 10_000);

const response = await session.send({
  message: "Run a long analysis.",
  signal: controller.signal,
});

for await (const event of response) {
  console.log(event.type);
}

clearTimeout(timeout);
```

response 被 aborted 后，请为下一个 turn 创建新的 send。不要复用同一个 `MessageResponse`。

## 接下来阅读

- [Messages](./messages)：创建 streams 的 send APIs
- [Continuations](./continuations)：stream cursors 如何持久化
- [Output schema](./output-schema)：消费 `result.completed`
