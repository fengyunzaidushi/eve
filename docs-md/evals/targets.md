---
title: "Targets"
description: "用同一组 eval files 指向 local dev server 或 deployment。"
---

eval target 始终是 HTTP URL。`eve eval` 会启动 local dev server，而 `eve eval --url <url>` 会针对已有 server 或 deployment 运行。同一组 eval files 可用于两者，这让 evals 可以作为 CI 中的 end-to-end tests。

runner 会 poll `/eve/v1/health`，验证 `/eve/v1/info`，并在 `test` function 内把 live target 暴露为 `t.target`。

## Target helpers

```ts title="evals/heartbeat.eval.ts"
import { defineEval } from "eve/evals";

export default defineEval({
  async test(t) {
    const { sessionIds } = await t.target.dispatchSchedule("heartbeat");
    await t.target.attachSession(sessionIds[0]!);
    t.completed();
    t.calledTool("send_report");
  },
});
```

- `t.target.fetch(path, init)` 对 target 执行 authenticated fetch，适合 channel 和 webhook ingress。runner 如何认证见 [Authentication](#authentication)。
- `t.target.dispatchSchedule(id)` 通过 dev-only schedule route 触发 [schedule](../schedules)，并返回它创建的 session ids。它只适用于启用了 dev routes 的 target（local `eve eval` dev server，或以 development mode 运行的 deployment），否则会 throw。
- `t.target.attachSession(sessionId, { startIndex? })` 消费由 channel 或 schedule 在 eval 外创建的 session 中的一个 turn，使其 events 进入 run-level assertions。`startIndex` 会跳过该位置之前的 events，因此已经进行到 stream 中途的 session 会从你离开的地方恢复，而不是从头 replay。

以这种方式 attached 的 sessions 是完整的 `EveEvalSession`s：你可以继续用 `send` 驱动它们并读取 event streams。`t` 上的 run-level assertions（`t.completed()`、`t.calledTool(...)`）会读取整个 run，包括 attached sessions。

## Authentication

Local targets 不发送 auth：`eve eval` 拥有它启动的 dev server。remote `--url` target 会使用与其他 development client 相同的 credentials 连接，按以下顺序解析：

- Vercel OIDC trusted-IDP token，作为 per-request header 发送。它无需 per-project secret 即可绕过 Deployment Protection，因此带有 pulled OIDC token 的 CI job 可以无需额外设置访问受保护的 preview deployment。
- 设置 `VERCEL_AUTOMATION_BYPASS_SECRET` 时添加的 `x-vercel-protection-bypass` header。
- 从同一 OIDC cascade 解析的 bearer token。
- `EVE_EVAL_AUTH_TOKEN`，用于以 static token 覆盖 bearer，适用于 auth 不是 OIDC-based 的 targets。

`t.target.fetch(path, init)` 会携带这些相同 credentials，因此通过它 exercise 的 channel 和 webhook ingress 会以与 session protocol 相同的方式认证。

## 接下来阅读

- [Running evals](./running)：实践中的 `--url` 和其他 CLI
- [Schedules](../schedules)：`dispatchSchedule` 驱动的 surface
- [Channels](../channels/overview)：可用 `target.fetch` exercise 的 ingress
