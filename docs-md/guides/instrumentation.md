---
title: "instrumentation.ts"
description: "在 instrumentation.ts 中用 OpenTelemetry trace agent，读取 eve 发出的 workflow run tags，并用 eve info 和常见失败表调试 discovery。"
---

`instrumentation.ts` 用来配置如何观测 eve agent。framework 会自动发现 `agent/instrumentation.ts`，并在 server startup 时、任何 agent code 运行前执行它。只要这个文件存在，就会隐式启用 telemetry，因此没有单独的 `isEnabled` 开关。

如果你打算导出 telemetry，请在启用前审查 exporter destination、数据类别和所需的法律审批。

## 三个 observability surfaces

eve 通过三个彼此独立的 surface 观测 agent。它们并不都在这个文件里配置，也会写入不同位置：

| Surface                          | 在 `instrumentation.ts` 中配置？                           | 作用                                                                                                                                               |
| -------------------------------- | ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Workflow run tags** (`$eve.*`) | 否（自动）                                                 | 每个 Vercel Workflow run 上由 framework 拥有的 attributes。让 dashboards 能把 session、turn 和 subagent runs 拼成树，并展示 model 和 token usage。 |
| **OpenTelemetry export**         | 是：`setup`、`recordInputs`、`recordOutputs`、`functionId` | AI SDK spans 导出到哪里，以及记录什么内容。                                                                                                        |
| **Runtime context events**       | 是：`events["step.started"]`                               | 写入 AI SDK runtime context 的 per-model-call values，AI SDK 会把它们带到 spans 上。                                                               |

两个可配置 surface 会把 AI SDK spans 发送到你的 OpenTelemetry backend。Workflow run tags 是另一套系统，可在 Workflow dashboard 中查询，而不是出现在 OTel spans 上。下面几节说明你在这里配置的内容；[Workflow run tags](#workflow-run-tags) 说明 eve 自行发出的内容。

## 定义 instrumentation

```ts title="agent/instrumentation.ts"
import { BraintrustExporter } from "@braintrust/otel";
import { defineInstrumentation } from "eve/instrumentation";
import { registerOTel } from "@vercel/otel";

export default defineInstrumentation({
  setup: ({ agentName }) =>
    registerOTel({
      serviceName: agentName,
      traceExporter: new BraintrustExporter({
        parent: `project_name:${agentName}`,
        filterAISpans: true,
      }),
    }),
});
```

将 `defineInstrumentation` 的结果作为 default export 导出。

## OpenTelemetry

使用 `setup` callback 注册你的 OTel provider（例如来自 `@vercel/otel` 的 `registerOTel`）。framework 会在 server startup 时调用它，并传入解析后的 agent name。`context.agentName` 会在 compile time 从你的项目解析出来（优先用 package 的 `name`，否则回退到 app directory name），所以你不用硬编码 service name。

任何兼容 OTel 的 backend 都可以使用（Braintrust、Honeycomb、Datadog、Jaeger）。安装你需要的 exporter package，并在 callback 中配置它。

还有三个字段控制 AI SDK 在这些 spans 中记录什么（见 AI SDK 的 [telemetry reference](https://ai-sdk.dev/docs/ai-sdk-core/telemetry)）：

- `recordInputs` 会在每个 step span 上记录完整 message history（默认 `true`）。如果 inputs 包含敏感内容，或你想减少 span payload size，请设为 `false`。
- `recordOutputs` 会在 spans 上记录 model outputs（默认 `true`）。设为 `false` 可禁用 output recording。
- `functionId` 覆盖 spans 上的 function name（默认是 agent name）。

对于敏感、受监管或生产数据，除非你已经审查 exporter 及其 data-retention path，否则请将 `recordInputs` 和 `recordOutputs` 设为 `false`。

你负责确保任何 observability 或 eval provider 都已获准接收导出的数据。

第三个可配置 surface [runtime context events](#runtime-context) 会把 per-model-call values 附加到这些 spans 上。

## Runtime context

_Runtime context_ 是一个 [AI SDK 概念](https://ai-sdk.dev/docs/reference/ai-sdk-core/stream-text)：它是贯穿 generation lifecycle 的用户定义对象。eve 通过 `events["step.started"]` 暴露它；这个 callback 会在 eve 组装好某次 attempt 的 model input 后运行，并返回 `{ runtimeContext }`。由于 eve 注册 AI SDK 的 OpenTelemetry integration 时启用了 runtime context，这些返回值会被带到 model-call span 及其子 span 上。字段名是 `runtimeContext`，不是 `metadata`，因为 AI SDK v7 会把 per-call attributes 放在 runtime context 上，而不是专用 metadata 字段。

当值依赖当前 session、turn、step、channel 或 model input 时使用它：

```ts
import { defineInstrumentation, isChannel } from "eve/instrumentation";
import supportChannel from "./channels/support.js";

export default defineInstrumentation({
  events: {
    "step.started"(input) {
      if (!isChannel(input.channel, supportChannel)) {
        return undefined;
      }

      return {
        runtimeContext: {
          "support.channel_id": input.channel.metadata.channelId ?? "",
          "support.user_id": input.channel.metadata.triggeringUserId ?? "",
        },
      };
    },
  },
});
```

callback 会接收：

- `session`：session id、current 和 initiator auth，以及这是 child run 时的 parent session lineage
- `turn`：stream turn id 和 sequence，例如 `turn_0`
- `step`：turn 内从零开始的 step index
- `channel`：channel 的 `kind`，以及 active channel 投影出的 metadata
- `modelInput`：传给 model call 的最终 instructions 和 messages

channel 通过 `kind` 暴露自己的 identity，你可以用它作为 discriminant 来 narrow。对于 authored channels，它是 `channel:<name>`，其中 `<name>` 来自 `agent/channels/` 下的 channel 文件名，所以 `agent/channels/support.ts` 是 `channel:support`。Framework channels 使用 `http`、`schedule` 或 `subagent`，未识别或缺失的 kind 会规范化为 `unknown`。这个 kind 也会作为 `eve.channel.kind` span attribute 发出。eve 会发出按 channel 文件名索引的 compiler-owned typings，所以你既可以检查 `input.channel.kind === "channel:support"`，也可以使用 `isChannel(input.channel, supportChannel)` 来 narrow。

Channel metadata 由 channel 自己拥有。内置 channels 只暴露它们选择用于观测的字段；例如 Slack 会从 durable channel state 投影 `channelId`、`teamId`、`threadTs` 和 `triggeringUserId`。用户编写的 channels 通过从 `defineChannel` 返回 `metadata(state)` 暴露自己的投影。Runtime instrumentation 永远不会回退读取 raw channel state。

## Trace hierarchy

启用 telemetry 后，每个 turn 会产生类似这样的 trace：

```text
ai.eve.turn  {eve.session.id}
  +-- ai.streamText                           step 1
  |     +-- ai.streamText.doStream            model call
  |     +-- ai.toolCall  {toolName: search}   tool exec
  +-- ai.streamText                           step 2
  |     +-- ai.streamText.doStream
  |     +-- ai.toolCall  {toolName: read}
  +-- ai.streamText                           step 3 (final text)
```

eve 为每个 turn 创建 `ai.eve.turn` parent span，并把增强过的 telemetry 传给 AI SDK，这样 model calls 和 tool executions 会自动被 trace。Session、turn、step 和 channel context 会作为 runtime context 的 framework 部分注入（`eve.version`、`eve.session.id`、`eve.environment`、`eve.turn.id`、`eve.turn.sequence`、`eve.step.index`、`eve.channel.kind`），并和你的 `events["step.started"]` callback 在 `runtimeContext` 下返回的值一起带到 spans 上。

## Workflow run tags

与 OpenTelemetry 分开，eve 会用保留的 `$eve.*` attributes 标记每个 workflow run。它们存在于 Vercel Workflow run 上，可在 Workflow dashboard 中查询，不在 OTel spans 上，而且你不需要配置：它们由 framework 拥有，并会在每个 session、turn 和 subagent run 上自动发出，无论是否存在 `instrumentation.ts` 文件。Authored code 不能设置或覆盖 `$eve.` namespace。

这些 tags 让 dashboard 能重建单个 agent invocation 背后的 run tree，并在不读取 run bodies 的情况下展示 model 和 token usage。

Structural tags 描述每个 run 在树中的位置：

- `$eve.type`：`"session"`、`"turn"` 或 `"subagent"`
- `$eve.parent`：直接 parent 的 session id
- `$eve.root`：链中 root session 的 session id（用 `$eve.root=<id>` 聚合整棵树）
- `$eve.subagent`：compiled graph node id（仅 subagent runs）
- `$eve.trigger`：启动 run 的 channel kind
- `$eve.title`：由第一条 user message 派生的截断 title

Per-turn usage tags 会写在 turn 的每个 step 上，并累加累计总量（最后一次写入生效）：

- `$eve.model`：turn 使用的 model id
- `$eve.input_tokens`、`$eve.output_tokens`、`$eve.cache_read_tokens`：运行中的 token counts
- `$eve.tool_count`：turn 可用的 tools 数量

Tag 写入是 best-effort：失败会在每个进程中记录一次，然后被吞掉，因此 broken tag emit 不会让 agent 失败。

这些 tags 支撑 Vercel dashboard 中的 **Agent Runs** tab。当你部署到 Vercel 时，platform 会自动检测 `eve` framework，并在项目 **Observability** tab 下展示 Agent Runs view；你可以浏览 sessions，并深入查看每段 conversation 的 trace，不需要 `instrumentation.ts`。该 tab 目前按 team gated。启用方式见 [Deployment](./deployment#view-runs-in-the-dashboard)。Agent Runs 独立于上面的 OpenTelemetry export。如果你希望 spans 进入 Braintrust、Datadog 或其他第三方 backend，请使用 OTel。

注意：telemetry 默认会记录完整 message history 和 model outputs。如果使用它，你可能需要在隐私材料中披露这些 data flows。

## Debugging

`eve info` 是查看 eve 实际发现了什么的最快方式：active tools、skills、subagents、schedules、routes 和 discovery diagnostics。eve 也会在 `.eve/` 下写入可检查 artifacts，即使 discovery 遇到 errors 也会保留：

| Artifact                        | 告诉你什么                               |
| ------------------------------- | ---------------------------------------- |
| `agent-discovery-manifest.json` | eve 在磁盘上发现了什么                   |
| `diagnostics.json`              | authored-shape errors 和 warnings        |
| `compiled-agent-manifest.json`  | eve 在 runtime 加载的 serialized surface |
| `module-map.mjs`                | eve 导入的 compiled module entrypoints   |

当 `eve build` 因 discovery errors 失败时，CLI 会打印完整 diagnostics report（severity、message、source path）和 diagnostics artifact 的路径。

### Common failures

| Symptom                               | Likely cause and fix                                                                                                                                                                                                                                    |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Tool not discovered（model 看不到它） | 运行 `eve info`。确认文件在正确 slot（`agent/tools/<name>.ts`）中，并 default-export `defineTool(...)`；同时检查 `.eve/diagnostics.json` 是否有 shape errors。`schedules/` 仅支持 root。                                                                |
| Model won't call a tool it should     | 收紧 tool `description` 和 `inputSchema`；把流程性指导放进 [skill](../skills)，不要放在 description 中。用 `eve info` 确认它在 active set 中。                                                                                                          |
| Stuck on `session.waiting`            | turn 正停在 approval、question 或 connection sign-in 上。回答它，或用 `continuationToken` POST 一个 follow-up（stale token 会被拒绝）。                                                                                                                 |
| 401 on production routes              | 这是预期行为：auth fails closed。用你的 route policy 替换 `placeholderAuth()`。`vercelOidc()` 只适用于 Vercel-issued tokens；否则配置 `httpBasic()`、JWT/OIDC helpers 或 custom `AuthFn`。见 [Auth and route protection](./auth-and-route-protection)。 |
| Build fails with discovery errors     | 阅读打印出的 diagnostics 和 `.eve/diagnostics.json`；确认 root-vs-subagent boundary 有效，并且 secrets 来自 env vars。                                                                                                                                  |

## 接下来阅读

- [`agent.ts`](../agent-config)
- [Hooks](./hooks)：观察 runtime event stream
- [Local Development](./dev-tui)：本地驱动 agent
- [Evals](../evals/overview)：可重复的 scored checks
