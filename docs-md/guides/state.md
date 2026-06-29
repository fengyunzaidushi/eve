---
title: "State"
description: "使用 defineState 提供 durable per-session memory：get() 和 update()，跨 step boundaries 持久化。"
---

`defineState` 是 agent 的 typed、named durable per-session memory slot。当 agent 必须在 conversation turns 之间记住某些内容（running budget、glossary、checklist），而你不想为此搭建 external store 时使用它。值会跨 workflow step boundaries 保留，因此能经受 crashes、redeploys 和持续数天的 sessions。

```ts
import { defineState } from "eve/context";

const budget = defineState("my-agent.budget", () => ({ count: 0, cap: 25 }));
```

向 `defineState(name, initial)` 传入稳定 string `name`（为你的 agent 加 namespace）以及 `initial` function，后者会在 slot 第一次读取时产生 starting value。你会得到 `StateHandle<T>`：

- `get()`：读取当前值。在 context 内首次访问时返回 `initial()`。
- `update(fn)`：用 `fn(current)` 替换值。

在 module scope 声明一次 handle，然后在任何读写该 slot 的地方导入它。请在 tool、hook 或其他 framework-managed runtime code 内使用它：

```ts title="agent/lib/budget.ts"
import { defineState } from "eve/context";

export const budget = defineState("my-agent.budget", () => ({ count: 0, cap: 25 }));
```

```ts title="agent/tools/spend.ts"
import { defineTool } from "eve/tools";
import { z } from "zod";
import { budget } from "../lib/budget.js";
import { runQuery } from "../lib/warehouse.js";

export default defineTool({
  description: "Run a query, counting it against the session budget.",
  inputSchema: z.object({ sql: z.string() }),
  async execute({ sql }) {
    const { count, cap } = budget.get();
    if (count >= cap) throw new Error("Query budget exhausted for this session.");
    budget.update((s) => ({ ...s, count: s.count + 1 }));
    return runQuery(sql);
  },
});
```

`get()` 和 `update()` 要求 active eve context。在 tools、hooks 或 framework-managed code 之外调用它们会 throw。

## 在 turns 之间重置 state

State 默认是 durable 的，不会在 turns 之间重置。如果你希望每个 turn 都有 clean slate，请在 `turn.started` lifecycle [hook](./hooks) 中覆盖它：

```ts title="agent/hooks/reset-budget.ts"
import { defineHook } from "eve/hooks";
import { budget } from "../lib/budget.js";

export default defineHook({
  events: {
    async "turn.started"() {
      budget.update(() => ({ count: 0, cap: 25 }));
    },
  },
});
```

hook 导入与 tool 相同的 module-scope `budget` handle，因此二者读写同一个 slot。

## State 永远不与 subagents 共享

每个 [subagent](../subagents) 都以自己的 fresh state 启动，无论它是 built-in `agent` copy 还是 declared specialist。`defineState` values 永远不会跨越 parent/child boundary，即使 child 是同一个 agent 的副本。

## State vs. connection-side storage

`defineState` 保存 conversation-scoped working memory，其生命周期与 session 相同，包括 counters、current plan，以及用户在本次 conversation 中告诉你的内容。它是 agent 的 short-term memory，会在 session 生命周期内 durable 地持久化。任何必须超过 session 生命周期、跨 sessions 或 users 共享，或独立于 turn 查询的内容，都应放在 external store 中，可以是 [connection](../connections)，也可以是你自己的 database。

## 接下来阅读

- 在 dynamic resolvers 内读取 state → [Dynamic capabilities](./dynamic-capabilities)
- step durability 如何工作 → [Execution model & durability](../concepts/execution-model-and-durability)
- state 旁边可用的 `ctx` accessors → [TypeScript API](../reference/typescript-api)
