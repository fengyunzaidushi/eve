---
title: "Telegram"
description: "通过 Telegram bot webhooks 访问你的 agent，支持 inline-keyboard human-in-the-loop prompts 和 attachments。"
type: integration
---

Telegram channel 会把你的 agent 放在 Telegram bot 后面。它接收 Bot API webhooks，在信任任何内容前检查 `X-Telegram-Bot-Api-Secret-Token` header，并把关心的 messages（private chats，以及指向 bot 的 group messages）路由到通过 `sendMessage` 发出的 reply。它基于的 contract 见 [Channels](./overview)。

## 添加 channel

```ts title="agent/channels/telegram.ts"
import { telegramChannel } from "eve/channels/telegram";

export default telegramChannel({
  botUsername: "my_bot",
});
```

```bash
TELEGRAM_BOT_TOKEN=123456:...        # replies, typing, callbacks, proactive sends
TELEGRAM_WEBHOOK_SECRET_TOKEN=...    # must match the secret_token you register
```

你可以通过 `credentials: { botToken, webhookSecretToken }` 传入相同值。该 channel 挂载 `POST /eve/v1/telegram`。请自行注册 deployed URL；eve 不会调用 `setWebhook`：

```bash
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://your-app.example.com/eve/v1/telegram",
       "secret_token":"'"$TELEGRAM_WEBHOOK_SECRET_TOKEN"'",
       "allowed_updates":["message","callback_query"]}'
```

## channel 如何处理 messages

### Dispatch

在 private chat 中，text、captions、photos 和 documents 都会通过。Groups 更严格。只有三种内容会唤醒 bot：command（`/ask`、`/ask@my_bot`）、`@my_bot` mention（设置了 `botUsername` 时），或对 bot 自己 message 的 reply。其他所有内容都会被忽略。

Forum topics 会在 continuation token 中携带 `message_thread_id`，因此每个 topic 都会留在自己的 thread 上。

若要 customize auth 或 filtering，请覆盖 `onMessage`。Group privacy mode 本身位于 BotFather 中，不在这里。

### Delivery

默认 `message.completed` handler 会通过 `sendMessage` 发送 plain text。它不传入 `parse_mode`，因此任何 Markdown 都会按字面显示。超过 Telegram 4096 字符限制的 replies 会拆分为多条 messages。Custom handlers 使用 `channel.telegram`。

### Human-in-the-loop (HITL)

Human-in-the-loop（HITL）会把 option requests 转成 inline-keyboard buttons，把 freeform requests 转成 `ForceReply`。Telegram 将 `callback_data` 限制为 64 bytes，因此 eve 会改为在 channel state 中保存 compact callback ids。它会用 `answerCallbackQuery` acknowledge 自己的 callbacks；任何无法识别的内容都会进入 `onCallbackQuery`。

### Proactive sessions

可以从 schedule `run` handler 中通过 `receive(telegram, { message, target, auth })`，或从另一个 channel 中通过 `args.receive(telegram, ...)`，在没有 inbound message 的情况下启动 session。`target.chatId` 必填。添加 `messageThreadId` 可落到特定 forum topic 中。

### Attachments

支持 inbound photos 和 documents。只有当 upload policy 允许该类型时，eve 才会通过 `getFile` 按需获取它们：

```ts
export default telegramChannel({
  botUsername: "my_bot",
  uploadPolicy: { allowedMediaTypes: ["image/*", "application/pdf"], maxBytes: 10 * 1024 * 1024 },
});
```

## 接下来阅读

- [Channels overview](./overview)：channel contract 和每个 built-in channel
- [Auth & route protection](../guides/auth-and-route-protection)：authenticating inbound traffic
