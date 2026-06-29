---
title: "GitHub"
description: "通过 GitHub App webhooks 访问你的 agent，支持 @mention dispatch、PR diff context 和 sandbox checkout。"
type: integration
---

GitHub channel 让 agent 可以直接在 repository 上工作。有人在 issue、PR 或 review comment 中 `@mentions` 它时，agent 会直接在 thread 中回答，此时 PR diff 已经在 context 中，repo 也已 checkout 到 sandbox。它在 `/eve/v1/github` 接收 GitHub App webhooks，检查 signature，从触发 event 的人派生 auth，并在原生 surface 上回复。它基于的 contract 见 [Channels](./overview)。

## 添加 channel

```ts title="agent/channels/github.ts"
import { githubChannel } from "eve/channels/github";

export default githubChannel({
  botName: "my-agent",
  credentials: {
    appId: process.env.GITHUB_APP_ID,
    privateKey: process.env.GITHUB_APP_PRIVATE_KEY,
    webhookSecret: process.env.GITHUB_WEBHOOK_SECRET,
  },
});
```

每个字段都会 fallback 到 env var，因此设置好这些变量后，你可以完全移除 `credentials` block：

```bash
GITHUB_APP_ID=...            # GitHub App id
GITHUB_APP_PRIVATE_KEY=...   # GitHub App private key (PEM)
GITHUB_WEBHOOK_SECRET=...    # verifies the webhook signature
GITHUB_APP_SLUG=...          # supplies botName when it is not set in config
```

如果你希望按需获取，`appId`/`privateKey`/`webhookSecret` 也接受 lazy resolver function。

把 GitHub App webhook URL 指向 `https://<deployment>/eve/v1/github`。对于 mention-driven turns，请订阅 `issue_comment` 和 `pull_request_review_comment`；如果你接入它们的 opt-in hooks，再添加 `issues` / `pull_request`。`@mention` `botName` 的 comment 会启动 turn。

## channel 如何处理 messages

### Dispatch

Inbound hooks 返回 `{ auth }` 表示 dispatch，或返回 `null` 表示忽略。使用 `defaultGitHubAuth(ctx)` 从 actor 派生 auth。

```ts
import { defaultGitHubAuth, githubChannel } from "eve/channels/github";

export default githubChannel({
  botName: "my-agent",
  // Replaces the @mention gate. ctx.conversation.kind is "issue", "pull_request", or "review_thread".
  onComment: (ctx, comment) => ({ auth: defaultGitHubAuth(ctx) }),
  // Opt in; no default dispatch on these events.
  onIssue: (ctx, issue) => (issue.action === "opened" ? { auth: defaultGitHubAuth(ctx) } : null),
  onPullRequest: (ctx, pr) => (pr.action === "opened" ? { auth: defaultGitHubAuth(ctx) } : null),
});
```

### Delivery

turn 启动时，channel 会给触发 comment 添加 `eyes` reaction（可用 `progress: { reactions: false }` 关闭）。reply 会作为 comment 返回到 timeline 或 review thread，过长时会拆分成多条 comments。如果 turn 失败，你会得到一条携带 error id 的短 error comment。

### Human-in-the-loop (HITL)

GitHub comments 没有 interactive button 或 card affordance。human-in-the-loop（HITL）`input.requested` event 会作为 comment prompt 发布，用户的 reply comment 会映射回 pending input request。声明 `events["input.requested"]` handler 可以 customize prompt。

### Proactive sessions

可以从 schedule `run` handler 中通过 `receive(github, { message, target, auth })`，或从另一个 channel 中通过 `args.receive(github, ...)`，在没有 inbound mention 的情况下启动 session。target 需要 `owner`、`repo`，以及 `issueNumber` 或 `pullRequestNumber` 中恰好一个。

### Attachments

此 channel 目前不支持 inbound file attachments。Repository contents 会通过下面的 sandbox checkout 到达 agent，而不是作为 message attachments。

### PR context

在 PR 上召唤 agent 时，它总能看到 diff。PR metadata 和 changed-file patch 会进入 `context`。大型 generated files 仍会出现在列表中，但其 patch body 会被 drop；可以用 `pullRequestContext.excludedFiles` 向 skip list 添加更多路径。

### Sandbox checkout

在第一次 model call 前，每个被触发的 turn 都会把相关 ref checkout 到 sandbox 中，因此 `read_file`/`glob`/`grep`/`bash` 都会基于真实 tree 运行。installation token 永远不会进入 sandbox。`git` fetch 的是 token-free URL，platform 会在 firewall 处为 egress 注入 auth。这需要 firewall-capable backend（Vercel）；local backend 会跳过 checkout。在一个 session 内，checkout 会跨 turns 增量进行。

### Arbitrary API calls

对于 channel 未包装的任何内容，调用 `ctx.github.request({ method, path, body })`。它会携带 installation-token auth。

## 接下来阅读

- [Channels overview](./overview)：channel contract 和每个 built-in channel
- [Auth & route protection](../guides/auth-and-route-protection)：authenticating inbound traffic
