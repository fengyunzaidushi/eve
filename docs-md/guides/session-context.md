---
title: "Session Context"
description: "Runtime helpers：ctx.session、ctx.getSandbox、ctx.getSkill 和 defineState。"
---

eve 通过传给 tool `execute`、hook handlers 和 channel event handlers 的 `ctx` 参数暴露 runtime state：

- `ctx.session`：session metadata、turn、auth 和 parent lineage
- `ctx.getSandbox()`：当前 agent 的 live sandbox handle
- `ctx.getSkill(identifier)`：当前 agent 可见的 named skill handle
- `defineState(name, initial)`：带 `get()` 和 `update()` 的 typed durable state（从 `eve/context` 导入）

这些 API 只在 active authored runtime execution 内工作，包括 tools、channel event handlers 和 authored hooks。在 managed context 外调用时会 throw。

## `ctx.session`

`ctx.session` 暴露当前 execution 的 durable runtime metadata。

```ts title="agent/tools/who_called_me.ts"
import { defineTool } from "eve/tools";
import { z } from "zod";

export default defineTool({
  description: "Return the active session metadata.",
  inputSchema: z.object({}),
  async execute(_input, ctx) {
    return {
      sessionId: ctx.session.id,
      turnId: ctx.session.turn.id,
      turnSequence: ctx.session.turn.sequence,
      currentCaller: ctx.session.auth.current?.principalId,
      initiator: ctx.session.auth.initiator?.principalId,
      parentSessionId: ctx.session.parent?.sessionId,
      parentCallId: ctx.session.parent?.callId,
    };
  },
});
```

public session fields：

- `auth.current`
- `auth.initiator`
- `id`
- `turn.id`
- `turn.sequence`
- optional `parent`

行为：

- `auth.current` 是 active inbound turn 的 caller。
- `auth.initiator` 是启动 durable session 的 caller。
- unprotected agents 会把二者都暴露为 `null`。
- top-level schedule sessions 会暴露 framework app principal（`principalId: "eve:app"`、`principalType: "runtime"`）。
- `parent` 会出现在 child subagent sessions 中，并包含 parent `callId`、`sessionId`、`rootSessionId` 和 `turn`。

## `ctx.getSandbox()`

`ctx.getSandbox()` 返回当前 agent sandbox 的 live handle。

```ts
const sandbox = await ctx.getSandbox();
const result = await sandbox.run({ command: "npm test" });
```

行为：

- 它不接受参数。每个 agent 正好有一个 sandbox。
- 它是 async 的，因为 eve 会惰性 bind 或 restore sandbox state。
- 它只在 sandbox access 附着到 active runtime path 时工作。
- visibility 是 node-local。subagent 看到的是自己的 sandbox，而不是 parent 的 sandbox。

`SandboxSession` 还暴露 `resolvePath(path)`，返回 logical `/workspace/...` location 对应的 live backend-native path。当 authored code 在把路径传给 shell code 或 child process 前需要该路径时使用它。

lifecycle details 见 [Sandbox](../sandbox)。

## `ctx.getSkill(identifier)`

`ctx.getSkill(identifier)` 返回当前 agent 可见的 named skill handle。

```ts
const skill = ctx.getSkill("research");
const notes = await skill.file("references/checklist.md").text();
```

行为：

- 它是同步的。File content 会从 active sandbox 惰性读取。
- 它只在 sandbox access 附着到 active runtime path 时工作。
- `identifier` 是 path-derived skill id。
- visibility 跟随当前 agent 的 sandbox。
- missing skill 会在 file accessor 读取 missing sandbox path 时暴露。
- 返回的 handle 暴露 `name` 和 `file(relativePath)`。

完整 authoring model 见 [Skills](../skills)。

## Custom state with `defineState`

当你的 agent 需要 tools、hooks 和 channel handlers 可共享的 durable typed state 时，请使用 `defineState`。State 会跨 workflow step boundaries 保留。请在 module scope 声明 handle，让每个 importer 共享它：

```ts title="agent/lib/budget.ts"
import { defineState } from "eve/context";

interface BudgetState {
  readonly count: number;
  readonly cap: number;
}

export const budget = defineState<BudgetState>("myapp.budget", () => ({
  count: 0,
  cap: 25,
}));
```

`get()` 读取当前值（首次访问时返回 `initial()`），`update(fn)` 对其应用 function。二者在 managed scope 外都会 throw。完整读写模型以及 tools 和 hooks 示例见 [State](./state)。

## 这些 API 在哪里可用

安全位置：

- 在 `defineTool(...).execute(input, ctx)` 内
- 在 eve 于 runtime 内运行的 authored callbacks 中
- 在同一个 authored execution chain 的 asynchronous boundaries 之后

不安全位置：

- top-level module evaluation
- build scripts
- discovery-time code paths

如果在 active eve runtime context 外调用它们，它们会立即 throw，并用 message 说明所需 scope。

## 工作原理

framework 会在调用 authored code 前设置 context container：

1. runtime 填充 durable seed values（auth、session id、compiled bundle）。
2. 每个 step 前，framework 从 durable state 派生 step-local values（session metadata、sandbox access、skill access）。
3. authored code 在 managed scope 内运行，因此 `ctx` 和 `defineState` accessors 会自动 resolve。
4. step 后，framework 会把 mutable state（例如 sandbox changes）commit 回 durable session。

framework 管理这个 lifecycle。authored code 只使用 `ctx` 和 public accessors。

## 接下来阅读

- [State](./state)
- [Sessions, runs & streaming](../concepts/sessions-runs-and-streaming)
- [Subagents](../subagents)
- [Skills](../skills)
