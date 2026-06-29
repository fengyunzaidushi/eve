---
title: "运行 Analysis"
description: "Build an Agent 教程第 5 部分。把 warehouse schema seed 到 sandbox workspace，然后执行 SQL 之外的计算和制图。"
---

SQL 会告诉 analytics assistant 数字，但 cohort curve、forecast 或 chart 需要真实计算。这正是 sandbox 的用途。它是一个带有 `/workspace` filesystem 的隔离 bash environment，每个 agent 都会获得一个。

这需要两部分。先 seed model 可读取的 reference files，然后基于它们进行计算。

## 将 schema seed 到 workspace

把 warehouse schema mount 到 sandbox 中，这样 model 就不必猜测 table shapes。Seeding 使用 folder sandbox layout，其中 `agent/sandbox/workspace/` 下的任何内容都会在 session bootstrap 时进入 live `/workspace` cwd。

```text
agent/sandbox/
  workspace/
    schema.sql        ← lands at /workspace/schema.sql
    notes/grain.md    ← lands at /workspace/notes/grain.md
```

```sql
-- agent/sandbox/workspace/schema.sql
-- Reference only: table shapes the analyst can read before writing queries.
CREATE TABLE orders     (id INT, customer_id INT, amount_cents INT, created_at DATE);
CREATE TABLE customers  (id INT, name TEXT, plan TEXT, signed_up_at DATE);
```

top-level workspace entries 会自动暴露给 model，因此它知道可以读取 `schema.sql`。不需要 `agent/sandbox/sandbox.ts`。`workspace/` 文件夹会保留 default sandbox，并把你的文件 seed 进去。

## 在 sandbox 中计算和制图

built-in `bash`、`read_file` 和 `write_file` tools 已经以 sandbox 为目标。当你编写自己的 analysis steps 时，请用 `ctx.getSandbox()` 获取 live handle：

```ts title="agent/tools/chart_series.ts"
import { defineTool } from "eve/tools";
import { z } from "zod";

export default defineTool({
  description:
    "Plot a time series to a PNG in the workspace. Pass {date, value} points; " +
    "returns the chart path.",
  inputSchema: z.object({
    title: z.string(),
    points: z.array(z.object({ date: z.string(), value: z.number() })),
  }),
  async execute({ title, points }, ctx) {
    const sandbox = await ctx.getSandbox();
    await sandbox.writeTextFile({
      path: "analysis/series.json",
      content: JSON.stringify({ title, points }),
    });
    await sandbox.writeTextFile({
      path: "analysis/plot.py",
      content: [
        "import json, matplotlib",
        "matplotlib.use('Agg')",
        "import matplotlib.pyplot as plt",
        "d = json.load(open('series.json'))",
        "plt.plot([p['date'] for p in d['points']], [p['value'] for p in d['points']])",
        "plt.title(d['title']); plt.savefig('chart.png')",
      ].join("\n"),
    });
    const root = sandbox.resolvePath("analysis");
    await sandbox.run({ command: `cd ${JSON.stringify(root)} && python plot.py` });
    return { chart: `${root}/chart.png` };
  },
});
```

这个 tool 会 shell out 到带有 matplotlib 的 `python`，而 sandbox base image 并未预装它。请在 sandbox bootstrap 中安装 runtime（或把它 bake 到 custom image 中），让 `python plot.py` 可以解析。bootstrap 的运行位置见 [Sandbox](../sandbox)。

现在提出一个超出 plain SQL 的请求。如果你跳过了第 4 步，它仍可基于第 3 步的 sample dataset 工作：

```text
Plot total order revenue per customer.
```

model 会查询数字（第 4 步的 warehouse，或你跳过时的 sample dataset），检查 `schema.sql` 以确保 grain 正确，然后调用 `chart_series` 在 `/workspace` 中渲染 PNG。

## Secrets 不会进入 sandbox

sandbox 没有 `process.env`，也无法访问你的 app secrets。你的 warehouse token 存在于 app runtime 中，firewall brokering 是它通往 warehouse host 的唯一路径。它永远不会进入 sandbox process。

local backend 会在 `eve dev` 期间在你的 laptop 上运行 sandbox；在 Vercel 上则运行于 Vercel Sandbox。Lifecycle、backends 和 network policy 见 [Sandbox](../sandbox)。

→ 下一步：[Remember definitions](./remember-definitions)

了解更多：[Sandbox](../sandbox)
