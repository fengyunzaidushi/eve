---
title: "概览"
description: "使用 defineEval 为 eve agent 定义可重复的 scored checks，并用 eve eval 运行它们。"
---

eval 是 scored check，会让你的 agent 基于真实 sessions 运行并评估结果，用来在你修改 prompt 或 tool 时捕获 regressions。你可以驱动 agent 经过一个或多个 turns，对它做了什么进行 assert（run 已完成、正确 tool 已运行、reply 包含正确文本），并可选择把结果发送到 Braintrust。

Evals 会 exercise 用户访问的同一 HTTP surface。runner 会启动（或指向）真实 agent server，通过 [TypeScript client](../guides/client/overview) protocol 驱动 sessions，并评估返回内容，因此通过的 eval 意味着 agent 已启动、接受了 request，并产生了你 assert 的结果。

## `defineEval`

eve 会在 app-root `evals/` 目录下发现 `.eval.ts` 文件中的 evals。默认情况下，每个文件是一个 eval。文件也可以 default-export 一个 array，用于 fan out 到 dataset（见 [Cases](./cases)）。文件路径就是 eval 的 identity，因此你不需要编写 `id` 或 `name`。目录用于分组相关 evals（`evals/weather/brooklyn-forecast.eval.ts` 的 id 会变成 `weather/brooklyn-forecast`）。

```text
my-agent/
├── agent/
├── evals/
│   ├── evals.config.ts
│   ├── smoke.eval.ts
│   └── weather/
│       ├── brooklyn-forecast.eval.ts
│       └── no-tools-for-greetings.eval.ts
└── package.json
```

eval 是单个 `async test(t)` function。你用 `t` 驱动 agent，并用同一个 `t` 对 run 做 assert：

```ts title="evals/weather/brooklyn-forecast.eval.ts"
import { defineEval } from "eve/evals";
import { includes } from "eve/evals/expect";

export default defineEval({
  description: "Basic message and tool-usage coverage for the weather agent.",
  async test(t) {
    await t.send("What is the weather in Brooklyn?");
    t.completed();
    t.calledTool("get_weather");
    t.check(t.reply, includes("Sunny"));
  },
});
```

`test` 是唯一必填字段。其他字段都是可选的：`description`、`judge`、`tags`、`metadata`、`timeoutMs` 和 `reporters`。init template 会把 `evals/**/*.ts` 添加到 `tsconfig.json`，因此你的 eval code 会与 app 一起 type-check。

## `evals.config.ts`

每个 `evals/` 目录都需要在其 root 下有且仅有一个 `evals.config.ts`。它声明所有 eval 共享的 defaults：

```ts title="evals/evals.config.ts"
import { defineEvalConfig } from "eve/evals";
import { Braintrust } from "eve/evals/reporters";

export default defineEvalConfig({
  judge: { model: "openai/gpt-5.4-mini" },
  reporters: [Braintrust({ projectName: "my-agent" })],
});
```

所有内容都是可选的。`judge` 为 [LLM-as-judge](./judge) assertions（`t.judge.*`）设置默认 model；完全 deterministic 的 eval tree 可以省略它。`reporters`、`maxConcurrency` 和 `timeoutMs` 补充 defaults。Config `reporters` 会观察 run 中的每个 eval，因此请在这里设置一个 `Braintrust()`，而不是添加到每个 eval。CLI flags（`--max-concurrency`、`--timeout`）和 per-eval values 优先于 config defaults。

## `t` context

`t` 既是 driver，也是 assertion surface。没有单独的 `input`、`run`、`checks` 或 `scores` 字段。你编写普通 control flow，发送 turns，并 inline assert。

- **Drive** agent：`t.send(...)`、`t.respond(...)`、`t.respondAll(...)`、`t.sendFile(...)`、`t.expectInputRequests(...)`、`t.newSession()`。用 `t.reply`（最后一条 assistant message）、`t.sessionId` 和 `t.events` 读取返回内容。见 [Cases](./cases)。
- **Assert** 使用三个 surfaces，见下文。

## 三个 assertion surfaces

每个 surface 对应真正不同的 judgment 类型：

- **Run-level methods** 读取整个 run，例如 `t.completed()`、`t.calledTool("get_weather")`、`t.usedNoTools()` 和 `t.toolOrder([...])`。它们不接受 value，因为它们观察 run 本身。见 [Assertions](./assertions)。
- **`t.check(value, assertion)`** 用来自 `eve/evals/expect` 的 deterministic builder 评估显式 value，例如 `t.check(t.reply, includes("sunny"))`。可以评估 `t.reply`、intermediate draft、parsed JSON 或任何其他内容。见 [Assertions](./assertions)。
- **`t.judge.autoevals.*`** 是 LLM-as-judge surface，例如 `t.judge.autoevals.closedQA("cites a source")`。它默认评估 `t.reply`，使用配置的 judge model，永远不会使用被测 agent。见 [Judge](./judge)。

## Gate vs soft

每个 assertion 都返回 chainable handle，因此 severity 位于 assertion 本身上。没有单独的 thresholds map。

- **Gates** 是硬门槛。失败的 gate 会把 eval 标记为 `failed`，并让 `eve eval` 以非零状态退出。Run-level methods、`includes`、`equals` 和 `matches` 默认是 gates。
- **Soft** assertions 是 tracked data。它们会进入 reports 和 artifacts，低于 threshold 的 soft assertion 会把 eval 标记为 `scored`（可见但不 fatal，除非传入 `--strict`）。`similarity` 和每个 `t.judge.*` assertion 默认都是 soft。没有 threshold 的 soft assertion 只会 tracking，永远不会失败。

可以按 assertion 覆盖：`.gate(threshold?)` 提升为 hard gate，`.soft(threshold?)` 降级为 tracked，`.atLeast(threshold)` 是带 bar 的 soft assertion。

```ts
t.completed(); // gate
t.calledTool("get_weather").soft(); // record as a metric, don't gate
t.judge.autoevals.closedQA("cites a source"); // soft, tracked (no threshold)
t.judge.autoevals.factuality(reference).atLeast(0.7); // soft, gated under --strict at 0.7
```

## 使用 eve eval 运行 evals

```bash
eve eval                       # run all discovered evals against a local dev server
eve eval weather               # run one eval, or every eval under evals/weather/
eve eval --url https://<app>   # target an existing server or deployment
```

exit code `0` 表示每个 eval 都通过了 gates。完整 flag list、exit codes 和 CI guidance 见 [Running evals](./running)。

## 良好的 baseline

大多数 apps 用少量 small smoke evals 就足够。用 `t.completed()` 加一两个 content checks assert 行为，把 dataset fixtures 放在 `evals/data/` 中，只有在需要 fuzzy grading 或 shared result review 时才使用 judge 或 Braintrust。在 CI 中运行 `eve eval --strict`，这样 soft threshold misses 也会让 build 失败。

## 接下来阅读

本节其余页面覆盖各个部分：

- [Cases](./cases)：single-turn evals、scripted multi-turn evals 和 dataset fan-out
- [Assertions](./assertions)：run-level methods 和 `t.check` value assertions，包括 matchers 和 severity
- [Judge](./judge)：LLM-as-judge grading 和 judge model
- [Targets](./targets)：同一组 eval files 的 local vs remote targets
- [Reporters](./reporters)：Braintrust experiments 和 JUnit XML
- [Running evals](./running)：`eve eval` CLI、exit codes 和 artifacts
- [Tools](../tools)：大多数 evals assert 的 surface
