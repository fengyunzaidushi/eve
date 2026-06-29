---
title: "记住 Definitions"
description: "Build an Agent 教程第 6 部分。使用 defineState 跨 turns 记住团队的 metric glossary。"
---

每个团队都有给 analytics assistant 使用的内部 definitions。“Active” 表示过去 30 天内有购买，revenue 是扣除退款后的净额，“week” 从周一开始。每个 turn 都重新解释这些内容是一种浪费。State 给 agent 提供了保存它们的位置。

`defineState(name, initial)` 会创建一个类型化、具名的 slot，它能在 session 内跨 step 和 turn boundaries 保留。你用 `get()` 读取它，用 `update()` 修改它。

## 定义 glossary slot

```ts title="agent/lib/glossary.ts"
import { defineState } from "eve/context";

export interface Glossary {
  readonly terms: Readonly<Record<string, string>>;
}

export const glossary = defineState<Glossary>("analytics.glossary", () => ({
  terms: {},
}));
```

## 读写它的 tools

```ts title="agent/tools/define_metric.ts"
import { defineTool } from "eve/tools";
import { z } from "zod";
import { glossary } from "../lib/glossary.js";

export default defineTool({
  description: "Record the team's definition of a metric so it persists across turns.",
  inputSchema: z.object({ term: z.string(), meaning: z.string() }),
  async execute({ term, meaning }) {
    glossary.update((g) => ({ terms: { ...g.terms, [term]: meaning } }));
    return glossary.get();
  },
});
```

```ts title="agent/tools/recall_metrics.ts"
import { defineTool } from "eve/tools";
import { z } from "zod";
import { glossary } from "../lib/glossary.js";

export default defineTool({
  description: "Read the team's recorded metric definitions.",
  inputSchema: z.object({}),
  async execute() {
    return glossary.get();
  },
});
```

## 查看它如何持久保留

```text
> For us, an active customer is one with a purchase in the last 30 days.
  Remember that.
  → calls define_metric("active customer", "purchase in the last 30 days")

> How many active customers do we have?
  → recalls the definition, writes the matching SQL, answers
```

第二个 turn 是同一个 session 中的独立 turn，但 definition 仍然存在。State 会在 step boundaries checkpoint，因此这与 [Step 2](./how-it-runs) 中的 durability 是同一套机制，只是现在应用到了你自己的数据上。

State 的作用域限定在 session 内，并按 agent 隔离，因此 subagent 会以 fresh state 启动，永远看不到 parent 的 state。需要在每个 turn 重置某些内容？在 lifecycle hook 中调用 `update(() => fresh)`。更多内容见 [State](../guides/state)。

→ 下一步：[Team playbooks](./team-playbooks)

了解更多：[State](../guides/state)
