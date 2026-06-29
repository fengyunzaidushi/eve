---
title: "Output Schema"
description: "从 eve client turns 请求 structured results，并从 MessageResult 读取 typed data。"
---

当 caller 需要 structured data，而不只是 assistant text 时，请在 client turn 上传入 `outputSchema`。runtime 会让 model 在 turn settle 前满足 schema，然后以 `result.completed` 发出 final payload。

## JSON Schema

Raw JSON Schema objects 可以直接使用：

```ts
import { Client } from "eve/client";

interface Summary {
  title: string;
  count: number;
}

const outputSchema = {
  type: "object",
  properties: {
    title: { type: "string" },
    count: { type: "integer" },
  },
  required: ["title", "count"],
} as const;

const client = new Client({ host: "http://127.0.0.1:3000" });
const session = client.session();

const response = await session.send<Summary>({
  message: "Summarize this turn.",
  outputSchema,
});

const result = await response.result();

console.log(result.data?.title);
console.log(result.data?.count);
```

当 turn 没有产生 structured result 时，`result.data` 是 `undefined`。

## Standard Schema

client 也接受 Zod、Valibot 和 ArkType 等 Standard Schema implementations。schema 会在 request 发送前 lowered 为 JSON Schema：

```ts
import { z } from "zod";

const summarySchema = z.object({
  title: z.string(),
  count: z.number().int(),
});

type Summary = z.infer<typeof summarySchema>;

const response = await session.send<Summary>({
  message: "Summarize this turn.",
  outputSchema: summarySchema,
});

const { data } = await response.result();
```

server 是 validation 的权威。client 会根据你的 generic 和 schema 为 `MessageResult.data` 提供类型，但不会在 client-side 重新 validate streamed payload。

## Stream result event

如果你手动消费 events，请读取 `result.completed`：

```ts
const response = await session.send<Summary>({
  message: "Summarize this turn.",
  outputSchema,
});

for await (const event of response) {
  if (event.type === "result.completed") {
    const summary = event.data.result as Summary;
    console.log(summary.title);
  }
}
```

如果 consumed event list 中出现多个 `result.completed`，`result()` 会把最近的一个作为 `data` 返回。

## 发送带 output schema 的 payloads

`outputSchema` 可用于 string shorthand 和 object-form sends。当你需要 schema、headers、signal、context、attachments 或 HITL responses 时，请使用 object form：

```ts
const response = await session.send<Summary>({
  message: "Summarize this PDF.",
  clientContext: { reportId: "rpt_123" },
  outputSchema,
});

const result = await response.result();
```

它也适用于 follow-up turns 和 HITL response turns：

```ts
const response = await session.send({
  inputResponses: [{ requestId, optionId: "approve" }],
  message: "Return the approved action as structured output.",
  outputSchema,
});

const result = await response.result();
```

## Per-turn scope

Client `outputSchema` 的作用域限定在发送它的 turn 上。它不会成为 conversation 的永久设置：

```ts
const response = await session.send({ message: "Return a structured summary.", outputSchema });
await response.result();

const followUpResponse = await session.send("Now answer normally.");
const followUp = await followUpResponse.result();

console.log(followUp.data); // undefined unless this turn also requested a schema
```

对于属于 agent 或 subagent definition 本身的 task-mode output，见 [`agent.ts`](../../agent-config#outputschema) 和 [Subagents](../../subagents)。

## 接下来阅读

- [Messages](./messages)：使用 `send()` 发送 turns
- [Streaming](./streaming)：实时处理 `result.completed`
- [`agent.ts`](../../agent-config#outputschema)：配置的 task-mode output
