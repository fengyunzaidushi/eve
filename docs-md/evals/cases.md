---
title: "Cases"
description: "使用 test(t) 编写 single-turn 和 multi-turn evals，并把一个文件 fan out 到 dataset。"
---

默认情况下，每个 eval file 是一个 graded case；单个文件也可以通过 default-export array fan out 到 dataset（下文介绍）。runner 会针对 target 执行每个 `test(t)` function，捕获每个 event，并根据你记录的 [assertions](./assertions) 计算 verdict。无论是 single-turn、multi-turn、human-in-the-loop（HITL）还是 dataset-driven，每个 eval 都共享同一形状：一个驱动 agent 并 inline assert 的 `async test(t)` function。

## Single-turn evals

常见情况是发送一个 turn 并对 reply 做 assert。`t.send(input)` 会在 turn settle 后 resolve，`t.reply` 是最后一条 assistant message：

```ts title="evals/weather/brooklyn-forecast.eval.ts"
import { defineEval } from "eve/evals";
import { includes } from "eve/evals/expect";

export default defineEval({
  async test(t) {
    await t.send("What is the weather in Brooklyn?");
    t.completed();
    t.check(t.reply, includes("Sunny"));
  },
});
```

有些 evals 只关心行为，而不关心文本。可以对 run 做 assert，并完全跳过 content check：

```ts title="evals/weather/no-tools-for-greetings.eval.ts"
import { defineEval } from "eve/evals";

export default defineEval({
  async test(t) {
    await t.send("Hello!");
    t.completed();
    t.notCalledTool("get_weather");
  },
});
```

## 使用目录组织

Identity 是文件路径，因此目录就是分组机制。`evals/weather/brooklyn-forecast.eval.ts` 的 id 是 `weather/brooklyn-forecast`，`eve eval weather` 会运行 `evals/weather/` 下的所有内容。Shared constants 和 helpers 放在 sibling non-eval files 中（任何不以 `.eval.ts` 结尾的名称）：

```text
evals/
├── weather/
│   ├── shared.ts                    # helpers, not an eval
│   ├── brooklyn-forecast.eval.ts
│   └── no-tools-for-greetings.eval.ts
└── smoke.eval.ts
```

## Multi-turn evals

按顺序驱动多个 turns，可用于 branching、HITL approvals、structured output、attachments 或 multiple sessions。由于 assertions 位于 function 内，intermediate value 就是 local variable。可以在下一个 turn 覆盖 draft 前评估它，然后继续。

```ts title="evals/draft-then-send.eval.ts"
import { defineEval } from "eve/evals";
import { includes } from "eve/evals/expect";

export default defineEval({
  async test(t) {
    const draft = await t.send("Draft the follow-up email.");
    t.check(draft.message, includes("Best regards"));
    t.judge.autoevals.closedQA("professional tone", { on: draft.message }).atLeast(0.6);

    await t.send("Now send it.");
    t.calledTool("send_email");
  },
});
```

对于 built-in assertion 无法表达的 precondition，请 `throw`。抛出的 error 会把 eval 标记为 `failed`，并在 result 中包含 message：

```ts title="evals/session-continuity.eval.ts"
import { defineEval } from "eve/evals";
import { includes } from "eve/evals/expect";

export default defineEval({
  async test(t) {
    await t.send("My favorite word is marigold.");
    const firstSessionId = t.sessionId;

    const second = await t.send("Thanks for remembering.");
    second.expectOk();
    if (t.sessionId !== firstSessionId) {
      throw new Error(`Expected one session; got ${firstSessionId} then ${t.sessionId}.`);
    }

    t.completed();
    t.check(second.message, includes("Thanks for remembering."));
  },
});
```

## Drive API

`t` 驱动 primary session；`t.newSession()` 会返回面向同一 target 的独立 `EveEvalSession`，其 events 会进入同一组 run-level assertions。

- `t.send(input)` 发送 turn 并等待它 settle。它接受与 `ClientSession.send()` 相同的 input（string 或 structured message），并 resolve 为携带 `.message` 和 `.expectOk()` 的 turn。
- `t.sendFile(text, path, mediaType?)` 将 local file 作为 data URL 附加。
- `t.expectInputRequests(filter?)` assert 前一个 turn park 在 HITL input 上，并返回 pending requests。
- `t.respond(...responses)` 回答特定 pending input requests，并把它们作为下一个 turn 发送。
- `t.respondAll(optionId)` 用同一个 option 回答每个 pending input request，并把 responses 作为下一个 turn 发送。
- `t.reply` 是最后一条 assistant message（或 `null`）；`t.sessionId` 是当前 session id；`t.events` 是截至目前捕获的完整 typed event stream。

每个 `send`（以及 `respond`/`respondAll`）都会 resolve 为一个 turn，其 `expectOk()` 只在 turn 以失败结束时 throw。为下一条 message 保持 open 的 session，是 successful turn 的正常 end state。

每个 session 的 events 都会捕获到 result 和 artifacts 中。`t.log(message)` 会把 debug lines 记录进 eval artifact；`--verbose` 还会在 evals 运行时把它们 stream 到 stdout。`t.signal` 是一个会在 timeout 时触发的 `AbortSignal`。

对于由 channel webhook 或 schedule 在 eval 外创建的 sessions，如何驱动它们见 [Targets](./targets)。

## Datasets：导出 array

若要把一个文件 fan out 到 dataset，请 default-export 一个由 `defineEval(...)` values 组成的 array。Eval modules 是 ESM，因此 top-level `await` 可以加载任何内容。Ids 派生自文件名加上按 array 顺序补零的 index（`sql/0000`、`sql/0001` 等）。loaders（来自 `eve/evals/loaders` 的 `loadJson`、`loadYaml`）会相对于 app root 解析 fixture files：

```ts title="evals/sql.eval.ts"
import { defineEval } from "eve/evals";
import { loadYaml } from "eve/evals/loaders";
import { equals } from "eve/evals/expect";

const doc = await loadYaml("evals/data/cases.yaml");
const rows = doc.evals as readonly { task: string; prompt: string; sql: string }[];

export default rows.map((row) =>
  defineEval({
    description: row.task,
    async test(t) {
      await t.send(row.prompt);
      t.completed();
      t.check(t.reply, equals(row.sql));
    },
  }),
);
```

loaders 用于 fixtures，而不是 runtime agent code。

## 接下来阅读

- [Assertions](./assertions)：对 eval 做了什么进行 assert
- [Judge](./judge)：用 LLM judge 评估质量
- [TypeScript client](../guides/client/messages)：eval sessions 构建其上的 send/turn protocol
