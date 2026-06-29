---
title: "Assertions"
description: "Run-level methods、t.check value assertions、matcher mini-language，以及 gate vs soft severity。"
---

Assertions 是 eval 评估其 `test(t)` function 产物的方式。每个 assertion 都会把结果 **record** 到 `t` 上，并返回 chainable handle。runner 会读取记录的结果来计算 verdict，因此单次 run 会报告每个 failing assertion，而不是在第一个失败处中止。有两个 deterministic surfaces：`t` 上的 run-level methods，以及用于评估特定 value 的 `t.check`。model-graded assertions 见 [Judge](./judge)。

## Run-level assertions

Run-level assertions 读取整个 run，因此不接受 value。它们是 `t` 上的方法，默认 gate。有几个 assertion 基于 run 是否 **parked**：暂停在未回答的 human-in-the-loop（HITL）input request 上，等待 approval 或 answer 后才能继续。

| Assertion                                           | 断言内容                                                                             |
| --------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `t.completed()`                                     | run 未失败，且未 park 在未回答的 HITL input 上                                       |
| `t.didNotFail()`                                    | 没有 terminal failure，也没有 `turn.failed`/`step.failed` events（parked runs 通过） |
| `t.waiting()`                                       | run park 在 HITL input 上（用于 approval-shaped evals）                              |
| `t.messageIncludes(token)`                          | joined assistant text 包含 `token`（string 或 RegExp）                               |
| `t.outputEquals(value)` / `t.outputMatches(schema)` | 对 agent structured output 做 deep equality 或 Standard Schema（例如 Zod）validation |
| `t.calledTool(name, opts?)`                         | 发生了匹配的 tool call（`input`、`output`、`isError`、`times` constraints）          |
| `t.notCalledTool(name)`                             | 没有对 `name` 的 call                                                                |
| `t.toolOrder([...names])`                           | Tool names 按顺序出现（其他 calls 可以穿插）                                         |
| `t.usedNoTools()`                                   | 完全没有 tool calls                                                                  |
| `t.maxToolCalls(n)`                                 | 最多 `n` 次 tool calls                                                               |
| `t.noFailedActions()`                               | 没有 tool、subagent 或 skill action 报告 failure                                     |
| `t.calledSubagent(name, opts?)`                     | 发生了 subagent delegation（`remoteUrl`、`output` constraints）                      |
| `t.event(predicate, label)`                         | Escape hatch：对 typed event stream 的任意 predicate                                 |

`t.completed()` 包含 `t.didNotFail()` 的含义，因此除非你明确想允许 parked run，否则使用 `completed`。`t.outputEquals` 和 `t.outputMatches` 读取的 structured output 是 agent 的 structured output（见 [output schema guide](../guides/client/output-schema)）。

```ts
await t.send("What is the weather in Brooklyn?");
t.completed();
t.calledTool("get_weather");
```

`t.calledTool` 和 `t.usedNoTools` 互斥；在同一个 run 中只能 assert 其中一个，不能两者都用。

## Value assertions with `t.check`

`t.check(value, assertion)` 会用来自 `eve/evals/expect` 的 builder 评估显式 value。value 可以是 `t.reply`、某个 turn 的 `.message`、parsed JSON，或你计算出的任何 local：

```ts
import { includes, equals, matches, similarity } from "eve/evals/expect";

t.check(t.reply, includes("sunny")); // substring (gate)
t.check(parsed, equals({ city: "Brooklyn" })); // deep structural equality (gate)
t.check(parsed, matches(WeatherSchema)); // Standard Schema, e.g. Zod (gate)
t.check(t.reply, similarity("Sunny, 72F")); // fuzzy 0–1 Levenshtein (soft)
```

| Builder                | 评分内容                                      | Default |
| ---------------------- | --------------------------------------------- | ------- |
| `includes(substring)`  | value（coerced to string）包含 `substring`    | gate    |
| `equals(value)`        | deep structural equality                      | gate    |
| `matches(schema)`      | 根据 Standard Schema validation               | gate    |
| `similarity(expected)` | normalized Levenshtein similarity，1 表示相同 | soft    |

选择能捕获“正确”含义的最便宜 builder。当 exact match 过于严格，而 judge model 又过重时，`similarity` 是折中方案。对于更细腻的 grading，请使用 [judge](./judge)。

## matcher mini-language

`t.calledTool` 和 `t.calledSubagent` 接受 matcher object：tools 使用 `{ input, output, isError, times }`，subagents 使用 `{ remoteUrl, output }`。每个字段都接受 literal（objects 会 partial-deep-match）、RegExp 或 function。matcher function 会收到 value，并返回 boolean（作为 predicate）或用于比较的 expected value（适合 environment-provided URLs 等 runner-assigned values）：

```ts
t.calledTool("bash", { input: { command: /^pwd/ }, isError: false, times: 1 });

t.calledTool("echo", { output: (value) => String(value).includes(marker) });

t.calledSubagent("weather", {
  remoteUrl: () => process.env.WEATHER_AGENT_URL!,
  output: /72F/,
});
```

## Run state 和 derived facts

除了 raw `t.events` stream，runner 还会派生 assertions 会读取的 typed facts：tool calls（name、input、output、error state）、subagent calls 和 HITL input requests。让 session 为下一条 message 保持 open 的 turn，是 successful turn 的正常 end state；未回答 HITL input 上的 parking 会单独 tracking，`t.completed()` 和 `t.waiting()` 就基于它判断。

built-in assertions 覆盖几乎所有内容。当你需要直接读取 stream 时，`t.event(predicate, label)` 是 escape hatch：

```ts
t.event(
  (events) =>
    events.some((e) => e.type === "message.completed" && e.data.message?.includes(marker)),
  "assistant reply includes the marker",
);
```

## Severity

每个 assertion 都返回 chainable handle。Severity 位于 assertion 上，因此没有需要同步的单独 thresholds map。

- `.gate(threshold?)` 是 hard。miss 会把 eval 标记为 `failed`，并让 `eve eval` 非零退出。
- `.soft(threshold?)` 是 tracked data。below-threshold miss 会把 eval 标记为 `scored`，只在 `--strict` 下 fatal。没有 threshold 时，它只 tracking，永远不会失败。
- `.atLeast(threshold)` 是带 bar 的 soft（等价于 `.soft(threshold)`）。

默认值经过选择，因此你很少需要设置 severity。Run-level methods 和 `includes`/`equals`/`matches` 是 gates；`similarity` 和每个 `t.judge.*` assertion 都是 soft。只有偏离默认时才 annotate：

```ts
t.calledTool("get_weather").soft(); // record the tool call as a metric, don't gate
t.check(t.reply, similarity("Sunny")).atLeast(0.8); // gate the fuzzy match under --strict
t.check(t.reply, includes("error")).soft(); // track without failing the build
```

## 接下来阅读

- [Judge](./judge)：带 thresholds 的 LLM-graded assertions
- [Cases](./cases)：assertions 附着的位置
- [Running evals](./running)：verdicts 如何映射到 exit codes
