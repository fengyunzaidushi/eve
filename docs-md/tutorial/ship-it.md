---
title: "发布上线"
description: "Build an Agent 教程第 9 部分。用 useEveAgent 为 agent 添加 web dashboard，替换 placeholderAuth，并部署到 Vercel。"
---

analytics assistant 已经能在 TUI 中正常运行。现在把它真正发布出去：作为团队登录使用的 web dashboard，接入真实 auth，并部署到 Vercel。需要接入三部分：React UI、channel 的 auth，以及 deploy 本身。

## 添加 Web Chat app

第 1 步 scaffold 的 agent 没有 web frontend。现在从 `analytics-assistant/` 目录运行 `eve channels add` 来添加一个：

```bash
npx eve channels add web
```

这会添加一个连接到现有 eve channel 的 Next.js app（`next.config.ts`、`app/page.tsx`、`app/_components/`），以及 chat UI components 和它们的 dependencies。随后运行 `npm install` 安装新增 packages。生成的 `next.config.ts` 会用 `withEve` 包装你的 config，自动接入 eve routes：

```ts title="next.config.ts"
import type { NextConfig } from "next";
import { withEve } from "eve/next";

const nextConfig: NextConfig = {};

export default withEve(nextConfig);
```

## 使用 `useEveAgent` 的 dashboard

dashboard 会与 built-in eve HTTP channel（`agent/channels/eve.ts`）通信。在浏览器侧，`useEveAgent` 负责 session creation、streaming 和 HITL。scaffold 会从 `app/_components/agent-chat.tsx` 渲染 chat，并由 `app/page.tsx` 挂载。该 component 对起步来说偏完整，因此请把它的内容替换为这个最小版本：

```tsx title="app/_components/agent-chat.tsx"
"use client";

import { useEveAgent } from "eve/react";

export function AgentChat() {
  const agent = useEveAgent();
  const isBusy = agent.status === "submitted" || agent.status === "streaming";

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        const message = String(data.get("q") ?? "").trim();
        if (message) void agent.send({ message });
      }}
    >
      {agent.data.messages.map((message) => (
        <article key={message.id}>
          <header>{message.role}</header>
          {message.parts.map((part, index) =>
            part.type === "text" ? <p key={index}>{part.text}</p> : null,
          )}
        </article>
      ))}
      <input name="q" disabled={isBusy} placeholder="Ask about the data…" />
      <button type="submit" disabled={isBusy}>
        Ask
      </button>
    </form>
  );
}
```

生成的 `app/page.tsx` 已经导入并渲染这个 `AgentChat` export，因此不需要其他 wiring：

```tsx title="app/page.tsx"
import { AgentChat } from "@/app/_components/agent-chat";

export default function Page() {
  return <AgentChat />;
}
```

`agent.data.messages` 和 `agent.status` 覆盖了大多数 chat UI。该 hook 还会暴露 HITL prompts（来自 [Step 8](./guard-the-spend) 的 spend approval），因此 dashboard 可以渲染 approve/deny controls。完整 API 见 [Frontend](../guides/frontend/overview)。

## 替换 `placeholderAuth`

scaffold 的 channel 随附 `placeholderAuth()`，它会 fail closed。它会拒绝 production traffic，避免 unauthenticated app 意外上线。部署前请把它换成你的 app 的真实 auth。

你的 auth 位于一个 module 中，用于把 request 转换为 user。创建 `agent/lib/auth.ts`，并在这里接入你的真实 provider（cookie session、Auth.js、Clerk）。下面的 stub 会返回固定 user，让页面可以编译并端到端运行：

```ts title="agent/lib/auth.ts"
export interface AppUser {
  id: string;
  team: string;
}

// Replace with your real session/provider lookup.
export async function authenticate(_request: Request): Promise<AppUser | null> {
  return { id: "demo-user", team: "growth" };
}
```

现在让 channel 指向它。替换 `agent/channels/eve.ts` 的内容；第 7 步留下了 dev-only `devTeam` entry 和 `placeholderAuth()`。请把你的 app auth 放在最前，排在 catch-all helpers 之前，这样任何不识别 caller 的 entry 都会 fall through 到下一项：

```ts title="agent/channels/eve.ts"
import { eveChannel } from "eve/channels/eve";
import { localDev, vercelOidc, type AuthFn } from "eve/channels/auth";
import { authenticate } from "../lib/auth.js";

const appAuth: AuthFn<Request> = async (request) => {
  const user = await authenticate(request); // your cookie/session/provider
  if (!user) return null;
  return {
    attributes: { team: user.team }, // the claim Step 7's playbook reads
    principalType: "user",
    principalId: user.id,
    authenticator: "app",
    issuer: "analytics-dashboard",
  };
};

export default eveChannel({
  auth: [appAuth, localDev(), vercelOidc()],
});
```

这个 `team` attribute 正是 [Step 7](./team-playbooks) 中 dynamic playbook 从 `ctx.session.auth` 读取的内容。Identity 在这一处设置，然后从这里流向每个 capability。

## 部署到 Vercel

```bash
vercel deploy
```

在 Vercel 上，web app 保持 public，eve runtime 位于同一 origin 上、处在它后面，sandbox 运行在 Vercel Sandbox 上。你可以不离开 CLI 就 smoke-test deployment：

```bash
npx eve dev https://your-analytics-app.vercel.app
```

这就是完整的 assistant，已经部署并接入 auth。它会查询 warehouse，在 sandbox 中运行 analysis，绘制结果图表，记住团队 definitions，按 team 加载正确 playbook，并在花费前询问。

## 你学到了什么

通过九个步骤，你构建并发布了一个 agent，并在过程中使用了：

- **Tools**：为 model 提供 typed actions（`run_sql`、`chart_series`、`define_metric`）。
- **Connections**：通过 OAuth MCP 访问 warehouse，并由 eve 为你解析 per-user tokens。
- **The sandbox**：在隔离的 `/workspace` 中执行 SQL 之外的计算和制图。
- **State**（`defineState`）：跨 turns 记住团队 glossary。
- **Dynamic skills**（`defineDynamic`）：按 caller 加载正确的 team playbook。
- **Human-in-the-loop** approval（`needsApproval`）：gate 昂贵 queries。
- **Channel auth**：把 request 转换为 authenticated principal。
- **Deployment**：部署到 Vercel，让 runtime 位于你的 web app 后面。

## 后续步骤

- [Connections](../connections)：tool allowlists 和 per-connection approval。
- [Sandbox](../sandbox)：backends、lifecycle 和 network policy。
- [Dynamic capabilities](../guides/dynamic-capabilities)：在同一个示例上实现 schema-derived dynamic tools、read-only analyst subagent 和 model-authored report workflows。
- [Auth and route protection](../guides/auth-and-route-protection)：production auth patterns。

了解更多：[Frontend](../guides/frontend/overview) · [Auth and route protection](../guides/auth-and-route-protection) · [Deployment](../guides/deployment)
