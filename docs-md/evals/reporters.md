---
title: "Reporters"
description: "把 eval results 发送到 Braintrust experiments 或 JUnit XML。eve 自己运行并评分所有内容。"
---

eve 自己运行并评分所有内容；reporters 负责把 results 发送出去。CLI 默认打印 console summary（每个 eval 一行，带 failed assertions 及其 messages），来自 `eve/evals/reporters` 的 reporters 会在此基础上添加 destinations。

你有责任确保任何 observability 或 eval provider 已获准接收导出给它的数据。

Reporters 可在两个位置 attach。在 `evals.config.ts` 中声明它们，可观察 run 中的 **每个** eval；这通常适合一个 Braintrust experiment 这类 shared destination，避免在每个文件中重复 reporter。也可以把它们列在单个 eval 的 `reporters` 上，将 destination scope 到该 eval（或共享同一 instance 的一组 evals）。

## Braintrust

`Braintrust(...)` 会把 eval results 上传到 Braintrust experiments。把一个 instance 放在 config 中，让它覆盖整个 run：

```ts title="evals/evals.config.ts"
import { defineEvalConfig } from "eve/evals";
import { Braintrust } from "eve/evals/reporters";

export default defineEvalConfig({
  judge: { model: "openai/gpt-5.4-mini" },
  reporters: [Braintrust({ projectName: "weather-agent" })],
});
```

只需要为部分 evals 设置 destination？请改为按 eval attach：

```ts title="evals/brooklyn-forecast.eval.ts"
import { defineEval } from "eve/evals";
import { Braintrust } from "eve/evals/reporters";

export default defineEval({
  reporters: [Braintrust({ projectName: "weather-agent" })],
  async test(t) {
    await t.send("What is the weather in Brooklyn?");
    t.completed();
  },
});
```

reporter config 接受可选 `projectName` 和 `experimentName`，以及用于 diff 的 base experiment（按 name 或 id）。Gate assertions 会在 `gate:` prefix 下记录为 binary scores，因此 experiments 可以像 diff soft-score regressions 一样 diff gate regressions。Eval `metadata` 会一并传给 reporters。

reporter instance 会观察引用它的 evals。在多个 evals 之间共享一个 instance（config、`shared.ts` export 或 dataset array 的每个 entry），它们的 results 会落入同一个 experiment。把同一个 config reporter 也列到 eval 上，不会 double-report。

Braintrust 需要在 app 中安装其 SDK，并在 environment 中提供 credentials：安装 `braintrust` package（`npm install braintrust`）并设置 `BRAINTRUST_API_KEY`。传入 `--skip-report` 可以在不发送 results 的情况下运行 eval；这也会抑制 config reporters，适合本地迭代。

## JUnit

`JUnit({ filePath })` 会写入用于 CI annotations 的 JUnit XML。`--junit <path>` CLI flag 可以在不触碰 eval file 的情况下做同样的事，通常更合适，因为 output path 属于 CI，而不是 eval：

```bash
eve eval --strict --junit .eve/junit.xml
```

每个 eval 都会成为一个以 path-derived id 命名的 `<testcase>`；failed gates 和 execution errors 会作为 failure messages 落到匹配的 test case 上，因此 CI 会 inline 展示它们。

## Custom reporters

reporter 实现来自 `eve/evals/reporters` 的 `EvalReporter` interface，并接收与 built-ins 相同的 structured results。runner 会调用三个 lifecycle methods，每个都可以为 remote upload 等 async work 返回 promise：

```ts
interface EvalReporter {
  onRunStart(evaluations: readonly EveEval[], target: EveEvalTarget): void | Promise<void>;
  onEvalComplete(result: EveEvalResult): void | Promise<void>;
  onRunComplete(summary: EveEvalRunSummary): void | Promise<void>;
}
```

`onRunStart` 在任何 eval 运行前触发一次，`onEvalComplete` 在每个 observed eval 完成后触发并携带其 checks、scores 和 verdict，`onRunComplete` 携带 aggregated summary 触发一次。只有当 destination 未被覆盖时才使用 custom reporter。`.eve/evals/` 下的 per-run artifacts 已经捕获了 ad-hoc inspection 所需的全部内容。

## 接下来阅读

- [Running evals](./running)：console output、`--json` 和 artifacts
- [Judge](./judge)：reported numbers 的含义
