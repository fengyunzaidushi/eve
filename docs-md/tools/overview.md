---
title: "Tools"
description: "定义 agent 可以调用的 typed actions，并让敏感 action 需要 human approval。"
url: /tools
---

tool 是 agent 可以调用的 typed action，例如访问 API、运行 query 或写入文件。action 保留在你控制的代码中。Tools 会在你的 app runtime 中运行，并可完整访问 `process.env`，而不是在 [sandbox](/docs/sandbox) 中运行。

## 定义 tool

文件名就是 model 看到的 tool 名称。位于 `agent/tools/get_weather.ts` 的文件会暴露为 `get_weather`。

```ts title="agent/tools/get_weather.ts"
import { defineTool } from "eve/tools";
import { z } from "zod";

export default defineTool({
  description: "Get the current weather for a city.",
  inputSchema: z.object({ city: z.string().min(1) }),
  async execute({ city }, ctx) {
    return { city, condition: "Sunny", temperatureF: 72 };
  },
});
```

tool definition 需要：

- `agent/tools/` 下的 filename slug，也就是面向 model 的名称。
- `description`：写给 model 的 tool 功能说明。
- `inputSchema`：Zod schema（或任何 Standard Schema，或 plain JSON Schema object）。必填。没有输入时传入 `z.object({})`。Zod 和 Standard Schema 会推断 `execute` 中的 `input` 类型。Plain JSON Schema 会将其类型标为 `Record<string, unknown>`。
- `execute(input, ctx)`：实现。可以同步，也可以异步。

当 tool 返回 structured data 时，可以添加可选的 `outputSchema`。使用 Zod 或 Standard Schema 时，它也会为 `execute` 返回值提供类型。

### `ctx` 参数

`execute` 会收到携带 runtime accessors 的 `ctx`：

- `ctx.session`：session metadata、turn、auth、parent lineage。
- `ctx.getSandbox()`：live [sandbox](/docs/sandbox) handle。
- `ctx.getSkill(id)`：读取 packaged [skill](/docs/skills) 的 metadata 和 files。

在 app runtime 中运行，意味着 tool 可以从 `lib/` 导入共享代码、读取 `process.env`，并参与 eve 的 durable pause/resume model。

eve 在 discovery 期间绝不会运行 authored tools。model 会先看到 descriptors，只有它实际调用的内容才会执行。已完成的 steps 永远不会重新运行；eve 会 replay 已记录的结果。执行中断的 step 会重新运行，因此请让扣款或发送邮件等非幂等 side effects 变成幂等，或用 approval gate 住它们。

## 用 human approval gate tool

tool 可以要求先由人员签核再运行。使用来自 `eve/tools/approval` 的 helpers 设置 `needsApproval`：

```ts title="agent/tools/refund_charge.ts"
import { defineTool } from "eve/tools";
import { always } from "eve/tools/approval";
import { z } from "zod";

export default defineTool({
  description: "Refund a charge.",
  inputSchema: z.object({ chargeId: z.string(), amount: z.number() }),
  needsApproval: always(), // or once() / never() / a predicate
  async execute(input) {
    return refund(input);
  },
});
```

Approval 是 eve [human-in-the-loop](./human-in-the-loop) model 的一部分。该页面介绍 `always/once/never` helpers、依赖输入的 predicates，以及 gated call 如何 durable 地暂停和恢复。

## 用 `toModelOutput` 塑造 model 看到的内容

默认情况下，model 会看到完整的 `execute` 返回值。当 tool 返回 channel 渲染所需的 rich data，而 model 只需要要点时，可以用 `toModelOutput` 将其投影为更小的内容：

```ts
toModelOutput(output) {
  return { type: "text", value: `Report for ${output.domain}: score ${output.score}.` };
},
```

`toModelOutput` 会收到完整、类型化的 `execute` 返回值，并且只影响 model。Channel event handlers 和 hooks 仍会在 `action.result` 上拿到完整 output，因此 channel 可以渲染 model 永远看不到的 rich platform output（例如 Slack Block Kit）。返回 `{ type: "text", value }` 表示摘要，或返回 `{ type: "json", value }` 表示更小的 object。

不要从 tools 返回 secrets、credentials、不必要的 personal data 或无边界的 sensitive content。返回前请过滤、最小化并 redact tool outputs。

## 接下来阅读

- [Human-in-the-loop](./human-in-the-loop)：用 approval gate tool，或让 agent 提问
- [Skills](/docs/skills)：model 在相关时加载的 on-demand procedures
- [Default harness](/docs/concepts/default-harness)：built-in tools 以及如何覆盖或禁用它们
- [Dynamic capabilities](/docs/guides/dynamic-capabilities)：使用 `defineDynamic` 按 session 解析 tool 集合
- [Auth & route protection](/docs/guides/auth-and-route-protection)：为访问外部服务的 tool 进行认证
