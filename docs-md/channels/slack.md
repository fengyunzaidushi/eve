---
title: "Slack"
description: "通过 Slack app mentions 和 DMs 访问你的 agent，支持 thread anchoring、buttons 和 Vercel Connect credentials。"
type: integration
---

Slack channel 会把你的 agent 放进 workspace。它会响应 `@mentions` 和 DMs，在线程中回复，显示 typing indicators，并把 human-in-the-loop（HITL）prompts 转成 buttons。当 conversation 应发生在团队已经工作的地方时，请使用它。Credentials 通过 [Vercel Connect](../guides/auth-and-route-protection) 处理，后者同时负责 outbound bot token 和 inbound webhook verification，因此你不需要管理 `SLACK_BOT_TOKEN` 或 `SLACK_SIGNING_SECRET`。它基于的 contract 见 [Channels](./overview)。

## 设置 Connect

创建 Slack Connect client 并复制其 UID（例如 `slack/my-agent`），然后把此 project 作为 trigger destination attach 到 eve 的 Slack route：

```bash
npm install -g vercel@latest && export FF_CONNECT_ENABLED=1
vercel connect create slack --triggers
vercel connect detach <uid> --yes
vercel connect attach <uid> --triggers --trigger-path /eve/v1/slack --yes
```

`FF_CONNECT_ENABLED=1` 会开启 Connect commands，这些命令目前在 Vercel CLI 中受 feature flag 控制。`create` 步骤会在默认 Connect path 上 provision 一个 destination。由于 eve 不提供默认 Connect path，`detach` 再 `attach --trigger-path /eve/v1/slack` 会把 trigger 重新指向 eve Slack route。`--triggers` 会开启 Slack Event Subscriptions；没有它，Slack 不会投递 `app_mention` 或 `message.im`。你也可以从 [Connect dashboard](https://vercel.com/d?to=/%5Bteam%5D/~/connect&title=Go+to+Connect) 创建 client。

## 添加 channel

用 `eve channels add slack` scaffold channel 及其 dependency，或手动设置：

```bash
npm install @vercel/connect
```

```ts title="agent/channels/slack.ts"
import { connectSlackCredentials } from "@vercel/connect/eve";
import { slackChannel } from "eve/channels/slack";

export default slackChannel({
  credentials: connectSlackCredentials("slack/my-agent"),
});
```

`connectSlackCredentials` 返回 `{ botToken, webhookVerifier }`，把 token rotation、multi-workspace tenancy 和 request verification 留在 Connect 中，而不是放进你的代码。trigger destination 和 channel file 准备好后即可 deploy：

```bash
VERCEL_USE_EXPERIMENTAL_FRAMEWORKS=1 vercel deploy --prod
```

`VERCEL_USE_EXPERIMENTAL_FRAMEWORKS=1` 让 Vercel CLI 在 build 期间把 eve 识别为 framework。eve 自己的 setup commands 会设置同一个 flag。

## channel 如何处理 messages

### Dispatch

Inbound hooks 决定是否 dispatch 一个 turn，以及使用什么 `auth`。返回 `{ auth }` 表示 dispatch，返回 `null` 表示 drop，返回 `{ auth, context }` 表示向 history 注入 background。

- `onAppMention(ctx, message)` 处理 `app_mention` events。默认实现会派生 workspace-scoped auth，并发布 `Thinking…` indicator。
- `onDirectMessage(ctx, message)` 处理 `message.im` events（需要 `im:history` scope）。Bot-authored messages 和 edits 会先被过滤掉。
- `onInteraction(action, ctx)` 处理未被 HITL 消耗的 `block_actions` callbacks。

默认情况下，你会拿到触发 mention，但拿不到 thread 中更早的 replies。使用 `loadThreadContextMessages` 拉取它们，并以 `context` 返回；eve 会把它们作为 user messages 追加到 history 中，model 在后续每个 turn 都会看到。使用 `since: "last-agent-reply"`，让同一 thread 中的重复 mentions 只注入新内容：

```ts
import { defaultSlackAuth, loadThreadContextMessages, slackChannel } from "eve/channels/slack";
import { connectSlackCredentials } from "@vercel/connect/eve";

export default slackChannel({
  credentials: connectSlackCredentials("slack/my-agent"),
  async onAppMention(ctx, message) {
    const auth = defaultSlackAuth(message, ctx);
    const prior = await loadThreadContextMessages(ctx.thread, message, {
      since: "last-agent-reply",
    });
    if (prior.length === 0) return { auth };
    const transcript = prior
      .map((m) => `${m.isMe ? "you" : (m.user ?? "user")}: ${m.markdown}`)
      .join("\n");
    return { auth, context: [`Recent thread messages since your last reply:\n\n${transcript}`] };
  },
});
```

### Delivery

默认 handlers 会在 thread 内回复并显示进度。Typing indicators 会自动发布：inbound 时为 `Thinking…`，`turn.started` 时为 `Working…`，`actions.requested` 时显示 tool status。可覆盖 `onAppMention` 或 `events` handlers 来 customize。

当 session 在没有 `threadTs` 的情况下启动（例如来自 schedule 或 `receive(slack, ...)`）时，它会 anchor 在第一个 agent post 上，后续 posts 和 mentions 会恢复同一个 session。也可以传入带 `Card` 的 `initialMessage`，先落下一个 structured anchor。`threadTs` 和 `initialMessage` 互斥。

下面的示例覆盖 `onAppMention`，基于 authored message gate，并把 completed reply 发布到 thread。Event handlers 会收到 `(eventData, channel, ctx)`，Slack platform handles 位于 `channel.thread` 和 `channel.slack`：

```ts
import { defaultSlackAuth, slackChannel } from "eve/channels/slack";
import { connectSlackCredentials } from "@vercel/connect/eve";

export default slackChannel({
  credentials: connectSlackCredentials("slack/my-agent"),
  onAppMention: (ctx, message) =>
    message.author ? { auth: defaultSlackAuth(message, ctx) } : null,
  events: {
    "message.completed"(eventData, channel, ctx) {
      if (eventData.finishReason === "tool-calls") return;
      if (eventData.message) channel.thread.post(eventData.message);
    },
  },
});
```

### Human-in-the-loop (HITL)

HITL 会渲染为 Slack buttons 和 selects。用户响应后，parked session（暂停等待 input）会恢复。

Authorization prompts 是私有的。sign-in challenge（OAuth URL、device code）是一种 credential。任何完成它的人都会把自己的 identity 绑定到 session 的 connection。默认 `authorization.required` handler 会把 challenge（包括 device code）以 ephemeral 方式投递给触发用户，并且只有在没有可定向用户时才发布不含链接的 public status。该 handler 会收到带有 `postEphemeral`、`postDirectMessage`（需要 `im:write` scope）和 `state` 的 private-delivery context。这里有意不提供 public `post`，也没有 raw API access。

```ts
events: {
  "authorization.required"(eventData, channel) {
    const userId = channel.state.triggeringUserId;
    if (!userId || !eventData.authorization?.url) return;
    return channel.postDirectMessage(userId, `Sign in to continue: ${eventData.authorization.url}`);
  },
},
```

### Proactive sessions

可以从 schedule `run` handler 中通过 `receive(slack, { message, target, auth })`，或从另一个 channel 中通过 `args.receive(slack, ...)`，在没有 inbound message 的情况下启动 session。proactive target shape 是 `{ channelId }`。

### Attachments

位于 authenticated Slack URLs 后面的 inbound files 会通过 `fetchFile` staged。`fetchFile` contract 见 [File uploads](./custom#file-uploads)。

## 接下来阅读

- [Channels overview](./overview)：channel contract 和每个 built-in channel
- [Auth & route protection](../guides/auth-and-route-protection)：authenticating inbound traffic
