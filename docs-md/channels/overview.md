---
title: "概览"
description: "用户如何访问你的 agent：channel contract、基础 eve HTTP channel，以及编写 custom channels。"
---

channel 是 platform 与你的 agent 之间的 edge adapter。它做三件事：

- 将 platform input 规范化为 user message。
- 拥有 `continuationToken`，即该 surface 上 conversation 的 resume handle。
- 决定 delivery，也就是 response 如何、在哪里以及是否返回。

eve 随附一个基础 HTTP channel 和一组 first-class platform channels，你也可以编写自己的 channel。完整集合见 [Integrations](/integrations) gallery。

每个 channel 都有自己的 provider terms、data flow、auth model 和 user-consent expectations。在通过 channel 发送非公开、敏感、受监管或生产数据之前，请确认 channel provider 以及你配置的 scopes、signature checks、route auth 和 delivery behavior 适合你的 use case。

## Channels 的位置

Channel files 位于 root agent 的 `agent/channels/` 下。文件主名就是 channel id：`agent/channels/intake.ts` 会被寻址为 `intake`。请把 channel 作为 module 的 default export 导出。Local subagents 不声明 channels。

```text
agent/
  agent.ts
  channels/
    eve.ts
    slack.ts
    intake.ts
```

可以用 `eve channels add`（interactive）scaffold channel file，也可以传入 kind：`eve channels add slack` 或 `eve channels add web`。你也可以手写该文件。

## eve HTTP channel（默认）

eve channel 是 framework 默认的 HTTP session API，也是 terminal UI、[`useEveAgent`](../guides/frontend/overview) 和 `curl` 都会访问的 routes。即使没有 `agent/channels/eve.ts` 文件，它也默认启用。只有在需要覆盖 defaults 时才添加该文件，最常见的是覆盖 route auth policy。routes、auth 和 customization 见 [HTTP channel](./eve)。

## Custom channels

当 eve 没有为你的 surface 随附 channel 时，可以用来自 `eve/channels` 的 `defineChannel` 构建一个。custom channel 会声明 route handlers（`GET`、`POST`、`PUT`、`PATCH`、`DELETE`、`WS`）、`events` map，以及 handler 内用于启动或恢复 session 的 `send` call。完整 walkthrough 见 [Custom channels](./custom)，包括 WebSocket routes、cross-channel hand-off、channel metadata、continuation tokens 和 file uploads。

## 与 Chat SDK 的关系

eve 使用 Chat SDK 的 **card-builder components**（Cards、Buttons、Actions 等）来组合 rich Slack messages。当你用 [Slack channel](./slack) 构建 card 时，底层 primitives 来自 Chat SDK，并在 post time 转换为 Slack Block Kit。

eve **不** 使用 Chat SDK 的 runtime。`Chat`、`Adapter` 和 `Thread` primitives 永远不会被导入，也无法通过 eve public API 访问。eve 实现了自己的 channel layer（webhook handling、signature verification、event parsing 和 thread management）。构建 Slack messages 的体验类似 Chat SDK cards，但接入 channel 意味着针对 eve 的 `defineChannel(...)` API 编写，而不是使用 Chat SDK adapter。

## 选择哪个 channel？

| You want…                                   | Use                                                        |
| ------------------------------------------- | ---------------------------------------------------------- |
| web app / browser chat UI                   | eve channel + [`useEveAgent`](../guides/frontend/overview) |
| Local tooling、SDK clients、`curl`          | eve channel（default）                                     |
| Slack mentions、DMs、buttons                | [Slack](./slack)                                           |
| Discord slash commands、components          | [Discord](./discord)                                       |
| Microsoft Teams messages + Adaptive Cards   | [Teams](./teams)                                           |
| Telegram bot messages                       | [Telegram](./telegram)                                     |
| SMS 或 speech-transcribed phone calls       | [Twilio](./twilio)                                         |
| GitHub @mentions、带 checkout 的 PR review  | [GitHub](./github)                                         |
| Linear issue delegation 和 Agent Sessions   | [Linear](./linear)                                         |
| 其他任何内容（internal webhook、WebSocket） | Custom channel（上文的 `defineChannel`）                   |

## 免责声明

作为 deployer，你有责任确保你的 agent 符合适用法律。

当 eve agent 与人沟通时，如果法律要求，你可能需要披露他们正在与自动化 AI 系统互动。eve 不会自动添加这类披露；请在 instructions 和/或 channel responses 中配置。

## 接下来阅读

- [Slack](./slack)：最常见的 platform channel，端到端说明
- [Custom channels](./custom)：用 `defineChannel` 为任何 surface 构建 channel
- [Frontend](../guides/frontend/overview)：用 `useEveAgent` 在 eve channel 上构建 browser chat
- [Integrations](/integrations)：在一个 gallery 中浏览所有 built-in channel 和 connection
