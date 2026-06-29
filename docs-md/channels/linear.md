---
title: "Linear"
description: "通过 Linear Agent Sessions 访问你的 agent，并用原生 Agent Activities 表示进度、问题和响应。"
type: integration
---

Linear channel 使用 Linear 的 Agent Session surface，而不是普通 comments。用户从 Linear 将工作委派给 agent，eve 在 `/eve/v1/linear` 接收 `AgentSessionEvent` webhooks，该 channel 则用原生 Agent Activities 回复，包括 `thought`、`action`、`elicitation`、`response` 和 `error`。它基于的 contract 见 [Channels](./overview)。

## 添加 channel

```ts title="agent/channels/linear.ts"
import { linearChannel } from "eve/channels/linear";

export default linearChannel({
  credentials: {
    accessToken: process.env.LINEAR_AGENT_ACCESS_TOKEN,
    webhookSecret: process.env.LINEAR_WEBHOOK_SECRET,
  },
});
```

```bash
LINEAR_AGENT_ACCESS_TOKEN=lin_api_... # posts Agent Activities and creates proactive sessions
LINEAR_WEBHOOK_SECRET=...             # verifies Linear-Signature
```

示例显式传入 credentials。若要改用 env vars，请移除 `credentials` block：access token 会 fallback 到 `LINEAR_AGENT_ACCESS_TOKEN`、`LINEAR_ACCESS_TOKEN`、`LINEAR_API_KEY` 或 `LINEAR_API_TOKEN`，webhook secret 会 fallback 到 `LINEAR_WEBHOOK_SECRET`。两个字段也都接受 lazy resolver functions。

## 配置 Linear

创建 Linear OAuth app，启用 Agent Session events，并把 webhook URL 指向：

```text
https://<deployment>/eve/v1/linear
```

对于 Linear 的 agent surface，请用 `actor=app` 配置 OAuth authorize URL，并授予 app 可在 Linear 中作为 agent 出现的 scopes，包括 `app:assignable` 和 `app:mentionable`。订阅 `AgentSessionEvent` webhook category，这样当 agent 被委派或 mention 时，Linear 会发送 `created` events；当用户继续 session 时，会发送 `prompted` events。

Linear 会在 `Linear-Signature` 中发送 webhook signatures；eve 会验证 raw body 上的 HMAC，并拒绝 stale `webhookTimestamp` values。如果 trusted gateway 在 request 到达 eve 前已经验证 Linear，请传入 `credentials.webhookVerifier`，而不是 webhook secret。

## channel 如何处理 messages

### Dispatch

默认 hook 会 dispatch `created` 和 `prompted` Agent Session events。eve 会添加一个包含 agent session、issue、comment 和 organization identifiers 的 Linear context block，然后用 `agent-session:<id>` 继续同一个 session。

### Delivery

Turn start 会发布 ephemeral `thought`，tool calls 会发布 ephemeral `action` activities，final assistant text 会发布 durable `response`，failures 会发布 `error` activities。当 model 在 tool call 前发出文本时，eve 会 buffer 第一行非空文本，并把它用作下一个 ephemeral Linear `thought`，与 Slack 的 typing-status 行为相似。

### Human-in-the-loop (HITL)

Human-in-the-loop（HITL）input requests 会渲染为 Linear `elicitation` activities。当用户回复 Agent Session 时，该 channel 会把 prompt 解析回 pending eve input request，并用 `inputResponses` 恢复。

### Proactive sessions

使用 `receive(linear, { target })` 可以在没有 inbound webhook 的情况下启动 session。target shape 和示例见下方 [Proactive sessions](#proactive-sessions)。

### Attachments

此 channel 目前不支持 inbound file attachments。

### API handle

Event handlers 会收到 `channel.linear`，它暴露 `createActivity`、`listActivities` 和 `updateSession`，用于 custom Agent Activity delivery 和 Agent Session metadata。

## Custom hooks

返回 `{ auth }` 表示 dispatch，返回 `null` 表示 acknowledge 但不唤醒 agent。

```ts
import { defaultLinearAuth, linearChannel } from "eve/channels/linear";

export default linearChannel({
  onAgentSession: (_ctx, event) => {
    if (event.action !== "created" && event.action !== "prompted") return null;
    return { auth: defaultLinearAuth(event) };
  },
});
```

在 `onAgentSession` 中检查 `event.agentSession.issue`，可以把 dispatch 限制到 Linear teams 或 projects 的子集。通过在 `auth` 旁返回 `context` 添加额外 context。

```ts
import { defaultLinearAuth, linearChannel } from "eve/channels/linear";

export default linearChannel({
  onAgentSession: (_ctx, event) => {
    if (event.agentSession.issue?.identifier?.startsWith("OPS-") !== true) return null;
    return {
      auth: defaultLinearAuth(event),
      context: ["Only make reversible changes unless the issue says otherwise."],
    };
  },
});
```

当你想要更具体的 Agent Activities 时，可以覆盖 event delivery。

```ts
import { linearChannel } from "eve/channels/linear";

export default linearChannel({
  events: {
    async "message.completed"(eventData, channel) {
      if (eventData.finishReason === "tool-calls" || !eventData.message) return;
      await channel.linear.createActivity({
        body: `Done.\n\n${eventData.message}`,
        type: "response",
      });
    },
    async "input.requested"(eventData, channel) {
      await channel.linear.createActivity({
        body: eventData.requests.map((request) => request.prompt).join("\n\n"),
        type: "elicitation",
      });
    },
  },
});
```

当你的 agent 创建 external artifact 时，可以添加 session-level links。

```ts
await channel.linear.updateSession({
  addedExternalUrls: [{ label: "Run log", url: "https://example.com/runs/123" }],
});
```

## Proactive sessions

使用该 channel 的 `receive` target 可以继续已有 Agent Session，或从 Linear issue 或 root comment 创建一个。target 接受已有 `agentSessionId`，也接受 `issueId` 或 root `commentId`，用于在发送 message 前创建新 session。下面的示例从 schedule 运行；route handler 可通过自己的 `receive` helper 使用同一 target shape。

```ts
import { defineSchedule } from "eve/schedules";

import linear from "../channels/linear.js";

export default defineSchedule({
  cron: "0 14 * * 1",
  async run({ receive, waitUntil, appAuth }) {
    waitUntil(
      receive(linear, {
        auth: appAuth,
        message: "Post a concise status update with blockers and next actions.",
        target: {
          issueId: "EVE-123",
          initialActivity: "Preparing the status update.",
        },
      }),
    );
  },
});
```

对于 issue 或 comment targets，该 channel 会在启动 eve turn 前调用 Linear 的 proactive Agent Session mutations。对于已有 `agentSessionId`，它会跳过 session creation，只 seed continuation token。

## 接下来阅读

- [Channels overview](./overview)：channel contract 和每个 built-in channel
- [Connections](../connections)：当 agent 需要从另一个 channel inspect 或 edit Linear data 时，使用 Linear MCP connection
