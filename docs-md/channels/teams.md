---
title: "Microsoft Teams"
description: "通过 Bot Framework Activity protocol 从 Microsoft Teams 访问你的 agent，并使用 Adaptive Card human-in-the-loop prompts。"
type: integration
---

Teams channel 会把你的 agent 作为 bot 运行在 Microsoft Teams 内。它接收 Bot Framework Activity POSTs，检查每个请求上的 Bot Connector bearer JWT，并把 message activities 路由到你的 agent。Human-in-the-loop（HITL）prompts 会以 Adaptive Cards 返回，replies 则通过 Bot Framework Connector REST API 发出。它基于的 contract 见 [Channels](./overview)。

## 添加 channel

```ts title="agent/channels/teams.ts"
import { teamsChannel } from "eve/channels/teams";

export default teamsChannel();
```

```bash
MICROSOFT_APP_ID=...
MICROSOFT_APP_PASSWORD=...
MICROSOFT_TENANT_ID=...   # optional, single-tenant bots
```

默认情况下，该 channel 挂载在 `POST /eve/v1/teams`。请把你的 Azure Bot 或 Teams app messaging endpoint 指向该 public URL。若要挂载到其他位置，请传入 `route: "/api/teams/activity"`。

## channel 如何处理 messages

### Dispatch

默认 `onMessage` 处理两种情况：personal-chat messages，以及直接 mention bot 的 channel 或 group-chat messages。除非你覆盖它，否则 ambient resource-specific-consent messages 会被 drop。dispatch 前，eve 会剥离 mention，添加 `<teams_context>` block，并按 root activity id（`replyToId ?? id`）为 channel 和 group threads 定作用域。

```ts
import { defaultTeamsAuth, teamsChannel } from "eve/channels/teams";

export default teamsChannel({
  onMessage(ctx, message) {
    if (message.scope !== "personal" && !message.isBotMentioned) return null;
    return { auth: defaultTeamsAuth(message) };
  },
});
```

### Delivery

Replies 会作为 Markdown（`textFormat: "markdown"`）发布，超长文本会拆分到多条 messages 中，并在 turn start 和 action requests 时发送 typing indicator。

### Human-in-the-loop (HITL)

human-in-the-loop（HITL）`input.requested` event 会渲染为 Adaptive Card。Buttons 和 options 映射为 `Action.Submit`，selects 映射为 `Input.ChoiceSet`，freeform 映射为 `Input.Text`。用户提交后，activity 会为你转换成 eve `inputResponses`。对于非 HITL 的 invokes，请在 `onInvoke(ctx, activity)` 中处理。

### Proactive sessions

Proactive sessions 需要已有 conversation reference，因为 Bot Framework v1 surface 无法通过 Azure Active Directory（AAD）user id 创建新 chats。请把 `serviceUrl`、`conversationId` 和其他 reference fields 传给 `receive(teams, { target })`。

### Attachments

Inbound files 默认关闭。选择启用后，可以允许 personal-scope downloads 和 public media URLs：

```ts
export default teamsChannel({
  files: { enabled: true, allowedHosts: ["contoso.sharepoint.com"] },
});
```

## 接下来阅读

- [Channels overview](./overview)：channel contract 和每个 built-in channel
- [Auth & route protection](../guides/auth-and-route-protection)：authenticating inbound traffic
