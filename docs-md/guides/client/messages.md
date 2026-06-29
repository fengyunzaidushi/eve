---
title: "Messages"
description: "使用 eve/client 发送 text、完整 turn payloads、client context、attachments 和 HITL responses。"
---

`ClientSession` 每次发送一个 turn。fresh session 会在第一次 send 时启动；只要前一个 turn 让 session 处于 waiting，后续 sends 就会继续同一个 conversation。

## 发送 text

向 `send()` 传入 string 以发送 plain text：

```ts
import { Client } from "eve/client";

const client = new Client({ host: "http://127.0.0.1:3000" });
const session = client.session();

const response = await session.send("What is the weather in Brooklyn?");

// Metadata is available as soon as the POST succeeds.
console.log(response.sessionId, response.continuationToken);

const result = await response.result();
console.log(result.status, result.message);
```

`response.result()` 会消费 event stream 并返回 `MessageResult`：

| Field       | Meaning                                                               |
| ----------- | --------------------------------------------------------------------- |
| `message`   | turn 完成时的 final assistant text。                                  |
| `status`    | `"waiting"`、`"completed"` 或 `"failed"`。                            |
| `events`    | turn 期间观察到的所有 stream events。                                 |
| `sessionId` | 用于 streaming 和 inspection 的 Session ID。                          |
| `data`      | turn 请求了 [output schema](./output-schema) 时的 structured output。 |

当 stream 包含 `session.failed` 时，turn 会返回 `status: "failed"`，而不是 throw。Transport 和 route errors 会 throw `ClientError`。

## 发送完整 turn payload

当你需要的不只是 plain text 时，请使用 `send()`：

```ts
const response = await session.send({
  message: "What should I do on this screen?",
  clientContext: {
    route: "/billing",
    plan: "pro",
    seatsUsed: 4,
  },
});

await response.result();
```

`clientContext` 是下一个 model call 使用的 one-turn context。Strings 会变成 user-role context messages，string arrays 会变成多条 context messages，objects 会 JSON-serialize 成一条 context message。它不会持久化到 durable session history，也不会单独 dispatch turn。

## 发送 attachments

`send()` 接受 AI SDK `UserContent`，因此 message 可以混合 text 和 file parts：

```ts
const response = await session.send({
  message: [
    { type: "text", text: "Summarize this report." },
    {
      type: "file",
      data: reportDataUrl,
      mediaType: "application/pdf",
      filename: "report.pdf",
    },
  ],
});

await response.result();
```

对于 local files，请读取文件并发送 base64 `data:` URL：

```ts
import { readFile } from "node:fs/promises";

const bytes = await readFile("report.pdf");
const reportDataUrl = `data:application/pdf;base64,${bytes.toString("base64")}`;

const response = await session.send({
  message: [
    { type: "text", text: "Summarize this report." },
    {
      type: "file",
      data: reportDataUrl,
      mediaType: "application/pdf",
      filename: "report.pdf",
    },
  ],
});

await response.result();
```

## 回答 human input requests

Tools 可以为 approval 暂停，或向用户提问。stream 会发出带有一个或多个 requests 的 `input.requested`。请通过同一个 session 用 `inputResponses` 回复：

```ts
import type { InputRequest } from "eve/client";

let pendingRequests: readonly InputRequest[] = [];

const response = await session.send("Run the deployment checks.");

for await (const event of response) {
  if (event.type === "input.requested") {
    pendingRequests = event.data.requests;
  }
}

const resumed = await session.send({
  inputResponses: pendingRequests.map((request) => ({
    requestId: request.requestId,
    optionId: "approve",
  })),
});

await resumed.result();
```

当 resumed turn 同时需要 human answer 和 follow-up text 时，可以一起发送 `message`、`inputResponses` 和 `clientContext`。

## Single-use responses

`MessageResponse` 是 single-use 的。可以 aggregate 它：

```ts
const result = await response.result();
```

或 stream 它：

```ts
for await (const event of response) {
  console.log(event.type);
}
```

不要对同一个 response 同时做两者。一旦 stream 被消费，`ClientSession` 会为下一个 turn 推进 cursor。

## 接下来阅读

- [Continuations](./continuations)：session cursor 如何推进
- [Streaming](./streaming)：不用 `result()`，而是实时处理 events
- [Tools](../../tools)：配置 approvals 和 question prompts
