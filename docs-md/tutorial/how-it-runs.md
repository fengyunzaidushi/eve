---
title: "运行方式"
description: "Build an Agent 教程第 2 部分。Session、turn 和 durable steps，以及为什么 turn 能在 crash 后继续。"
---

analytics assistant 发送了一条 message，并得到了一条 answer。背后的模型可以用三个术语描述。

| 术语        | 含义                                           |
| ----------- | ---------------------------------------------- |
| **session** | 你的完整 conversation（durable，可跨越数天）。 |
| **turn**    | 你发送的一条 message，以及它触发的工作。       |
| **step**    | turn 内的 durable checkpoint。                 |

每个 turn 都会作为 durable workflow 运行，eve 会在每个 step 保存进度。已完成的 steps 永远不会重新运行；eve 会 replay 已记录的结果。执行中断的 step 会重新运行，因此请让扣款或发送邮件等非幂等 side effects 变成幂等，或用 approval gate 住它们。正在等待你的 turn（一个 approval 或问题）会在你回答时恢复，即使已经过了很久。

这就是本教程后续功能以这种方式工作的原因：

- 第 4 步的 warehouse sign-in 会 park 住 turn，直到你在浏览器中授权。等几分钟也没关系。
- 第 6 步的 metric glossary 会跨 turns 保留。State 会在 step boundaries checkpoint，因此能够留下来。
- 第 8 步的 spend approval 会在你的 yes/no 上暂停 turn，然后从停止处准确继续。

你负责编写 capabilities，包括 tools、instructions、channels 和 skills。eve 驱动 model-to-tool loop，并决定 turn 何时继续、等待或结束。你永远不需要自己编写这个 loop。

→ 下一步：[Step 3: Query sample data](./query-sample-data)

深入了解：[Execution model & durability](../concepts/execution-model-and-durability)
