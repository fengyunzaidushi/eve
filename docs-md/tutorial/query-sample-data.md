---
title: "查询 Sample Data"
description: "Build an Agent 教程第 3 部分。为捆绑的 sample dataset 添加 run_sql tool，并观察 tool loop。"
---

analytics assistant 已经能对话，但还看不到任何一行数据。给它一个 tool。tool 是 action primitive：typed input 进入，你的代码运行，structured output 返回。model 看到的名称来自文件名，因此 `agent/tools/run_sql.ts` 会成为 tool `run_sql`。

## 一个很小的 sample dataset

为了让第一次 query 无需设置即可运行，请在 `agent/lib/` 下捆绑一个小型 in-memory dataset。保持它很小。这只是一次性 scaffolding，不是真正的 warehouse（第 4 步会添加）。

```ts title="agent/lib/sample-db.ts"
// A toy SQLite-in-memory stand-in. Swap for your real warehouse in Step 4.
import initSqlJs from "sql.js";

const SEED = `
  CREATE TABLE orders (id INTEGER, customer_id INTEGER, amount_cents INTEGER, created_at TEXT);
  INSERT INTO orders VALUES
    (1, 10, 4200, '2026-05-01'), (2, 10, 1500, '2026-05-03'),
    (3, 11, 9900, '2026-05-04'), (4, 12,  800, '2026-05-06');
  CREATE TABLE customers (id INTEGER, name TEXT, plan TEXT);
  INSERT INTO customers VALUES
    (10, 'Acme', 'pro'), (11, 'Globex', 'enterprise'), (12, 'Initech', 'free');
`;

let dbPromise: Promise<import("sql.js").Database> | null = null;

async function db() {
  dbPromise ??= initSqlJs().then((SQL) => {
    const database = new SQL.Database();
    database.run(SEED);
    return database;
  });
  return dbPromise;
}

export async function runReadOnlySql(sql: string) {
  const database = await db();
  const [result] = database.exec(sql);
  if (!result) return { columns: [], rows: [] as unknown[][] };
  return { columns: result.columns, rows: result.values };
}
```

## 定义 run_sql tool

```ts title="agent/tools/run_sql.ts"
import { defineTool } from "eve/tools";
import { z } from "zod";
import { runReadOnlySql } from "../lib/sample-db.js";

export default defineTool({
  description:
    "Run a read-only SQL query against the analytics tables (orders, customers) " +
    "and return the columns and rows.",
  inputSchema: z.object({
    sql: z.string().describe("A single read-only SELECT statement."),
  }),
  async execute({ sql }) {
    const { columns, rows } = await runReadOnlySql(sql);
    // Bound the output so a wide query can't flood the model's context.
    return { columns, rows: rows.slice(0, 500), truncated: rows.length > 500 };
  },
});
```

Tools 会在你的 app runtime 中运行，并拥有完整的 `process.env`，而不是在 sandbox 中运行。`inputSchema` 既会验证 call，也会为你在 `execute` 内收到的 `input` 提供类型。关于 output bounding、`toModelOutput` 和 authorization，见 [Tools](../tools)。

## 观察 tool loop

用 `npm run dev` 重启 dev server，并提问：

```text
Which customer has spent the most, and how much?
```

在 TUI 中观察 loop 的执行过程。model 会发出 `run_sql` call，eve 运行你的 `execute`，rows 作为 tool result 返回。model 读取它们，并用真实数字回答。eve 驱动了整个 loop。你只提供了这个 tool。

→ 下一步：[Connect a warehouse](./connect-a-warehouse)

了解更多：[Tools](../tools)
