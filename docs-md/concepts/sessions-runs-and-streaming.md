---
title: "Sessions、Runs 与 Streaming"
description: "你会接触到的 session 和 run contract：continuation tokens、stream handles、NDJSON event stream 以及重连。"
---

每个 eve app 都通过同一套稳定 HTTP API 与 [durable session](./execution-model-and-durability) 通信。本页说明你需要掌握的 contract：返回给你的 handles、你要 stream 的 events，以及如何重连。

## 两个 handles

两个 handles 各司其职，混淆它们是最常见的错误。一个 handle 用于创建和恢复 session；另一个 handle 用于 stream 和 inspect 它。

- **`continuationToken`**：resume handle。用它向同一个 conversation 发送 follow-up message。由 channel 拥有。
- **`sessionId` / `runId`**：stream-and-inspect handle。用它连接到 event stream 并观察 run。由 runtime 拥有。

session 同一时间只有一个 active continuation：每个 follow-up 都使用当前 `continuationToken`，stale token 会被拒绝。

React、Vue 和 Svelte apps 应使用 [`useEveAgent()`](../guides/frontend/overview)，而不是手动调用这些 routes。Next.js 和 Nuxt apps 可以从同一 origin 把它们 proxy 到 eve runtime。

## 启动 session

```bash
curl -X POST http://127.0.0.1:3000/eve/v1/session \
  -H 'content-type: application/json' \
  -d '{"message":"Summarize the latest forecast."}'
```

eve 会立即响应。JSON body 携带 `sessionId` 和 `continuationToken`，`x-eve-session-id` header 命名要 stream 的 durable session。

## Stream session

```bash
curl http://127.0.0.1:3000/eve/v1/session/<sessionId>/stream
```

stream 是 newline-delimited JSON（NDJSON），每行一个 event：

| Event                     | Meaning                                                                                                        |
| ------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `session.started`         | 已创建 durable session。                                                                                       |
| `turn.started`            | 新 turn 已开始。                                                                                               |
| `message.received`        | inbound user message 已被接受。                                                                                |
| `step.started`            | model step 已开始。                                                                                            |
| `actions.requested`       | model 请求 tool calls。                                                                                        |
| `action.result`           | tool call 已返回。                                                                                             |
| `input.requested`         | run 暂停以等待 human input（[HITL](../tools/human-in-the-loop) approval 或 `ask_question`）；携带 `requests`。 |
| `subagent.called`         | 已委派 subagent；携带可用于连接的 `childSessionId`。                                                           |
| `subagent.completed`      | delegated subagent 已完成。                                                                                    |
| `reasoning.appended`      | reasoning delta（增量，带有截至目前的累计文本）。                                                              |
| `reasoning.completed`     | finalized reasoning block。                                                                                    |
| `message.appended`        | assistant text delta（增量，带有截至目前的累计文本）。                                                         |
| `message.completed`       | finalized assistant text block。                                                                               |
| `result.completed`        | 请求了 output schema 的 turn 的 finalized structured result；携带 `result`。                                   |
| `compaction.requested`    | context-window compaction 已开始；携带 `modelId`、`sessionId`、`turnId`、`usageInputTokens`。                  |
| `compaction.completed`    | compaction checkpoint 已写入 durable history。                                                                 |
| `authorization.required`  | connection 需要 OAuth；携带 `name`、`description` 和 `authorization` challenge。                               |
| `authorization.completed` | connection 的 authorization 已解析；携带 `outcome`。                                                           |
| `step.completed`          | model step 已完成；携带 `finishReason` 和 usage。                                                              |
| `step.failed`             | model step 已失败；携带 `{ code, message, details? }`。                                                        |
| `turn.completed`          | turn 已完成。                                                                                                  |
| `turn.failed`             | turn 已失败；携带 `{ code, message, details? }`。                                                              |
| `session.waiting`         | session 已 park，正在等待下一次 input（message 或 answer）。                                                   |
| `session.failed`          | session 已失败。                                                                                               |
| `session.completed`       | session 已到达 terminal end。                                                                                  |

`reasoning.appended` 和 `message.appended` 会在 deltas 到达时 stream 它们，并且每个 event 都同时携带新 delta 和当前 block 的累计文本。finalized block 会出现在 `message.completed` 和 `reasoning.completed` 上，这是不渲染 incremental streaming 的 clients 的兼容路径。

注意：在你的 application 中显示、存储或传输 reasoning events 时，请考虑 privacy、confidentiality 和 user-experience 影响。

`message.completed` 可以在一个 turn 中触发多次：agent 通常会在 tool call 前发出 interim assistant text。若要区分 tool-call narration 和 terminal reply，请检查 `message.completed.data.finishReason`。`step.completed.data.finishReason` 会镜像 step outcome，usage 位于 `step.completed` 上。

delegated subagent 会在自己的 child-session stream 上发布进度。parent 只会发出带有 `childSessionId` 的 `subagent.called`，client 可用它连接。

`step.failed` 和 `turn.failed` 会为失败的 fragment 或 turn 携带 `{ code, message, details? }`，`session.failed` 是 terminal session-level variant。当 turn 请求了 output schema 时，finalized payload 会在 turn boundary 前以 `data.result` 落到 `result.completed` 上。`authorization.required` 携带 sign-in challenge（`data.authorization` 可能包含 `url`、`userCode`、`expiresAt`、`instructions`），`authorization.completed` 携带 `data.outcome`（`"authorized" | "declined" | "failed" | "timed-out"`）。

## 发送 follow-up message

session 进入 waiting 后（你会看到 `session.waiting`），使用保存的 continuation token 将 follow-up POST 到 session endpoint：

```bash
curl -X POST http://127.0.0.1:3000/eve/v1/session/<sessionId> \
  -H 'content-type: application/json' \
  -d '{"continuationToken":"<token>","message":"Now send the short version."}'
```

follow-up 会复用同一个 durable session：同样的 history，同样的 state。

若要获得确定性顺序，请一次发送一个 follow-up，并等待下一个 `session.waiting` event 后再向同一 session 发送另一条 message。当前 runtime contract 见 [message delivery and queueing](./execution-model-and-durability#message-delivery-and-queueing)。

## 重连和 rewind

stream 是 durable 的。每个 event 都会在 step 完成前被记录，因此整个 stream 都可以 replay。传入 `startIndex` 可以按 event count 重连，并从断开的地方继续，也可以 rewind 到开头：

```bash
curl "http://127.0.0.1:3000/eve/v1/session/<sessionId>/stream?startIndex=<count>"
```

## 从 TypeScript 使用 client

对于 scripts、server-to-server calls、tests、evals 和 custom UIs，`eve/client` 会把这些 routes 包装成 typed client，这样你不必手写 POST 和 NDJSON stream loop。

请从 [TypeScript SDK](../guides/client/overview) guide 开始。它覆盖 basic usage、sending messages、continuations、streaming 和 per-turn `outputSchema` results。

## 通过 HTTP inspect agent

`GET /eve/v1/info` 会为正在运行的 agent 返回 JSON inspection snapshot：model、instructions、authored 和 framework tools、skills、channels、schedules、subagents、sandbox、connections、hooks、workflow 和 workspace metadata。Local development 接受 loopback requests；已部署的 Vercel targets 要求该 route 使用 OIDC auth。

```bash
curl http://127.0.0.1:3000/eve/v1/info
```

该 route 使用与 eve channel 相同的 default auth chain（`[localDev(), vercelOidc()]`）。本地会匿名响应；已部署的 Vercel target 需要有效的 OIDC bearer，并为 in-deployment callers 提供 same-project bypass。见 [auth & route protection](../guides/auth-and-route-protection)。

## Dispatch 顺序

每个 stream event 都按以下顺序运行四个 steps：

1. **Channel handler**：channel 的 event handler 运行，并可以 mutate adapter state。
2. **Metadata projection**：framework 重新求值 channel 的 `metadata(state)` 并存储结果。
3. **Hooks**：订阅该 event 的 authored [hooks](../guides/hooks) 触发。
4. **Dynamic resolvers**：[dynamic](../guides/dynamic-capabilities) tool、skill 和 instruction resolvers 触发，此时 `ctx.channel.metadata` 已经持有第 2 步刚投影出的 metadata。

这个顺序是结构性的，不是偶然的。当 resolver 或 hook 读取 channel metadata 时，channel 已经更新了自己的 state，projection 也是最新的。

## 接下来阅读

- [Execution model & durability](./execution-model-and-durability)：是什么让 session durable，以及 parked work 如何恢复。
- [Channels](../channels/overview)：什么拥有 continuation token 和 delivery。
- [TypeScript SDK](../guides/client/overview)：从 scripts 和 server-side code 调用这些 routes。
- [Frontend](../guides/frontend/overview)：使用 `useEveAgent`，而不是 raw routes。
