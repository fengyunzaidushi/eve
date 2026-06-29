---
title: "Twilio"
description: "通过 Twilio 上的 SMS 和 speech-transcribed phone calls 访问你的 agent。"
type: integration
---

Twilio channel 会把你的 agent 放到一个 phone number 上，这样人们可以给它发短信或打电话。Inbound SMS 以 webhook 形式到达。Inbound calls 会用 TwiML `<Gather input="speech">` 接听，生成的 transcript 会送入 SMS 使用的同一个 eve session，因此 caller 和 texter 在下游看起来相同。在运行任何其他内容前，每个 request 都会根据 `X-Twilio-Signature` 检查。raw continuation token 是 `From:To`。它基于的 contract 见 [Channels](./overview)。

## 添加 channel

```ts title="agent/channels/twilio.ts"
import { twilioChannel } from "eve/channels/twilio";

export default twilioChannel({
  allowFrom: "+15551234567",
  messaging: { from: "+15557654321" },
});
```

```bash
TWILIO_ACCOUNT_SID=AC...   # required for default outbound SMS
TWILIO_AUTH_TOKEN=...      # required for inbound signature verification
```

如果要跳过 env vars，请通过 `credentials: { accountSid, authToken }` 传入相同值。该 channel 挂载三条 routes：

- `POST /eve/v1/twilio/messages`：Messaging webhook
- `POST /eve/v1/twilio/voice`：inbound call webhook
- `POST /eve/v1/twilio/voice/transcription`：speech transcript callback

请把你的 Twilio number 的 Messaging webhook 指向 `/messages`，Voice webhook 指向 `/voice`，并使用 Twilio 将要调用的精确 public URL。

## channel 如何处理 messages

### Dispatch

`allowFrom` 必填。它 gate 谁可以访问 inbound hooks。传入单个号码、列表、async resolver 或 `"*"`。wildcard 很危险；只有在 `onText`/`onVoice` 内有显式检查时才使用它。

```ts
export default twilioChannel({ allowFrom: ["+15551234567", "+15557654321"] });
```

`onText` 和 `onVoiceTranscription` 决定 dispatch 和 `auth`。返回 `{ auth }` 表示继续，返回 `null` 表示 drop message。`onVoice` 会在 call 进入时立即触发。返回 `null` 表示拒绝，或返回 object 来覆盖 spoken prompt、language、`<Say voice>` 和 speech-recognition options。

```ts
export default twilioChannel({
  allowFrom: ["+15551234567"],
  onText: (ctx, message) => ({
    auth: {
      principalId: message.from,
      principalType: "user",
      authenticator: "twilio",
      attributes: { to: message.to ?? "" },
    },
  }),
});
```

### Delivery

默认 `message.completed` handler 会通过 Twilio Messages API 以 SMS 发送 reply。对 inbound message 的 reply 可以复用 webhook 的 `To` 作为 sender，但 proactive send 没有可复用内容，因此需要 `messaging.from` 或 `messaging.messagingServiceSid`。在 proxy 后面，请设置 `webhookUrl`，让 signature verification 匹配精确配置的 URL，并设置 `publicBaseUrl`，让 voice TwiML 可以构建 absolute callback URLs。

### Human-in-the-loop (HITL)

SMS 和 voice 没有 native button 或 card affordance，因此 HITL prompts 不会渲染为 interactive controls。如果你声明了 `events["input.requested"]` handler，agent 的 `input.requested` event 会到达那里。请通过发送文本 prompt 并自行把 caller 的 reply 映射回 input request 来处理它。

### Proactive sessions

可以从 schedule `run` handler 中通过 `receive(twilio, { message, target, auth })`，或从另一个 channel 中通过 `args.receive(twilio, ...)`，在没有 inbound message 的情况下启动 session。`target.phoneNumber` 必填，并且 channel 需要 `messaging.from` 或 `messaging.messagingServiceSid` 作为 outbound sender。

### Attachments

此 channel 目前不支持 inbound media attachments。

## 免责声明

作为 deployer，你有责任确保你的 agent 符合适用法律。

例如，你可能需要告知 callers 和 texters 通话会被记录/转录并由自动化 AI 系统处理，并在要求时取得同意（包括 two-party-consent jurisdictions）。对于你发起的 outbound SMS 或 calls，你可能需要取得 prior express consent，遵守 STOP/opt-out 和 quiet-hour rules，并完成所需 carrier registration。

## 接下来阅读

- [Channels overview](./overview)：channel contract 和每个 built-in channel
- [Auth & route protection](../guides/auth-and-route-protection)：authenticating inbound traffic
