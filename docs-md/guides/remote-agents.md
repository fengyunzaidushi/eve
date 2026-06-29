---
title: "Remote Agents"
description: "使用 defineRemoteAgent 将另一个 eve deployment 作为 subagent 调用：相同的 lowered tool shape、outbound auth、durable callback dispatch。"
---

`defineRemoteAgent` 会像调用 local subagent 一样调用单独部署的 eve agent。当你要委派的 specialist 是拥有自己 URL 的单独 agent，而不是 repo 中的目录时，请使用它。

文件位于 `agent/subagents/` 下，因此其 tool name 会从路径派生。没有 `name` 字段。

```ts title="agent/subagents/weather.ts"
import { defineRemoteAgent } from "eve";
import { vercelOidc } from "eve/agents/auth";

export default defineRemoteAgent({
  url: "https://weather-agent.example.com",
  description: "Answers weather, temperature, forecast, wind, rain, and snow questions.",
  auth: vercelOidc(),
});
```

`defineRemoteAgent` 接受：

| Parameter      | Type                            | Required | Default           | Description                                                                                                                               |
| -------------- | ------------------------------- | -------- | ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `url`          | `string`                        | Yes      | n/a               | 要调用的 remote eve deployment 的 Base URL。                                                                                              |
| `description`  | `string`                        | Yes      | n/a               | model-visible delegation description。                                                                                                    |
| `auth`         | `OutboundAuthFn`                | No       | none              | 来自 `eve/agents/auth` 的 outbound auth hook。                                                                                            |
| `headers`      | `HeadersValue`                  | No       | none              | Static 或 lazily resolved request headers。                                                                                               |
| `path`         | `string`                        | No       | `/eve/v1/session` | 附加到 `url` 上、用于 create-session request 的 route。                                                                                   |
| `outputSchema` | `StandardSchema \| JSON Schema` | No       | none              | caller 要求的 structured return type。会在 compile time lowered 到 JSON Schema，并由 remote 像任何 task-mode output schema 一样强制执行。 |

## Lowered tool

remote agent 会 lower 为与 local subagent 相同的 `{ message, outputSchema? }` tool shape。parent 会把 remote 所需的所有内容打包进 `message`。remote 永远看不到 parent 的 history。设置 `outputSchema`（在这里或 per call），remote 会以 task mode 运行（single-shot delegation，返回一个 structured result，而不是 open conversation；见 [Subagents](../subagents)），并把 structured output 作为 tool result 返回。

## Outbound auth

`auth` 是来自 `eve/agents/auth` 的 `OutboundAuthFn`，它会把 request headers 附加到 outbound dispatch：

| Helper                          | Header                                                                        |
| ------------------------------- | ----------------------------------------------------------------------------- |
| `vercelOidc(opts?)`             | `Authorization: Bearer <Vercel OIDC token>`（deployment-to-deployment trust） |
| `bearer(token)`                 | `Authorization: Bearer <token>`（static 或 lazily resolved）                  |
| `basic({ username, password })` | `Authorization: Basic …`                                                      |

如果你调用另一个部署在 Vercel 上的 eve agent，请使用 `vercelOidc()`。remote 会验证 OIDC token 来 authorize caller。receiving side 见 [Auth & route protection](./auth-and-route-protection)。

## remote dispatch 和 callbacks 如何工作

local subagent inline 运行。remote subagent 在自己的 deployment 中运行，因此 dispatch 是 asynchronous 的：

1. parent 在 remote 的 `POST /eve/v1/session` 上启动 task-mode session，并传入 framework callback URL。
2. parent turn 会 park（durably suspend 且不占用 compute；见 [Execution model & durability](../concepts/execution-model-and-durability)），直到 remote post terminal callback。
3. callback 到达后，parent 恢复并暴露 result。

parent stream 携带与 local delegation 相同的 `subagent.called`、`action.result` 和 `subagent.completed` events。对于 remote call，`subagent.called.data.remote.url` 会记录 target。

两条 failure paths 都会作为 failed tool result 暴露给 parent，因此 caller 可以在同一个 session 内解释或恢复。failed _start_ 会 inline 返回 error。启动后失败的 remote 会 post terminal failure callback，parent 会把它接收为 errored subagent result，携带 remote 的 error（未提供时为 `REMOTE_AGENT_FAILED`）。Terminal callback delivery 会作为 durable step 运行在底层 workflow engine 上（见 [Execution model & durability](../concepts/execution-model-and-durability)）。失败的 callback POST 会被 rethrow，而不是标记 task complete，因此 engine 会 retry。

## 接下来阅读

- Local delegation 和 isolation boundary → [Subagents](../subagents)
- 让 model 以编程方式编排 remote agents → [Dynamic workflows](./dynamic-workflows)
- 保护 receiving deployment → [Auth & route protection](./auth-and-route-protection)
