---
title: "Team Playbooks"
description: "Build an Agent 教程第 7 部分。使用按 principal keyed 的 dynamic skill 加载调用者的 team playbook。"
---

[Step 6](./remember-definitions) 中的 glossary 是 per-session 的。但你的团队会为 analytics assistant 准备长期 analysis conventions（Growth 以特定方式运行 cohort retention，Finance 有自己的 revenue-recognition rules），这些内容不应跨 tenants 泄漏。请为提问者加载正确团队的 playbook。

skill 是 on-demand procedure。只有当某个 turn 需要时，model 才会用 `load_skill` 拉入它。把它做成 dynamic 后，skill 会在 runtime 决定，而不是 baked in。`defineDynamic` resolver 会读取 session 并返回一个 `defineSkill`（或不返回）。这里你会根据 `ctx.session.auth` 中的 caller identity 来决定。

## 每个 principal 一个 playbook

`ctx.session.auth.current` 保存最近的 caller；如果没有，则为 `null`。它的 `attributes` 是 auth layer 打上的 claims，包括 team。读取 team，查找该团队的 playbook，并为它 emit 一个 skill：

```ts title="agent/skills/team-playbook.ts"
import { defineDynamic, defineSkill } from "eve/skills";

const PLAYBOOKS: Record<string, { title: string; markdown: string }> = {
  growth: {
    title: "Growth analysis playbook",
    markdown:
      "When analyzing retention, use weekly cohorts anchored on signup week, " +
      "report curves not point estimates, and exclude trial accounts.",
  },
  finance: {
    title: "Finance analysis playbook",
    markdown:
      "Report revenue net of refunds and recognized over the subscription term. " +
      "Always reconcile against the close-of-month snapshot.",
  },
};

export default defineDynamic({
  events: {
    "session.started": async (_event, ctx) => {
      const team = ctx.session.auth.current?.attributes.team;
      const key = Array.isArray(team) ? team[0] : team;
      const playbook = key ? PLAYBOOKS[key] : undefined;
      if (!playbook) return null;

      return defineSkill({
        description:
          `Use when answering analysis questions for the ${key} team. ` +
          `Contains that team's standing conventions.`,
        markdown: `# ${playbook.title}\n\n${playbook.markdown}`,
      });
    },
  },
});
```

`session.started` 每个 session 触发一次。resolver 会读取一次 team，生成的 skill 会在后续每个 turn 中保持可用。返回 `null` 不会产生 skill，因此没有 team 的 caller 不会获得 playbook。

## 查看路由效果

team 来自 authenticated claims，auth layer 会在 [Step 9](./ship-it) 中打上它们。在那之前，`ctx.session.auth.current` 没有 `team`，因此 resolver 会返回 `null`，不会加载 playbook。若要现在验证路由，请在 local dev 中打上 team。向 `agent/channels/eve.ts` 添加一个位于 `localDev()` 之前的 dev-only entry，并在第 9 步接入真实 auth 前移除它：

```ts title="agent/channels/eve.ts"
import { eveChannel } from "eve/channels/eve";
import { localDev, placeholderAuth, vercelOidc, type AuthFn } from "eve/channels/auth";

// Dev-only: stamp a team so Step 7's playbook resolver has something to read.
// Remove before Step 9.
const devTeam: AuthFn<Request> = () =>
  process.env.NODE_ENV === "production"
    ? null
    : {
        attributes: { team: "growth" },
        authenticator: "dev-team",
        principalId: "dev",
        principalType: "user",
      };

export default eveChannel({
  auth: [devTeam, localDev(), vercelOidc(), placeholderAuth()],
});
```

用 `npm run dev` 重启，并询问 “what's our 8-week retention?”。model 会看到 Growth playbook 匹配，调用 `load_skill`，并把 Growth conventions 应用于该 turn（weekly cohorts、无 trial accounts）。把 `team` 切换为 `"finance"`，重启，同一个问题就会改为路由到 Finance 的 playbook。

因为 team 来自 authenticated claims，而不是 message，所以一个 tenant 无法通过 message content 借用另一个 tenant 的 playbook。

同一个 `defineDynamic` resolver 也会驱动 dynamic tools 和 instructions。完整机制见 [Dynamic capabilities](../guides/dynamic-capabilities)。

→ 下一步：[Guard the spend](./guard-the-spend)

了解更多：[Skills](../skills) · [Dynamic capabilities](../guides/dynamic-capabilities)
