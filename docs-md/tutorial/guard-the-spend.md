---
title: "控制 Spend"
description: "Build an Agent 教程第 8 部分。用 cost-based approval gate 住昂贵 queries。agent 会暂停、询问并恢复。"
---

一次 warehouse query 可能扫描数 TB 数据并抬高账单。因此，在 analytics assistant 发起昂贵 scan 之前，让它停下来向你确认。agent 会暂停、询问你，并带着你的回答恢复。这就是 human-in-the-loop，你只需在 tool 上接入一个字段。

`needsApproval` 会在 `execute` 之前运行。返回 `true` 时，turn 会 park 在 approval request 上；你回答后，run 会从那个准确的 step 继续。该函数会收到 tool input，因此你可以基于 cost 做决定。

## 先估算，再 gate

这一步继续让 `run_sql` 使用第 3 步的 sample dataset，方便你在本地演示 gate。使用真实 warehouse 时，你会以相同方式 gate 第 4 步的 warehouse connection tool，只是基于 dry-run byte estimate，而不是下面的 toy heuristic。

添加一个便宜的 estimator，并基于它 gate `run_sql`：

```ts title="agent/lib/cost.ts"
// Illustrative: a real warehouse exposes a dry-run byte estimate.
export function estimateScanGb(sql: string): number {
  return /\bwhere\b/i.test(sql) ? 1 : 200; // unfiltered scans are the expensive ones
}
```

```ts title="agent/tools/run_sql.ts"
import { defineTool } from "eve/tools";
import { z } from "zod";
import { runReadOnlySql } from "../lib/sample-db.js";
import { estimateScanGb } from "../lib/cost.js";

const THRESHOLD_GB = 50;

export default defineTool({
  description: "Run a read-only SQL query against the analytics tables.",
  inputSchema: z.object({ sql: z.string() }),
  // Cost-based gate: only the expensive queries need a human yes.
  needsApproval: ({ toolInput }) => estimateScanGb(toolInput?.sql ?? "") > THRESHOLD_GB,
  async execute({ sql }) {
    const { columns, rows } = await runReadOnlySql(sql);
    return { columns, rows: rows.slice(0, 500), truncated: rows.length > 500 };
  },
});
```

便宜 queries 会直接运行。估算值高于 threshold 的 query 会触发 gate。

## 暂停、询问、恢复

提出一个会强制执行 large unfiltered scan 的请求：

```text
Total revenue across all customers, all time, broken out by day.
```

model 会提出 query，`needsApproval` 返回 `true`，turn 随即 park。stream 会发出 `input.requested`，然后是 `session.waiting`。prompt 的呈现取决于 channel，可能是 TUI 中的按钮、Slack 中的 Block Kit，或 web 上的 UI control。批准后，run 会从那个准确的 step 恢复，然后运行 query。拒绝后，tool 会被跳过，并把原因告诉 model。

每个 session 正好有一个 active continuation。针对 stale handle 回答 approval 会被拒绝，因此无法对同一个 parked turn 执行 double-resume。

同一套机制也支撑 built-in `ask_question` tool（model 在 mid-turn 向你提问），以及通过 `approval: once()` 实现的 per-connection approval。见 [Tools and human-in-the-loop](../tools)。

→ 下一步：[Ship it](./ship-it)

了解更多：[Tools and human-in-the-loop](../tools)
