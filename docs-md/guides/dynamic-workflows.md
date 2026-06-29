---
title: "Dynamic Workflows"
description: "experimental Workflow tool：让 model 通过 model-authored JavaScript 将自己的 subagents 编排为一个 durable step。"
---

experimental `Workflow` tool 允许 model 编写 JavaScript，把 agent 自己的 subagents 协调为单个 durable step。program 可以按顺序运行它们、把一个结果喂给下一个、对列表 fan out，并组合 results。你启用 capability，model 决定并运行 orchestration。它是 [code mode](../agent-config#other-defineagent-fields) 中仅面向 agents 的部分（更广泛的 `codeMode` flag 会把 agent 的所有 tools 都通过 model-authored JavaScript 路由）。

单个 turn 已经可以调用多个 subagents，parallel tool calls 也会并发 dispatch。workflow 增加的是 _programmatic_ coordination。program 会根据早先结果决定运行多少 subagents、哪个 output 喂给哪个 call，以及如何组合全部结果。这类逻辑不是 model 通过几个 one-off calls 就能表达的。

## 启用 Workflow tool

把 opt-in marker 作为 `agent/tools/workflow.ts` 的 default export 重新导出。marker name 带有 “experimental” warning，但 model 实际看到的 tool 名为 `Workflow`。

```ts title="agent/tools/workflow.ts"
export { ExperimentalWorkflow as default } from "eve/tools";
```

没有该文件时，`Workflow` tool 保持关闭。只有当 agent 有值得协调的 subagents（或 built-in `agent`）时，它才有价值：

```ts title="agent/subagents/analyst/agent.ts"
import { defineAgent } from "eve";

export default defineAgent({
  description: "Analyzes one metric: queries, computes, writes a short finding.",
  model: "anthropic/claude-opus-4.8",
});
```

当被要求生成 weekly business review 时，model 会选择 metrics，为每个 metric 并行运行一个 `analyst`，并组合 findings。下面的 program 是 model 会编写的 JavaScript 类型。它会把 `analyst` fan out 到 runtime-decided metrics 列表，并合并 results：

```js
const metrics = ["revenue", "signups", "churn"];
const findings = await Promise.all(
  metrics.map((metric) => tools.analyst({ message: `Summarize last week's ${metric}.` })),
);
return findings.join("\n\n");
```

每个 `tools.analyst(...)` call 都会 dispatch 一个 child subagent，因此 parent stream 会为每个 metric 记录一个 `subagent.called`，并在每个完成时记录一个 `subagent.completed`：

```json
{ "type": "subagent.called", "data": { "name": "analyst", "toolName": "analyst", "callId": "call_1", "childSessionId": "ses_a1", "sequence": 0 } }
{ "type": "subagent.called", "data": { "name": "analyst", "toolName": "analyst", "callId": "call_2", "childSessionId": "ses_a2", "sequence": 1 } }
{ "type": "subagent.called", "data": { "name": "analyst", "toolName": "analyst", "callId": "call_3", "childSessionId": "ses_a3", "sequence": 2 } }
{ "type": "subagent.completed", "data": { "subagentName": "analyst", "callId": "call_1", "output": "..." } }
{ "type": "subagent.completed", "data": { "subagentName": "analyst", "callId": "call_2", "output": "..." } }
{ "type": "subagent.completed", "data": { "subagentName": "analyst", "callId": "call_3", "output": "..." } }
```

## workflow 可以编排什么

workflow 只能访问此 agent 自己的 agents：built-in `agent`（自身副本）、declared [subagents](../subagents) 和 [remote agents](./remote-agents)。这就是完整列表。没有 files、network、shell、skills 或 connections。workflow 是 subagents 之上的 coordination layer，不是执行其他工作的地方。每个 call 仍可通过 `outputSchema` 请求 structured output，就像 direct subagent delegation 一样。

## JavaScript 在哪里运行

orchestration code 永远不会触碰 agent process。runtime 会把 program text 交给一个小型 isolated JavaScript engine（QuickJS sandbox）并在那里运行。host realm 中没有任何东西会跨进去，因此没有 `process`，没有来自 agent 的 `globalThis`，也没有 `import`/`require`。program 只能访问两类东西：以 `tools.<name>` bridge 进来的 agent functions，以及普通语言 built-ins。

这是 allowlist，不是 denylist。sandbox 不能读 files、打开 socket 或看到 environment variable，是因为这些东西不存在，而不是因为逐项阻止。program 调用 agent function 时，该 call 会 bridge 回 runtime，runtime 会像 direct delegation 一样 dispatch 它。orchestration glue 保留在 sandbox 内。

## Durability、approvals 和 observability

- **Durable.** 整个 orchestration 算作一个 step。一起 dispatch 的 subagents 会并发运行；如果 run 在 long-running 或 human-gated child 上 park（durably suspend 且不占用 compute；见 [Execution model & durability](../concepts/execution-model-and-durability)），restart 后会从离开处恢复。
- **Approval-safe.** mid-run 需要 human approval（HITL，human-in-the-loop）的 subagent 会把 request 暴露给用户，用户回答后 workflow 会继续，和 direct delegation 相同。
- **Observable.** 每个 orchestrated subagent 都会在 parent stream 上发出通常的 `subagent.called` / `subagent.completed` events，并获得自己的 child session 和 stream。telemetry 与 direct delegation 匹配，因此现有 dashboards 和 cost attribution 会继续工作。

## 与 code mode 的关系

[Code mode](../agent-config#other-defineagent-fields) 是更广泛的版本，model 会从 JavaScript 驱动 agent 的 _所有_ tools（files、shell、web 和 agents）。workflow 只覆盖 subagents。二者互不干扰。启用 `Workflow` tool 不会影响 code mode，一个 agent 可以同时运行二者。

`codeMode` 是 experimental 的，可能变化或被移除。

## 接下来阅读

- 声明 workflow 要编排的 subagents → [Subagents](../subagents)
- 把另一个 deployment 作为其中一个 agent 调用 → [Remote agents](./remote-agents)
- `agent/tools/` opt-in mechanism → [Default harness](../concepts/default-harness)
