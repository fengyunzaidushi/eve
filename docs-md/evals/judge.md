---
title: "Judge"
description: "通过 t.judge.autoevals 使用 LLM judge 评估 evals，在 assertion 上设置 thresholds，并配置 judge model。"
---

当没有 deterministic [assertion](./assertions) 能捕获“好”的含义（factual correctness、summary quality、free-form criteria）时，请用 LLM judge 评估 run。`t.judge.*` assertions 是唯一 model-backed assertions，它们使用与被测 agent 分开解析的 judge model。eve 只用它评分，永远不会用它替换 agent。

```ts
import { defineEval } from "eve/evals";

export default defineEval({
  async test(t) {
    await t.send("Explain quantum tunneling to a 10-year-old.");
    t.completed();
    t.judge.autoevals.closedQA("uses no math beyond arithmetic").atLeast(0.8);
  },
});
```

## Graders

judges 位于 `t.judge.autoevals` 下。该 namespace 命名的是 [Braintrust autoevals](https://github.com/braintrustdata/autoevals) grader family，因此 factuality 和 closedQA semantics 来自 autoevals，而不是 eve 自创。每个 grader 默认评分 `t.reply`，且默认是 soft（tracked，无 gate）：

| Grader                                   | Grades                                                                   |
| ---------------------------------------- | ------------------------------------------------------------------------ |
| `t.judge.autoevals.factuality(expected)` | reply 与 expected answer 的 factual consistency（A–E buckets）           |
| `t.judge.autoevals.summarizes(expected)` | reply 对 expected text 的 summarize 程度                                 |
| `t.judge.autoevals.closedQA(criteria)`   | reply 是否满足 free-form yes/no criterion（没有 expected answer 可匹配） |
| `t.judge.autoevals.sql(expected)`        | 两个 SQL statements 的 semantic equivalence                              |

reference 或 criteria 是位置参数。后面可以跟 options object：

- `on` 是要评分的 value，默认是 `t.reply`。可以传入 intermediate draft 或 parsed value 来改为评分它。
- `model` 和 `modelOptions` 是 per-call judge override（见下文）。

```ts
const draft = await t.send("Draft the welcome email.");
t.judge.autoevals.closedQA("professional tone", { on: draft.message }).atLeast(0.6);
```

## Soft scoring 和 thresholds

Judge assertions 是 soft，因此 threshold 位于 assertion handle 上。没有单独的 thresholds map：

- **No threshold** 仅 tracking。score 会进入 reports 和 artifacts，永远不会让 eval 失败。用它观察 metric，而不 gate。
- `.atLeast(threshold)` 是 soft bar。below-threshold score 会把 eval 标记为 `scored`，只在 `eve eval --strict` 下 fatal。
- `.gate(threshold)` 会把 judge 提升为 hard gate，直接让 eval 失败。

```ts
t.judge.autoevals.closedQA("cites a source"); // tracked, never fails
t.judge.autoevals.closedQA("cites a source").atLeast(0.6); // soft, fails under --strict below 0.6
t.judge.autoevals.factuality(reference).gate(0.8); // hard gate at 0.8
```

judge 每个 assertion 运行一次并消耗 tokens，因此只有在 deterministic 方法无法胜任时才使用。一个 eval 中多个慢 judge calls 可以用 `await Promise.all([...])` fan out。

## 配置 judge model

judge model 会在 runner 构建 `t` 时解析一次。它 **永远不是** 被测 model。三层解析遵循 innermost-wins：

1. **Per-call**：`t.judge.autoevals.closedQA("…", { model, modelOptions })`。
2. **Per-eval**：`defineEval({ judge: { model, modelOptions }, test })`。
3. **Project default**：`evals.config.ts` 中的 `defineEvalConfig({ judge: { model, modelOptions } })`。

```ts title="evals/evals.config.ts"
import { defineEvalConfig } from "eve/evals";

export default defineEvalConfig({
  judge: { model: "openai/gpt-5.4-mini" }, // the default judge for every eval in this tree
});
```

```ts title="evals/quantum.eval.ts"
import { defineEval } from "eve/evals";

export default defineEval({
  judge: { model: "anthropic/claude-opus-4.8" }, // a stronger judge for this eval
  async test(t) {
    await t.send("Explain quantum tunneling to a 10-year-old.");
    t.judge.autoevals.factuality(reference).atLeast(0.7);
    t.judge.autoevals.closedQA("is concise", { model: "anthropic/claude-haiku-4.5" }); // cheaper, per-call
  },
});
```

`evals.config.ts` 中的 `judge` 是可选的，完全 deterministic 的 eval tree 可以省略它。在没有解析到 judge model 时调用 `t.judge.*` 会记录 failed gate：runner 会在 `test` function 运行后评分 assertion，缺失 model 会 throw，eval 会带着该 message 失败。

**string model id**（例如 `"anthropic/claude-opus-4.8"`）会通过 Vercel AI Gateway 路由，并需要 environment 中有 `AI_GATEWAY_API_KEY` 或 `VERCEL_OIDC_TOKEN`。**AI SDK `LanguageModel` instance** 会被直接使用。配置了 model 但没有 credentials 时，judge-backed eval 会 **可见地 skip**，而不是失败，因此 run 会报告 skip，而不是虚假 error。provider-specific judge settings 请使用 `modelOptions.providerOptions`。

## 接下来阅读

- [Assertions](./assertions)：deterministic run-level 和 value assertions
- [Reporters](./reporters)：把 judged scores 发送到 Braintrust experiments
- [Targets](./targets)：judge-backed evals 的 local vs remote targets
