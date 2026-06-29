---
title: "执行模型与 Durability"
description: "eve session 如何运行。Durable conversations、在 steps checkpoint 的 turns，以及稍后恢复的 parked work。"
---

eve session 是 durable conversation。它可以运行数天，并在 process restart 和 redeploy 后继续存在，而不需要你做任何额外工作。你编写 capabilities（tools、instructions、channels），eve 运行 loop。

## Sessions、turns 和 steps

工作按三层嵌套：

- **session**：完整的 durable conversation 或 task。它是 long-lived 的，可以跨越数天或数周的多个 requests，而不会丢失 context。
- **turn**：一条 user message 以及它触发的全部工作（model calls、tool calls、reasoning），直到 agent 产出 response。
- **step**：turn 内的 durable checkpoint（一次 model call 以及它发起的 tool calls）。

每个 turn 都作为 durable workflow 运行，基于开源 [Workflow SDK](https://workflow-sdk.dev/)（部署到 Vercel 时为 Vercel Workflow）构建。eve 会在每个 step boundary checkpoint 进度并序列化 durable state。你的代码运行在 managed step 内，因此即使底层 session 是 durable 的，tools、sandbox 和 subagents 使用起来也像同步调用。

Workflow SDK 本身并不绑定 Vercel。在 local development 和 self-deployed `eve start` process 中，eve 默认使用 SDK 的 local world；该 world 会把 workflow runs 持久化到磁盘，通常位于 `.workflow-data` 下，并通过同一套 Nitro-hosted workflow routes dispatch。在 Vercel 上，同样的 workflow code 则运行于 Vercel Workflow，从而获得 latest production deployment routing 和 dashboard run metadata 等平台能力。

Nitro 负责托管 HTTP routes 和 workflow entrypoints。它不提供 workflow state store 或 sandbox runtime。这些是独立 adapters：Workflow 使用 active world implementation，Sandbox 使用来自 `agent/sandbox` 或 `defaultBackend()` 的 backend。

目前，eve 负责 Workflow world selection。未来，eve 会暴露受支持的方式来提供不同的 Workflow world，让高级 self-hosted deployments 可以在同一个 agent runtime 后面替换 state、queue、auth 和 streaming backend。底层 [Workflow Worlds](https://workflow-sdk.dev/worlds) 抽象让这成为可能，但它还不是 eve application API。

## Crash 后恢复

如果 process crash、遇到 timeout，或在 mid-turn redeploy，run 会从最后完成的 step 继续，而不是 replay 整个 turn。已完成的 steps 永远不会重新运行；eve 会 replay 已记录的结果。执行中断的 step 会重新运行，因此请让扣款或发送邮件等非幂等 side effects 变成幂等，或用 approval gate 住它们。

无需配置。eve 负责 workflow lifecycle，sessions 默认 durable。

你不需要直接编写 workflow code。Workflow primitives（`start()`、`resumeHook()` 等）是 eve runtime layer 的实现细节；channels、tools 和 hooks 永远不会接触它们。有两个 surface 会向你的代码提供 session data：tools 通过 `ctx.session` 读取当前 session 的 metadata（id、turn、auth、parent lineage），[`defineState`](../guides/state) 读取或写入 session-scoped durable state。读写模型见 [State](../guides/state)。

## Parked work

有些工作必须等待，包括人员批准 [tool](../tools)、为 [connection](../connections) 执行 interactive OAuth sign-in，或等待 long-running [subagent](../subagents)。在这些点上，turn 会 durable 地 park。workflow 会 suspend，并且在等待的 input 到达之前不占用 compute（一次点击、一个 callback、一个 child 完成），即使那已经是很久之后。input 到达后，conversation 会从离开的位置精确继续。

## Message delivery and queueing

eve 不会为 session 维护 durable FIFO queue 来保存 user messages。`continuationToken` 是 session 当前 workflow hook 的 resume handle，而不是通用 message-queue address。

当 session 正在 waiting 时，投递到当前 continuation token 的内容会唤醒 session 并启动下一个 turn。当某个 turn 已经 active 时，hook 可能接受额外 deliveries，但 runtime 只会在特定 workflow boundaries drain 它们。如果 driver 检查时有多个 delivery 已就绪，eve 可能会把它们 fold 到下一个 turn 中；这个 drain 是 best-effort 的，取决于 workflow 和 transport timing。

因此，不要依赖对同一个 session 的 concurrent sends 表现得像典型 ordered chat queue。若要获得确定性行为，请一次发送一个 user turn，并等待 `session.waiting` 后再向同一 session 发送下一条 message。如果你的 channel 可能在 agent 工作时收到 bursts，请在 channel 或 app layer 中维护自己的 per-session queue，然后在 session 再次 park 后投递下一条 message。不同 sessions 仍会独立运行。

## Subagents

turn 可以把工作交给 [subagent](../subagents)。每个 subagent 都有自己的 context 和 durable session；declared subagent 还会有自己的 sandbox、skills 和 state。没有任何东西会隐式跨越边界。

## eve 如何排列 session history

session 内的 conversation history 是 append-only 的。Turns 会按顺序落地，turn 内的 tool calls（以及它们的 results）也会保持顺序。回读 session 时，你会按发生顺序看到 events。

## 接下来阅读

- [Sessions and streaming](./sessions-runs-and-streaming)：你持有的 handles 和观察的 event stream。
- [Security model](./security-model)：runtime 强制执行的 trust boundaries。
- [State](../guides/state)：跨 step boundaries 保留的 durable per-session memory。
