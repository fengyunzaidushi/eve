---
title: "Hooks"
description: "从 agent/hooks/ 订阅 runtime stream events。"
---

Hooks 是 eve 为 runtime event stream 提供的 authored extension points。hook 会订阅 stream events，并在每个 event durable 记录后运行 side effects，例如 audit logging、metrics and alerting，或把每个 session 和 message 持久化到你自己的 database 以供 analytics 使用。若要观察 agent 的行为，但不想编写 tool、context provider（跨 step 可用的值）或 channel adapter handler（定义在 channel adapter 上的 handler；见 [Channels](../channels)），请使用 hook。

## 定义 hook

```ts title="agent/hooks/audit.ts"
import { defineHook } from "eve/hooks";

export default defineHook({
  events: {
    async "session.started"(_event, ctx) {
      console.info("session started", { sessionId: ctx.session.id });
    },
    async "message.completed"(event) {
      console.info("model finished", { length: event.data.message?.length ?? 0 });
    },
  },
});
```

slug 是 path-relative basename。`agent/hooks/audit.ts` 会变成 `"audit"`，`agent/hooks/auth/load-profile.ts` 会变成 `"auth/load-profile"`。

`defineHook`、`HookDefinition` 和 `HookContext` 位于 `eve/hooks`。

hook file 会在 `events` map 下声明 stream-event subscribers，以 event type 为 key，`*` 匹配每个 event。你可以订阅 [Sessions, runs and streaming](../concepts/sessions-runs-and-streaming) 中记录的 runtime stream vocabulary 里的任何 event，包括 lifecycle events `session.started`、`turn.completed`、`message.completed` 和 `action.result`。Handlers 只能 observe。它们不能注入 model context。若要贡献 runtime model messages，请在 `agent/instructions/` 中使用 `defineDynamic` 和 `defineInstructions`。

## Hook structure 和 context

每个 handler 都会收到同一个 `HookContext`：

```ts
interface HookContext {
  readonly agent: { readonly name: string; readonly nodeId?: string };
  readonly channel: { readonly kind?: string; readonly continuationToken?: string };
  readonly session: { readonly id: string };
}
```

### Narrowing tool results

`toolResultFrom` 会把 `action.result` event narrow 到特定 authored tool 或 MCP connection，并返回 typed output。从 `eve/tools` 导入它：

```ts
import { defineHook } from "eve/hooks";
import { toolResultFrom } from "eve/tools";
import getWeather from "../tools/get-weather";
import linear from "../connections/linear";

export default defineHook({
  events: {
    "action.result"(event) {
      // Authored tool: output is typed as the tool's return type
      const weather = toolResultFrom(event.data.result, getWeather);
      if (weather) {
        console.log(weather.output.temperature);
      }

      // MCP connection: output is unknown, toolName is qualified
      const linearResult = toolResultFrom(event.data.result, linear);
      if (linearResult) {
        console.log(linearResult.connectionToolName, linearResult.output);
      }
    },
  },
});
```

当 result 不匹配，或 `isError` 为 `true` 时，返回 `undefined`。对于 authored tools，返回值包含 `{ output, toolName, callId }`，其中 `output` 类型为该 tool 的 `TOutput`。对于 connections，返回值包含 `{ output, toolName, connectionToolName, callId }`，其中 `output` 为 `unknown`。

## Execution order

stream event 触发时，会按顺序发生三件事：

1. Emit。channel adapter handler 运行，然后 event 写入 durable stream。
2. Hooks。Stream-event hooks 触发（先 typed handlers，再 `*` wildcard）。返回值会被忽略。
3. Dynamic tool resolvers。订阅该 event type 的 resolvers 运行，并更新 tool set。

Hooks 始终在 event durable 记录后运行，因此即使 hook throw，stream 仍保持一致。

## hook throw 时会发生什么

thrown handler 会通过 emit composer 传播，并表现为 `turn.failed`。如果订阅 failure-cascade event 的 hook 也 throw，它会升级为 `session.failed`。若要在 hook 内获得更稳妥的语义，请用 `try`/`catch` 包装 body。eve 会把 thrown hook 视为真实 failure。

## Subagent isolation

Subagents 可以带有自己的 `agent/hooks/` 目录。Subagent hooks 只在 subagent scope 内触发。Parent-agent hooks 不会为 subagent turns 触发，subagent hooks 也只看到 subagent 自己的 context。

## Hook vs tool vs provider

| Need                                               | Use                                           |
| -------------------------------------------------- | --------------------------------------------- |
| Observe runtime events（audit、metrics、alerting） | `events.<type>`（或 channel adapter handler） |
| 按需向 model 提供 structured input                 | tool                                          |
| 让某个值在整个 step 中可用                         | context provider                              |
| 订阅 platform-specific events                      | channel adapter handler                       |

Stream-event hooks 和 channel adapter event handlers 在结构上相同。当你编写 adapter-specific behavior 时，选择 channel adapter handler；当你编写应跨每个 channel 触发的 agent-level behavior 时，选择 `events.*`。两者同时注册时都会触发。

## 接下来阅读

- [Tools](../tools)
- [Context control](../concepts/context-control)
- [Session context](../reference/typescript-api)
- [Sessions, runs and streaming](../concepts/sessions-runs-and-streaming)
