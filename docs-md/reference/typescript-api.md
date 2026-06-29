---
title: "TypeScript API"
description: "define* helpers、runtime ctx，以及每个 API 从哪里 import。"
---

这是 `eve` package 的 public surface：你 author 时使用的 `define*` helpers、它们在 runtime 接收的 `ctx`，以及每个 API 的 import path。完整 contract 位于 `packages/eve/src/public/index.ts`；任何未从那里 export 的内容都是 framework internal。

identity 来自 filesystem，而不是你设置的字段。`agent/tools/get_weather.ts` 中的 tool 是 `get_weather`，`agent/connections/linear.ts` 中的 connection 是 `linear`，所以 definition 不携带 `name` 或 `id`。

大多数文件形状相同：import 一个 helper，然后 default-export 结果。

```ts title="agent/agent.ts"
import { defineAgent } from "eve";

export default defineAgent({ model: "anthropic/claude-opus-4.8" });
```

```ts title="agent/tools/get_weather.ts"
import { defineTool } from "eve/tools";
import { z } from "zod";

export default defineTool({
  description: "Get the weather for a city.",
  inputSchema: z.object({ city: z.string() }),
  async execute({ city }, ctx) {
    return { city, condition: "Sunny" };
  },
});
```

## define\* helpers

| Helper                                                 | Import from                                   | Authored at                          | Guide                                                  |
| ------------------------------------------------------ | --------------------------------------------- | ------------------------------------ | ------------------------------------------------------ |
| `defineAgent`                                          | `eve`                                         | `agent/agent.ts`                     | [agent.ts](../agent-config)                            |
| `defineTool`                                           | `eve/tools`                                   | `agent/tools/<name>.ts`              | [Tools](../tools)                                      |
| `defineDynamic`                                        | `eve/tools`, `eve/skills`, `eve/instructions` | `agent/{tools,skills,instructions}/` | [Dynamic capabilities](../guides/dynamic-capabilities) |
| `defineMcpClientConnection`, `defineOpenAPIConnection` | `eve/connections`                             | `agent/connections/<name>.ts`        | [Connections](../connections)                          |
| `defineChannel`                                        | `eve/channels`                                | `agent/channels/<name>.ts`           | [Custom channels](../channels/custom)                  |
| `eveChannel`, `slackChannel`, and the other platforms  | `eve/channels/<platform>`                     | `agent/channels/<platform>.ts`       | [Channels](../channels/overview)                       |
| `defineSkill`                                          | `eve/skills`                                  | `agent/skills/<name>.ts`             | [Skills](../skills)                                    |
| `defineInstructions`                                   | `eve/instructions`                            | `agent/instructions.ts`              | [Instructions](../instructions)                        |
| `defineHook`                                           | `eve/hooks`                                   | `agent/hooks/<slug>.ts`              | [Hooks](../guides/hooks)                               |
| `defineSchedule`                                       | `eve/schedules`                               | `agent/schedules/<name>.ts`          | [Schedules](../schedules)                              |
| `defineState`                                          | `eve/context`                                 | tools, hooks, lifecycle              | [Session context](../guides/session-context)           |
| `defineSandbox`                                        | `eve/sandbox`                                 | `agent/sandbox.ts`                   | [Sandbox](../sandbox)                                  |
| `defineInstrumentation`                                | `eve/instrumentation`                         | `agent/instrumentation.ts`           | [instrumentation.ts](../guides/instrumentation)        |
| `defineRemoteAgent`                                    | `eve`                                         | `agent/subagents/<id>/agent.ts`      | [Remote agents](../guides/remote-agents)               |
| `defineEval`                                           | `eve/evals`                                   | `evals/*.eval.ts`                    | [Evals](../evals/overview)                             |
| `defineEvalConfig`                                     | `eve/evals`                                   | `evals/evals.config.ts`              | [Evals](../evals/overview)                             |
| `useEveAgent`                                          | `eve/react`, `eve/vue`, `eve/svelte`          | frontend                             | [Frontend](../guides/frontend/overview)                |

还有一些非 `define*` helpers 补全这个集合：来自 `eve/tools` 的 `disableTool` 和 `ExperimentalWorkflow`（见 [Default harness](../concepts/default-harness)），来自 `eve/channels` 的 route verbs `GET`/`POST`/`PUT`/`PATCH`/`DELETE`/`WS`，来自 `eve/tools/approval` 的 approval predicates `always`/`once`/`never`，以及来自 `eve/channels/auth` 的 channel auth helpers `localDev`/`vercelOidc`/`placeholderAuth`。要包装 built-in tool，请从 `eve/tools/defaults` import 它的 default value（`bash`、`readFile`、`writeFile`、`glob`、`grep`、`webFetch`、`webSearch`、`todo`、`loadSkill`）。

## Runtime context (`ctx`)

`ctx` 会传给你的 tool `execute`、hook handlers 和 channel event handlers。它只在 authored code 运行期间 live，因此在 module top level 访问它会 throw。完整模型见 [Session context](../guides/session-context)。

| Member                     | 用途                                                            |
| -------------------------- | --------------------------------------------------------------- |
| `ctx.session`              | 当前 session、turn、auth 和可选 parent lineage（read-only）     |
| `ctx.getSandbox()`         | 当前 agent 的 live sandbox handle                               |
| `ctx.getSkill(identifier)` | 当前 agent 可见的 named skill handle                            |
| `ctx.getToken()`           | 解析 tool 声明的 `auth` 的 bearer token（没有 `auth` 时 throw） |
| `ctx.requireAuth()`        | 在继续前强制触发 tool authorization flow                        |

## Imports at a glance

| Import                                                      | Holds                                                                |
| ----------------------------------------------------------- | -------------------------------------------------------------------- |
| `eve`                                                       | `defineAgent`, `defineRemoteAgent`                                   |
| `eve/tools`                                                 | `defineTool`, `defineDynamic`, `disableTool`, `ExperimentalWorkflow` |
| `eve/tools/defaults`                                        | built-in tools 的 plain values                                       |
| `eve/tools/approval`                                        | `always`, `once`, `never`                                            |
| `eve/connections`                                           | `defineMcpClientConnection`, `defineOpenAPIConnection`               |
| `eve/channels`                                              | `defineChannel`, route verbs                                         |
| `eve/channels/eve`                                          | `eveChannel`                                                         |
| `eve/channels/auth`                                         | `localDev`, `vercelOidc`, `placeholderAuth`                          |
| `eve/channels/{slack,discord,teams,telegram,twilio,github}` | platform channel factories                                           |
| `eve/hooks`                                                 | `defineHook`                                                         |
| `eve/schedules`                                             | `defineSchedule`                                                     |
| `eve/skills`                                                | `defineSkill`, `defineDynamic`                                       |
| `eve/instructions`                                          | `defineInstructions`, `defineDynamic`                                |
| `eve/context`                                               | `defineState`, session 和 state types                                |
| `eve/sandbox`                                               | `defineSandbox`, backends                                            |
| `eve/instrumentation`                                       | `defineInstrumentation`, `isChannel`                                 |
| `eve/evals`                                                 | `defineEval`, `defineEvalConfig`, eval types                         |
| `eve/evals/expect`                                          | `includes`, `equals`, `matches`, `similarity`                        |
| `eve/evals/reporters`                                       | `Braintrust`, `JUnit`, `EvalReporter`                                |
| `eve/evals/loaders`                                         | `loadJson`, `loadYaml`                                               |
| `eve/react`, `eve/vue`, `eve/svelte`                        | `useEveAgent`                                                        |
| `eve/next`, `eve/nuxt`, `eve/sveltekit`                     | framework bundler plugins                                            |
| [`eve/client`](../guides/client/overview)                   | `Client`, `ClientSession`                                            |

Exported types 会从描述它们的 helper 所在同一个 entrypoint 发出（例如 `ToolDefinition` 和 `ToolContext` 来自 `eve/tools`）。完整列表请阅读 `packages/eve/src/public/index.ts`。

## 接下来阅读

- [`agent.ts`](../agent-config)：这些 helpers 配置的 agent config
- [Tools](../tools)：`defineTool`，最常用的 helper
- [Project layout](./project-layout)：每个 define\* 在磁盘上的位置
