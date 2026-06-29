---
title: "Schedules"
description: "按 cron cadence 运行 agent，可以是 fire-and-forget prompt，也可以是把工作交给 channel 的 handler。"
---

schedule 会按自己的时钟启动 agent，而不是等待 inbound message。它适合 daily digests、data syncs、cleanup sweeps、heartbeats，或任何应按 cadence 触发的工作。每个 schedule 都是 `agent/schedules/` 下携带 cron expression 的单个文件。Schedules 仅限 root，因此 declared subagents 不能有 `schedules/` 目录。

名称来自 `schedules/` 下的路径（`agent/schedules/billing/sweep.ts` → `"billing/sweep"`），可以使用 nested directories。

## `defineSchedule`

每个 schedule 都提供一个 `cron`，并且在 `markdown` 和 `run` 中恰好提供一个：

```ts
interface ScheduleDefinition {
  cron: string;
  markdown?: string; // fire-and-forget prompt (task mode)
  run?: (args: ScheduleHandlerArgs) => Promise<void> | void; // handler
}

interface ScheduleHandlerArgs {
  receive: CrossChannelReceiveFn; // hand the work off to a channel
  waitUntil: (task: Promise<unknown>) => void; // keep the cron task alive past return
  appAuth: SessionAuthContext; // pre-built app principal
}
```

`defineSchedule` 是 type-level pass-through。one-of 规则由 compiler 强制执行。

`cron` 是标准 5 字段字符串（`minute hour day-of-month month day-of-week`），粒度为分钟。在 Vercel 上，每个 schedule 都会成为 Vercel Cron Job，Vercel 会以 UTC 求值表达式，因此 `"0 9 * * 1-5"` 会在工作日 09:00 UTC 触发。`eve dev` 永远不会按 cron cadence 触发 schedules。通过 `eve start` 提供服务的 built app 会运行 production scheduled tasks。若要在 dev 迭代时触发一次，请使用下面的 dispatch route。

## Markdown form（fire-and-forget）

这是最小 schedule。eve 会基于 prompt 运行 agent 并丢弃 output，但 agent 仍可在过程中调用 tools、写入 backends 并记录日志。我们称之为 task mode。task-mode session 会运行到完成或失败，不能 park 以等待人员或 OAuth sign-in。

```ts title="agent/schedules/heartbeat.ts"
import { defineSchedule } from "eve/schedules";

export default defineSchedule({
  cron: "*/5 * * * *",
  markdown: "Pull open Linear issues and POST a summary to the metrics endpoint.",
});
```

你也可以把同样内容写成 plain `.md` 文件：其 frontmatter 只接受 `cron`，body 是 prompt。

`agent/schedules/cleanup.md`:

```md
---
cron: "0 0 * * 0"
---

Sweep stale workflow state.
```

## Handler form（`run`）

当 schedule 需要 deliver 到 channel、根据条件分支，或在 fire time 计算参数时，请使用 handler。handler 拥有完全控制权。它没有自己的 channel，因此会用 `receive` 把工作传给某个 channel。

```ts title="agent/schedules/daily-digest.ts"
import { defineSchedule } from "eve/schedules";

import slack from "../channels/slack.js";

export default defineSchedule({
  cron: "0 9 * * 1-5",
  async run({ receive, waitUntil, appAuth }) {
    waitUntil(
      receive(slack, {
        message: "Summarize yesterday's activity and post the digest.",
        target: { channelId: "C0123ABC" },
        auth: appAuth,
      }),
    );
  },
});
```

- `receive(channel, { message, target, auth })`：在另一个 channel 上启动 session。contract 与 route handler 的 `args.receive` 相同。
- `waitUntil(promise)`：延长 cron task 的 lifetime，让 parked session 和任何 in-flight fetches 在 task 结束前 settle。请用它包装 `receive` call。
- `appAuth`：app principal（`{ authenticator: "app", principalId: "eve:app", principalType: "runtime" }`）。对于 agent 代表自身执行的工作，把它作为 `receive(..., { auth: appAuth })` 传入。

handler-form session 与其他 session 运行在同一个 durable runtime engine 上，因此它可以 park（durably suspend），例如当 channel handoff 正在等待 Slack reply 时。只有 markdown task mode 被禁止等待。

## 迭代时触发 schedule

dev server 会挂载一个 one-shot dispatch route，可按名称 out of band 触发一次 schedule。由于 `eve dev` 永远不会按 cron cadence 运行 schedules，这就是无需等待下一个 production tick 即可触发它的方式。

```sh
curl -X POST http://localhost:3000/eve/v1/dev/schedules/heartbeat
# -> { "scheduleId": "heartbeat", "sessionIds": ["..."] }
```

`:scheduleId` 是 path-derived schedule name（`agent/schedules/heartbeat.ts` → `heartbeat`；nested names 中的 `/` 需要 URL-encode）。它会运行 production cron handler 使用的同一 dispatch path，并以 JSON 返回启动的 session ids，因此你可以在 `GET /eve/v1/session/:sessionId/stream` 订阅每个 session 的 [stream](./concepts/sessions-runs-and-streaming)。未知 id 会返回 `404`，并带有 `availableScheduleIds`，列出 app 实际定义的 schedules。

该 route 仅限 dev。Production builds 永远不会挂载它；由于 dev server 仅限本地，它不需要 auth。

## 在 Vercel 上

Hosted Vercel builds 会把每个 `defineSchedule(...)` 转成 Vercel Cron Job，并把每个 `cron` 写成 `.vercel/output/config.json` 中的 entry。Vercel 会以 UTC 求值这些表达式。请在 **Settings → Cron Jobs** 下确认 discovery，并在 **Observability → Cron Jobs** 下查看 execution history。Per-run logs 位于 **Observability → Logs** 下。

## Self-deployed hosts

Production builds 会把 schedules 注册为 Nitro scheduled tasks。在 Vercel 上，Nitro 的 Vercel preset 会为你把这些 task registrations 接入 Vercel Cron。在 Vercel 之外，标准 `eve build && eve start` 路径会提供 Nitro 的 Node output，并启动 Nitro 的 schedule runner，因此只要该 process 运行，tasks 就会按 cron cadence 触发。

需要注意 custom hosting。如果你把 generated output 适配到只提供 HTTP、但不启动 Nitro scheduled task runner 的 process manager、container platform 或 Nitro preset，schedule definitions 仍会 compile，但不会自动触发。在这种情况下，请通过 `eve start` 运行 eve，使用支持 Nitro scheduled tasks 的 host，或通过 authenticated route、channel handoff 或 application-specific job runner 从你自己的 scheduler 触发同样的工作。上面的 dev dispatch route 仅用于 `eve dev`；production builds 不会挂载它。

## 接下来阅读

- [Channels](./channels/overview)：把 schedule output deliver 给 users。
- [Sessions, runs & streaming](./concepts/sessions-runs-and-streaming)：inspect schedule run。
