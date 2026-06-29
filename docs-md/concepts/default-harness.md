---
title: "Harness"
description: "eve 开箱即用的 agent loop、每个 agent 随附的 built-in tools，以及如何覆盖或禁用它们。"
---

default harness 是每个 eve agent 随附的内容。它包括 framework-owned agent loop，以及一组 model 无需你编写任何代码即可调用的 built-in tools。你可以用 agent 专属 capabilities 扩展它。loop 本身，也就是 turn 如何运行、checkpoint 和恢复，见 [Execution model and durability](./execution-model-and-durability)。

## Compaction

harness 会防止 long session 溢出 model 的 context window。当 conversation 超过 window 的某个比例（`thresholdPercent`，默认 `0.9`）后，它会把较早的 turns 汇总成 compact form 并继续运行。除非你覆盖，否则 summary 使用 active turn model。请在 `agent.ts` 的 [`compaction`](../agent-config#compaction) 下调整触发时机和方式：

```ts title="agent/agent.ts"
export default defineAgent({
  model: "anthropic/claude-opus-4.8",
  compaction: {
    thresholdPercent: 0.75,
  },
});
```

Compaction 还会自动保留 framework 自己的 tool state。它会重置 read-before-write tracking（这样之后的 write 会重新读取其 read evidence 已被汇总掉的文件），并重新注入 active todo list，让 model 在 summary 之后仍保留 task list。这里没有可配置的 per-tool hook。

## Built-in tools

这些 tools 随每个 agent 提供，无需 imports。harness 会先向 model 展示 tool descriptors，然后只执行 model 实际调用的内容；discovery 永远不会运行它们。shell 和 file tools（`bash`、`read_file`、`write_file`、`glob`、`grep`）存在于 app runtime 中，并把工作 proxy 到 agent 的单个 [sandbox](../sandbox)；其余则在 app runtime 中运行。下方 “Where it runs” 列说明每个 tool 的效果落在哪里。

| Tool                | 作用                                                                                                                                                                                                     | 运行位置    |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- |
| `bash`              | 运行 shell command。                                                                                                                                                                                     | Sandbox     |
| `read_file`         | 读取 text file，并输出行号（启用 read-before-write）。                                                                                                                                                   | Sandbox FS  |
| `write_file`        | 写入完整文件；强制执行 read-before-write 和 stale-read detection。                                                                                                                                       | Sandbox FS  |
| `glob`              | 按 glob pattern 查找文件。                                                                                                                                                                               | Sandbox FS  |
| `grep`              | 用 regex 搜索文件内容。                                                                                                                                                                                  | Sandbox FS  |
| `web_fetch`         | Fetch URL。                                                                                                                                                                                              | App runtime |
| `web_search`        | 搜索 web（provider-managed；从 model provider 解析）。                                                                                                                                                   | Provider    |
| `todo`              | 维护 durable per-session todo list。                                                                                                                                                                     | App runtime |
| `ask_question`      | 在 mid-turn 向用户提出 clarifying question 或 choice，并 park 到用户回答。没有 `execute`；model 会用 `{ prompt, options?, allowFreeform? }` 调用它。见 [Human-in-the-loop](../tools/human-in-the-loop)。 | App runtime |
| `agent`             | 把 subtask 委派给自身的一个副本（共享 parent sandbox + tools，fresh history/state）。                                                                                                                    | App runtime |
| `load_skill`        | 把 on-demand [skill](../skills) 的 instructions 拉入当前 turn。仅当 agent 声明 skills 时存在。                                                                                                           | App runtime |
| `connection_search` | 在已声明的 [connections](../connections) 中发现 tools；匹配的 tools 会变成可直接调用。仅当 agent 声明 connections 时存在。                                                                               | App runtime |

说明：

- **`agent`** 会在 focused task 上运行当前 agent 的副本。它继承相同的 tools、connections 和 instructions，但以 fresh conversation history 和 fresh [state](../guides/state) 启动。child 共享 parent 的 sandbox filesystem，因此它写入的任何内容对 parent 可见。见 [Subagents](../subagents)。
- **`load_skill`** 只会把 instructions 拉入 context。它不添加新的 execution surface，因为行为仍来自 agent 已有的 tools。
- **`connection_search`** 是面向 model 的 `connection__search` tool。一次 search 会按 qualified name（例如 `connection__linear__list_issues`）暴露 connection 的 tools，之后 model 可以直接调用它们。只有当 agent 有 connections 时才会注册。
- **`web_search`** 没有 local executor；由 provider 运行。若要提供自己的实现，请用 `defineTool()` 覆盖它。

production use 前请审查这些 built-in tools。对于任何可以访问 filesystem、network、shell 或 sensitive data 的 tool，请禁用、包装、限制或要求 approval。

## 覆盖 default

在相同 slug 下编写 tool，它就会接管同名 built-in。文件 `agent/tools/write_file.ts` 通过存在本身替换 built-in `write_file`：

```ts title="agent/tools/write_file.ts"
import { defineTool } from "eve/tools";
import { writeFile } from "eve/tools/defaults";

export default defineTool({
  ...writeFile, // keep the default description, schema, and executor
  async execute(input, ctx) {
    console.log("[write_file]", input.path);
    return writeFile.execute(input, ctx);
  },
});
```

framework defaults 可从 `eve/tools/defaults` 导入（`bash`、`readFile`、`writeFile`、`glob`、`grep`、`webFetch`、`webSearch`、`todo`、`loadSkill`），因此你可以 spread、wrap 或 patch 它们。跳过 spread 时，replacement 会拥有自己的 context。为 `todo` 新建的 `defineTool` 不会继承 framework 的 durable state key。

## 禁用 default

从以 tool slug 命名的文件中 export 一个 `disableTool()` sentinel。文件名决定要移除哪个 default：

```ts title="agent/tools/bash.ts"
import { disableTool } from "eve/tools";

export default disableTool();
```

如果文件名不匹配任何已知 framework tool，resolution 会失败，而不是静默无事发生，因此 typo 会在 build time 暴露，而不是移除错误的 tool。

## 何时覆盖、禁用或编写新 tool

塑造 harness 有三种操作。正确选择取决于 model 是否应保留 built-in capability。

- **Override**：当你想要同一 capability 但行为不同。spread 来自 `eve/tools/defaults` 的 default 并 wrap 它（logging、额外 guard、不同 backend），model 仍会看到该名称的 tool。Spreading 会保留 default 的 description、schema 和任何 framework state，例如 `todo` tool 的 durable state key。去掉 spread 后，replacement 会拥有自己的 context，并失去那套 wiring。
- **Disable**：当 model 完全不应拥有该 capability。`disableTool()` sentinel 会移除 built-in，model 永远看不到它。对于不应运行 shell commands 或 fetch 任意 URLs 的 agent，可以用它锁定 `bash` 或 `web_fetch`。
- **Author a new tool**：当你想要 harness 未随附的 capability。在 `agent/tools/` 下给它一个新的 slug，它会加入 built-ins，而不是替换某一个。authoring model 见 [Tools](../tools)。

## Opt-in `Workflow` tool

随包提供了 experimental `Workflow` tool，但默认关闭。若要开启它，请从 `agent/tools/workflow.ts` 重新 export opt-in marker：

```ts
export { ExperimentalWorkflow as default } from "eve/tools";
```

开启后，model 可以从 model-authored JavaScript 编排 agent 自己的 subagents，并且全部作为一个 durable step 执行。见 [Dynamic workflows](../guides/dynamic-workflows)。

## 接下来阅读

- [Tools](../tools)：定义你自己的 tools，用 approval gate 它们，并用 `toModelOutput` 塑造输出
- [Dynamic capabilities](../guides/dynamic-capabilities)：使用 `defineDynamic` 按 session 生成 tool set
- [Sandbox](../sandbox)：shell 和 file tools 运行所在的 sandbox
