---
title: "Human-in-the-loop"
description: "为人员暂停 run：用 approval gate tool，或让 agent 提问，并在他们回答后 durable 地恢复。"
url: /human-in-the-loop
---

Human-in-the-loop（HITL）指 agent durable 地暂停并等待人员的任何点。有两件事会触发它，并且都使用同一套 pause-and-resume protocol：

- **Approvals**：tool 在运行前（或代替运行）需要人员签核。agent 决定调用 tool；human 决定它是否执行。
- **Questions**：agent 本身在 mid-turn 向用户提出 clarifying question 或 choice，并 park 到用户回答。

无论哪种方式，run 都会 durable 地 park 在 `session.waiting`，等待任意时长，可能是几秒，也可能是几天；answer 到达后会从离开的位置精确继续。Channels 会为你渲染 request。

## Approvals

Approval 是 [tool](/docs/tools) 的一个属性，会在运行前为人员暂停。使用 `needsApproval` 和来自 `eve/tools/approval` 的 helpers gate tool：

```ts title="agent/tools/refund_charge.ts"
import { defineTool } from "eve/tools";
import { always } from "eve/tools/approval";
import { z } from "zod";

export default defineTool({
  description: "Refund a charge.",
  inputSchema: z.object({ chargeId: z.string(), amount: z.number() }),
  needsApproval: always(), // or once() / never() / a predicate
  async execute(input) {
    return refund(input);
  },
});
```

| Helper     | 行为                                                             |
| ---------- | ---------------------------------------------------------------- |
| `never()`  | 永不要求 approval（省略时的默认值）。                            |
| `once()`   | 仅在 tool 于 session 中第一次运行时要求 approval；之后自动允许。 |
| `always()` | 每次调用前都要求 approval。                                      |

默认情况下，省略 `needsApproval` 的行为类似 `never()`，因此 tool calls 可能在没有 human approval 的情况下执行。对于敏感、不可逆、受监管、金融、医疗、就业、住房、法律、影响安全、影响用户或会产生外部副作用的 actions，请要求 human approval 或其他 safeguards。

当 decision 取决于 input 时，请传入自己的 predicate，而不是 helper。它会收到 `{ toolName, toolInput, approvedTools }` 并返回 boolean。`toolInput` 可能是 undefined，因此请保护访问。若只在 amount 超过 threshold 时要求 approval：

```ts
needsApproval: ({ toolInput }) => (toolInput?.amount ?? 0) > 1000,
```

用 approval gate side effect，也是让非幂等工作在 replays 中安全的方式：位于 `always()` 后面的扣款或邮件，不会在没有 fresh human decision 的情况下从 re-run step 触发。

## Questions

built-in `ask_question` tool 让 model 可以暂停并询问用户，而不是猜测。它没有 `execute`，model 会用 `{ prompt, options?, allowFreeform? }` 调用它：

- `prompt`：要向用户提出的问题。
- `options`：可提供的可选 choices 列表。Channels 会把它们渲染为 buttons 或 select menu。
- `allowFreeform`：用户是否可以用 free text 回答，而不是选择一个 option。

`ask_question` 是 [default harness](/docs/concepts/default-harness) 的一部分，因此无需定义任何内容即可使用。它会产生与 approval 相同的 `input.requested` pause，并以相同方式恢复。

## pause 和 resume 如何工作

Approvals 和 questions 共享同一 protocol：

1. model 请求 input（approval 或 `ask_question`）。
2. eve 发出携带 pending requests 的 `input.requested` stream event。
3. turn durable 地 park 在 `session.waiting`，等待任意时长。
4. client 用 `inputResponses`（结构化，按 `requestId` keyed）或普通 follow-up `message` 回答。文本匹配 option label（大小写不敏感）的 follow-up 会自动 resolve。

run 会从 park 的准确位置继续。由于 pause 是 durable 的，等待期间不会有任何内容保存在内存中；process 可以 restart，parked turn 仍会保留。

它基于的完整 event 和 resume contract 见 [Sessions, runs & streaming](/docs/concepts/sessions-runs-and-streaming)。

## 从 client 或 channel 回答

Channels 会把 requests 转成 native UI：Slack adapter 会把 approvals 渲染为 buttons，把 questions 渲染为 select menus，并把用户 choice 写回答案。每个 [channel](/docs/channels) 都会免费获得这套能力。

从你自己的 frontend 中，读取 latest message 上的 pending request，并通过同一个 session 回答。client-side reducer 和 `inputResponses` shape 见 [Building a frontend](/docs/guides/frontend/overview#human-in-the-loop-prompts)。

## 接下来阅读

- [Tools](/docs/tools)：定义 approval gate 的 typed actions
- [Default harness](/docs/concepts/default-harness)：built-in tools，包括 `ask_question`
- [Sessions, runs & streaming](/docs/concepts/sessions-runs-and-streaming)：pause 背后的 event 和 resume contract
- [Building a frontend](/docs/guides/frontend/overview)：从你自己的 UI 渲染和回答 requests
