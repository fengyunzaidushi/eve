---
title: "Discord"
description: "通过 Discord HTTP Interactions 访问你的 agent，包括 slash commands、components 和 modals。"
type: integration
---

Discord channel 会把你的 agent 接入 Discord 的 HTTP Interactions，包括 slash 和 application commands、message components 以及 modal submissions。Discord 强制三秒 ACK deadline，因此该 channel 会验证 Ed25519 signature headers，立即 acknowledge command，并在后台运行 eve work。它基于的 contract 见 [Channels](./overview)。

## 添加 channel

```ts title="agent/channels/discord.ts"
import { discordChannel } from "eve/channels/discord";

export default discordChannel();
```

```bash
DISCORD_PUBLIC_KEY=...      # verifies X-Signature-Ed25519 + X-Signature-Timestamp
DISCORD_APPLICATION_ID=...  # edits the deferred response and sends followups
DISCORD_BOT_TOKEN=...       # proactive messages + fallback + typing indicators
```

如果要跳过 env vars，请通过 `credentials: { applicationId, botToken, publicKey }` 传入相同值。默认 route 是 `POST /eve/v1/discord`。把这个 public URL 粘贴到你的 Discord application 的 Interactions Endpoint URL。

## 注册 command

注册 commands 由你负责，不由 channel 负责。使用 Discord API 或 Developer Portal。名为 `message` 的 string option 会与 eve 默认 prompt extraction 对齐：

```bash
curl -X PUT "https://discord.com/api/v10/applications/$DISCORD_APPLICATION_ID/commands" \
  -H "Authorization: Bot $DISCORD_BOT_TOKEN" -H "Content-Type: application/json" \
  -d '[{"name":"ask","description":"Ask the eve agent","type":1,
    "options":[{"name":"message","description":"What should the agent do?","type":3,"required":true}]}]'
```

development 期间使用 guild commands 可以更快传播。

## channel 如何处理 messages

### Dispatch

`onCommand(ctx, interaction)` 决定是否 dispatch，以及使用什么 `auth`。返回 `{ auth }` 表示继续，返回 `null` 表示 drop interaction。默认情况下，auth 来自 invoking user。Event handlers 会收到 `(eventData, channel, ctx)`，Discord platform handles 位于 `channel.discord`：

```ts
import { discordChannel } from "eve/channels/discord";

export default discordChannel({
  onCommand: (ctx, interaction) => ({
    auth: {
      principalId: interaction.user.id,
      principalType: "user",
      authenticator: "discord",
      attributes: { channel_id: interaction.channelId, guild_id: interaction.guildId ?? "" },
    },
  }),
  events: {
    "message.completed"(eventData, channel, ctx) {
      if (eventData.finishReason === "tool-calls") return;
      if (eventData.message) channel.discord.post(eventData.message);
    },
  },
});
```

### Delivery

默认 `message.completed` handler 会为第一条 reply 编辑 deferred response，之后发送 followups。如果 interaction token 被拒绝，它会回退到 bot-authenticated channel message。长文本会按 Discord 的 2000 字符限制拆分，generated messages 默认使用 `allowed_mentions: { parse: [] }`。

Typing 会在 `turn.started` 和 `actions.requested` 上触发，但只有存在 bot token 时才会触发。在 custom hooks 中，请自行调用 `channel.discord.startTyping()`。

### Human-in-the-loop (HITL)

HITL 会渲染为 Discord components。Confirmations 和 options 会变成 buttons，`display: "select"` 会变成 string select，freeform input 会变成打开 modal 的 button。用户响应后，parked session（暂停等待 input）会恢复。

### Proactive sessions

可以从 schedule `run` handler 中通过 `receive(discord, { message, target, auth })`，或从另一个 channel 中通过 `args.receive(discord, ...)`，在没有 inbound interaction 的情况下启动 session。proactive target shape 是 `{ channelId, conversationId?, initialMessage? }`。任一路径都需要 `DISCORD_BOT_TOKEN`。

### Attachments

此 channel 目前不支持 inbound file attachments。

## 接下来阅读

- [Channels overview](./overview)：channel contract 和每个 built-in channel
- [Auth & route protection](../guides/auth-and-route-protection)：authenticating inbound traffic
