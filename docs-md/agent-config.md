---
title: "agent.ts"
description: "在 agent.ts 中使用 defineAgent 设置 agent 的 runtime config，包括 model 和 compaction。"
---

agent 的 `agent.ts` 会调用来自 `eve` 的 `defineAgent` 来设置 runtime config。

## 设置 model

典型配置会选择一个 model：

```ts title="agent/agent.ts"
import { defineAgent } from "eve";

export default defineAgent({
  model: "anthropic/claude-opus-4.8",
});
```

如果不需要 runtime config，可以省略根目录下的 `agent.ts`。在这种情况下，eve 默认使用
`anthropic/claude-sonnet-4.6`。如果存在 `agent.ts`，则必须提供 `model`。

`model` 接受 gateway model id 字符串，并通过 [Vercel AI Gateway](https://vercel.com/docs/ai-gateway) 路由。若要直接调用 provider 并在代码中配置 model，请传入 provider 提供的 `LanguageModel`。

特定 provider 的 AI SDK packages 是普通项目依赖。全新的 `eve init` app 会包含核心 `ai` package，但不会安装每个 provider package。安装你导入的 provider package，然后设置该 provider 的 API key：

```bash
npm install @ai-sdk/anthropic
```

```ts title="agent/agent.ts"
import { anthropic } from "@ai-sdk/anthropic";
import { defineAgent } from "eve";

export default defineAgent({
  model: anthropic("claude-opus-4.8"),
});
```

model 的使用受所选 provider 和路由路径的条款、数据处理承诺、保留行为以及可用控制项约束。对于通过 gateway 路由的 models，请查看 [AI Gateway model catalog](https://vercel.com/ai-gateway/models)；配置直接 `LanguageModel` 时，请查看该 provider 的条款。

## Compaction

当接近 context window 时，compaction 会汇总较早的 turns。它默认开启，因此你通常只需要调整触发时机。降低 `thresholdPercent` 可以更早 compact：

```ts title="agent/agent.ts"
export default defineAgent({
  model: "anthropic/claude-opus-4.8",
  compaction: {
    thresholdPercent: 0.75, // default 0.9
  },
});
```

loop 如何应用它，见 [Default harness](./concepts/default-harness#compaction)。

## Other defineAgent fields

`defineAgent` 还接受几个字段，它们都是可选的。导出的类型见 [TypeScript API](./reference/typescript-api)。

| Field          | Type                                    | Default     | Description                                                                                                                                                                                                          |
| -------------- | --------------------------------------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `modelOptions` | `AgentModelOptionsDefinition`           | none        | 转发给 model call 的 provider option overrides。                                                                                                                                                                     |
| `experimental` | `{ codeMode?: boolean }`                | flags unset | 选择启用的 flags，可能在任何 release 中变化或消失。请将它们视为不稳定。`codeMode` 会通过 sandboxed code-execution wrapper 路由 executable tools，model 会写入 JavaScript，在 [sandbox](./sandbox) 中调用这些 tools。 |
| `outputSchema` | Standard Schema or a JSON Schema object | none        | task-mode runs（subagent、schedule 或 remote job）的结构化返回类型。除非 client 提供 per-message schema，否则 interactive conversation turns 会忽略它。                                                              |
| `build`        | `{ externalDependencies?: string[] }`   | none        | hosted-build packaging controls。`externalDependencies` 会在 eve 编译 tools 和 channels 等 authored modules 时让列出的 packages 保持 external，并把这些 packages trace 到 hosted output 中。                         |

`codeMode` 是 experimental 的，可能变化或被移除。

`externalDependencies` 只是 packaging control。它会让选定 packages 作为 runtime dependencies 保留在 hosted output 中；它不会授权、配置或审查这些 packages 可能调用的任何第三方服务。

## 相邻设置的位置

| Concern                       | Lives in                                                                     |
| ----------------------------- | ---------------------------------------------------------------------------- |
| Instructions prompt           | `agent/instructions.md`，[Instructions](./instructions)                      |
| Per-tool approval (HITL)      | `agent/tools/*.ts`，[Tools](./tools)                                         |
| Inbound auth & network policy | channel layer，[Auth & route protection](./guides/auth-and-route-protection) |
| Sandbox / workspace           | `agent/sandbox/`，[Sandbox](./sandbox)                                       |
| Telemetry & debugging         | `agent/instrumentation.ts`，[Instrumentation](./guides/instrumentation)      |

## 接下来阅读

- [Default harness](./concepts/default-harness)：了解此配置驱动的 loop 和 built-in tools
- [TypeScript API](./reference/typescript-api)：查看每个 `defineAgent` 字段和类型
- [Subagents](./subagents)：了解 `description` 要求和 child-agent config
