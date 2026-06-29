---
title: "Continuations"
description: "使用 continuation tokens、session IDs 和 stream cursors 持久化并恢复 eve client sessions。"
---

每个 eve client turn 都会返回两个 handles，混淆它们是常见错误。TypeScript client 会为你 tracking 二者：

- `continuationToken`：resume handle。用它发送下一个 user turn。
- `sessionId`：stream-and-inspect handle。用它 attach 到 event history。

`ClientSession` 还会 tracking `streamIndex`，也就是已消费 events 的数量。这三个字段共同组成 `SessionState`。

## 读取并持久化 state

streamed turn 完成后，读取 `session.state`：

```ts
const session = client.session();

const response = await session.send("Create a launch checklist.");
await response.result();

await saveSessionState(session.state);
```

存储完整 state object：

```ts
interface SessionState {
  continuationToken?: string;
  sessionId?: string;
  streamIndex: number;
}
```

continuation token 用于恢复 conversation。session ID 和 stream index 让 client 可以重连到正确的 stream position，而不 replay 已消费的 events。

## 恢复已保存 session

把保存的 state 传回 `client.session()`：

```ts
import type { SessionState } from "eve/client";

const saved = (await loadSessionState()) as SessionState;
const session = client.session(saved);

const response = await session.send("Now shorten it.");
const result = await response.result();
console.log(result.message);
```

如果你只有 continuation token，可以将它作为 shorthand 传入：

```ts
const session = client.session(continuationToken);
const response = await session.send("Continue where we left off.");
await response.result();
```

shorthand 可以发送 follow-up，但它不知道 previous stream cursor。当你控制 persistence 时，优先使用完整 `SessionState`。

## Waiting、completed 和 failed sessions

当 turn 以 `session.waiting` 结束时，client 会保留 state，让下一次 send 继续 conversation。

当 turn 以 `session.completed` 或 `session.failed` 结束时，client 会重置本地 state。下一次 send 会启动 fresh durable session：

```ts
const response = await session.send("Do this one-shot task.");
const result = await response.result();

if (result.status === "completed") {
  // session.state is now a fresh cursor: { streamIndex: 0 }
}
```

这与 runtime contract 一致：只有 waiting sessions 可以接受下一次 user input。

## Multiple sessions

为每个 conversation 创建独立 `ClientSession`：

```ts
const research = client.session();
const support = client.session();

const researchResponse = await research.send("Research competitors.");
await researchResponse.result();

const supportResponse = await support.send("Draft a support reply.");
await supportResponse.result();

await save("research", research.state);
await save("support", support.state);
```

共享的 `Client` 只拥有 host、auth、headers 和 reconnect settings。Conversation state 位于每个 `ClientSession` 上。

## 重连已有 stream

当 session 已经有 `sessionId` 时，`session.stream()` 会从保存的 cursor 重新 attach 到其 stream。restart 后恢复保存的 `SessionState` 是这样做的常见原因：

```ts
const session = client.session(savedState);

for await (const event of session.stream()) {
  console.log(event.type);
}
```

`stream()` 会 attach 到已有 run；若要发送新的 user input，请使用 `send()`。关于用 `startIndex` 覆盖 cursor 和完整 reconnection model，见 [Streaming](./streaming#open-a-stream-manually)。

## 接下来阅读

- [Streaming](./streaming)：stream events 并按 index 重连
- [Sessions, runs & streaming](../../concepts/sessions-runs-and-streaming)：raw HTTP contract
- [eve channel](../../channels/eve)：continuation tokens 的来源
