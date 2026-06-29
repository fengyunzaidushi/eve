---
title: "Dynamic Capabilities"
description: "使用 defineDynamic 在 runtime 解析 tools、skills 和 instructions：resolver events、execution order，以及 dynamic tools 如何跨 step boundaries 保留。"
---

`defineDynamic` 会在 runtime 根据 session event 解析 tools、skills 和 instructions，而不是预先声明它们。当正确 capabilities 直到 session 开始才知道时，请使用它，例如它们取决于 caller 是谁、属于哪个 tenant、feature flags 或 external data。[tools](../tools)、[skills](../skills) 和 [instructions](../instructions) guides 都会在介绍 dynamic form 时指向这里。

## Dynamic tools

向 `defineDynamic` 传入 `events` object，其 handlers 可以返回单个 `defineTool(...)`、`Record<string, defineTool(...)>`，或表示没有 tools 的 `null`。每个 entry 都要用 `defineTool()` 包装。wrapper 会给它们打标，让它们的 `execute` functions 能跨 workflow step boundaries 保留。

下面的示例为每个 warehouse table 构建一个 tool。map return 会把 tools 命名为 `slug__key`，因此 model 会看到 `query__orders`、`query__users` 等。

```ts title="agent/tools/query.ts"
import { defineDynamic, defineTool } from "eve/tools";
import { z } from "zod";
import { listTables, runReadOnly } from "../lib/warehouse.js";

export default defineDynamic({
  events: {
    "session.started": async (_event, ctx) =>
      Object.fromEntries(
        (await listTables()).map((t) => [
          t.name,
          defineTool({
            description: `Query ${t.name}. Columns: ${t.columns.join(", ")}`,
            inputSchema: z.object({ sql: z.string() }),
            execute: ({ sql }) => runReadOnly(t.name, sql),
          }),
        ]),
      ),
  },
});
```

### `execute` 必须是 inline function

请把 `execute` 写成直接作为 property value 放置的 inline function expression、arrow 或 method shorthand。bundler transform 不会检测 `execute: myFn` 或 `execute: makeFn()`，因此这些 tools 可以在第一个 step 工作，但无法 survive replay（crash 或 resume 后重新运行 step；见 [Execution model & durability](../concepts/execution-model-and-durability)）。在后续 steps 中，transform 会从存储的 closure variables 重建每个 `execute`，而不是重新运行 resolver，这就是它必须 inline 的原因。

### Naming

| Return shape                | File                       | Tool name(s)                      |
| --------------------------- | -------------------------- | --------------------------------- |
| single `defineTool`         | `agent/tools/analytics.ts` | `analytics`                       |
| map `{ export, query }`     | `agent/tools/tenant.ts`    | `tenant__export`, `tenant__query` |
| map `{ run }`（一个 entry） | `agent/tools/search.ts`    | `search__run`                     |

single return 会产生一个以 file slug 命名的 tool，与 static tool 相同。map 始终使用 `slug__key`，即使只有一个 entry，因此后续添加第二个 entry 也不会重命名第一个。

### Events

| Event             | Resolver runs      | Tools available for         |
| ----------------- | ------------------ | --------------------------- |
| `session.started` | 每个 session 一次  | session 中的每次 model call |
| `turn.started`    | 每个 turn 一次     | turn 中的每次 model call    |
| `step.started`    | 每次 model call 前 | 该次 model call             |

### Execution order

stream event 触发时，会按顺序发生三件事。

1. channel adapter handler 运行，并且 event 写入 durable stream。
2. Stream-event [hooks](./hooks) 触发。
3. 订阅该 event 的 dynamic tool resolvers 运行，并更新 tool set。

tool loop 会在每次 model call 前读取当前 set，因此 mid-turn update 会在下一次 call 中可见。

单个文件可以为多个 events 声明 handlers，并且最近触发的 handler 拥有该文件的 tool set。可以在 `turn.started` 上重新 resolve，以替换 `session.started` 返回的内容：

```ts title="agent/tools/catalog.ts"
import { defineDynamic, defineTool } from "eve/tools";
import { z } from "zod";
import { runReadOnly, searchCatalog } from "../lib/catalog.js";

export default defineDynamic({
  events: {
    "session.started": async (_event, ctx) => ({
      query: defineTool({
        description: "Run a read-only query.",
        inputSchema: z.object({ sql: z.string() }),
        execute: ({ sql }) => runReadOnly(sql),
      }),
    }),
    // On each turn, re-resolve. Replaces this file's session.started tools for later calls.
    "turn.started": async (_event, ctx) => ({
      search: defineTool({
        description: "Search the catalog.",
        inputSchema: z.object({ term: z.string() }),
        execute: ({ term }) => searchCatalog(term),
      }),
    }),
  },
});
```

跨文件的 resolvers 会并发运行。

## Dynamic skills

dynamic skills file 会根据 principal 解析 caller 可以加载哪个 [skill](../skills)。它只在 `session.started` 和 `turn.started` 上 resolve（`step.started` 保留给 dynamic tools）。读取 `ctx.session.auth` 或 channel metadata，并返回 `defineSkill(...)`（以 file slug 命名）或 `null`：

```ts title="agent/skills/team_playbook.ts"
import { defineDynamic, defineSkill } from "eve/skills";
import { PLAYBOOKS } from "../lib/playbooks.js";

export default defineDynamic({
  events: {
    "session.started": (_event, ctx) => {
      const team = ctx.session.auth.current?.attributes.team;
      const markdown = team ? PLAYBOOKS[team] : undefined;
      return markdown ? defineSkill({ markdown }) : null;
    },
  },
});
```

caller 的 team 会获得作为 loadable skill 暴露的专属 playbook；其他人不会获得任何内容。

## Dynamic instructions

dynamic instructions file 会以同样方式解析 per-session system prompt，返回根据 principal、tenant 或 external data 构建的 `defineInstructions(...)`：

```ts title="agent/instructions/persona.ts"
import { defineDynamic, defineInstructions } from "eve/instructions";

export default defineDynamic({
  events: {
    "session.started": (_event, ctx) => {
      const plan = ctx.session.auth.current?.attributes.plan ?? "free";
      return defineInstructions({
        markdown: `The caller is on the ${plan} plan. Match the depth of your answers to it.`,
      });
    },
  },
});
```

二者都会在 prompt 组装前 resolve，因此 model 会为当前 caller 看到正确的 instructions 和 skill set，而这些 context 不会到达其他人。

## 接下来阅读

- 它基于的 static tool 基础 → [Tools](../tools)
- built-in tools 以及如何覆盖它们 → [Default harness](../concepts/default-harness)
- 为访问 external service 的 tool 或 connection 进行认证 → [Auth & route protection](./auth-and-route-protection)
- resolvers 可读取的 durable per-session memory → [State](./state)
