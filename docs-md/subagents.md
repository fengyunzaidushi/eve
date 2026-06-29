---
title: "Subagents"
description: "将工作委派给 child agents，可以是 agent 自身的副本，也可以是拥有自己 sandbox 和 skills 的 declared specialists。"
---

subagent 是一个 child agent，某个 agent 会把 focused subtask 委派给它。把工作拆给 subagent，可以并行运行，也可以给 child 更窄的 tools 集合，或给 specialist 自己的身份。有两类 subagent：built-in `agent` tool（agent 自身的副本）和 declared subagents（拥有自己目录的 specialists）。

## Built-in `agent` tool

每个 agent 默认都有一个 `agent` tool。model 调用它，把 subtask 委派给自身副本：

```ts
{
  message: string;       // everything the child needs; it does not see the parent's history
  outputSchema?: object; // when set, the child runs in task mode and returns structured output
}
```

副本共享 parent 的 sandbox 和 tools，child 写入的文件会立即对 parent 可见。这让 parallel calls 很自然：fan out 几个副本，同时修复不同文件。副本会继承 auth 和 connections，但以 fresh conversation history 和 fresh state 启动。如果 declared subagent 调用 `agent`，child 是 _该_ subagent 的副本，而不是 root 的副本。

parent 通过传给 subagent 的 `message` input 向 child 传递数据。除非该 child 及其继承的 tools、connections、sandbox 和 telemetry path 适合处理这些数据，否则不要在 subagent request 中包含 sensitive data。

位于 `agent/tools/agent.ts` 的 authored tool 优先于 built-in。

## Declared subagents

declared subagent 位于 `agent/subagents/<id>/` 下，并使用与 root 相同的 `defineAgent` helper。它位于 `subagents/` 下这一点，就是标记它为 subagent 的唯一依据。当 child 需要明显不同的 prompt、role 或 tool surface 时，请声明一个。

```ts title="agent/subagents/researcher/agent.ts"
import { defineAgent } from "eve";

export default defineAgent({
  description: "Investigate ambiguous questions before the parent agent responds.",
  model: "anthropic/claude-opus-4.8",
});
```

`description` 必填。parent 会读取它来决定是否委派，因此 compiler 会拒绝任何 `agent.ts` 省略它的 subagent。

最小文件：

```text
agent/subagents/researcher/
├── agent.ts            # required (must export a description)
├── instructions.md     # or instructions.ts, optional
├── tools/              # optional, its own tools
├── skills/             # optional, its own skills
├── sandbox/            # optional, its own sandbox + workspace seed
└── subagents/          # optional, nested subagents
```

declared subagent 内不支持 `schedules/`。Schedules 仅限 root。

## 隔离边界

declared subagent 不会从 root 的 authored slots 继承任何内容。Discovery 会把它的目录视为自己的 agent root，因此它只拥有在 `agent/subagents/<id>/` 下编写的 instructions、tools、connections、skills、sandbox、hooks 和 nested subagents。缺失的 slot 会 fallback 到 framework default，而不是 root 的版本。

| Slot         | Built-in `agent` tool | Declared subagent                         |
| ------------ | --------------------- | ----------------------------------------- |
| Instructions | 继承（agent 的副本）  | 自己的 `instructions.{md,ts}`，可选       |
| Tools        | 继承                  | 自己的 `tools/`                           |
| Connections  | 继承                  | 自己的 `connections/`                     |
| Skills       | 继承                  | 自己的 `skills/`                          |
| Sandbox      | 与 parent 共享        | 自己的 `sandbox/`，否则 framework default |
| Hooks        | 继承                  | 自己的 `hooks/`                           |
| State        | Fresh                 | Fresh                                     |
| Channels     | 仅限 root             | 仅限 root                                 |
| Schedules    | 仅限 root             | 仅限 root                                 |

对于 declared subagent，这意味着需要复制 child 需要的任何内容。当两个 subagents 需要同一个 procedure 时，请把 markdown 复制到每个 `skills/` 目录下，或通过 `lib/` 共享 typed helpers。sandbox 不会从 parent 继承；除非 subagent 编写 `subagents/<id>/sandbox.ts`，或通过 `subagents/<id>/sandbox/workspace/` seed files，否则它会 fallback 到 framework default。

built-in `agent` tool 是例外。它的 children 共享 parent 的 sandbox 和 tools，因为它们是同一个 agent 的副本，处理同一组文件。

无论哪一类，`defineState` 都永远不共享。每个 child 都以 fresh durable state 启动。

## parent 会看到什么

eve 会把每个 subagent（built-in copy、declared 或 [remote](./guides/remote-agents)）lower 为一个 model-visible tool，形状都是 `{ message, outputSchema? }`。由于 child 永远看不到 parent 的 history，parent 会把 child 需要的所有内容打包进 `message`。设置 `outputSchema` 可让 child 以 task mode 运行，并把 structured output 作为 tool result 返回。

declared subagent 的 tool name 是裸 path-derived name，没有 prefix。`agent/subagents/researcher/` 会注册为 tool `researcher`。与 connection tools（`connection__<connection>__<tool>`）不同，它不携带 namespace，因此 model、approvals、logs 和 evals 都用该名称引用它。它的 input schema 是：

```ts
{
  message: string;       // all context the child needs; it never sees the parent's history
  outputSchema?: object; // when set, the child runs in task mode and returns structured output
}
```

由于该名称位于与 authored tools 相同的 runtime tool namespace 中，名为 `researcher` 的 subagent 会与名为 `researcher` 的 tool 冲突。eve 会拒绝 build，而不是选择一方，因此请保持 subagent directory names 与 tool names 不同。

不要把 subagent delegation 本身当作 approval boundary。只要 sensitive tools 可能被调用，就应把它们放在 `needsApproval`、connection approval、route/session authorization 或其他 controls 后面。

每个 delegated subagent 都会启动自己的 child session 和 stream。parent stream 只携带 control-plane events `subagent.called` 和 `subagent.completed`。若要跟踪 child 的完整进度，请读取 `subagent.called.data.childSessionId`，并订阅 `GET /eve/v1/session/:childSessionId/stream`。

## 何时拆分

当 task 需要不同 prompt 或 specialist role、更窄的 tool surface，或自己的 runtime context 时，请拆出 subagent。当 [skill](./skills) 足够时，不要使用 subagent。如果 agent 可以保持自己的身份，并且只需要 optional procedure，skill 是更轻量的选择。

## 接下来阅读

- [Remote agents](./guides/remote-agents)：把另一个 eve deployment 作为 subagent 调用。
- [Dynamic workflows](./guides/dynamic-workflows)：让 model 以编程方式编排它的 subagents（fan-out、map-reduce）。
