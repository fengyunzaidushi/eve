---
title: "Instructions"
description: "使用 instructions.md 或 instructions.ts 编写 agent 的 always-on system prompt。"
---

Instructions 是 always-on system prompt，是 agent 的永久身份，而不是在需要时才引入的 procedure。任何每个 turn 都应成立的内容都适合放在这里，例如规则、persona 或约束。eve 会把 instructions 放在 session 中每次 model call 的最前面。

## 编写 instructions

最简单的 instructions 是 agent 根目录下的一个 markdown 文件。你写下的内容就是 prompt：

```md title="agent/instructions.md"
You are a concise assistant. Use tools when they are available.
```

这个文件应只保存稳定行为，例如身份、语气和长期规则。

## Markdown vs TypeScript

静态 prompt 适合放在 markdown（`agent/instructions.md`）里。当你需要通过 typed helpers、`lib/` 代码或 build-time values 构建 prompt 时，再切换到 TypeScript module（`agent/instructions.ts`）。

```ts title="agent/instructions.ts"
import { defineInstructions } from "eve/instructions";
import { buildInstructionsPrompt } from "./lib/prompts.js";

export default defineInstructions({
  markdown: buildInstructionsPrompt(),
});
```

`defineInstructions` 接受一个字段 `markdown`，也就是解析后的 prompt text。由 module 支持的 prompt 会在 build time 运行一次。eve 会把生成的 markdown 捕获到 compiled manifest 中，因此 runtime 会为每个 session 提供同一个 prompt，而不会重新运行该 module。

## 将 instructions 拆分到目录

如果需要多个文件，请添加 `agent/instructions/` 目录。eve 会非递归读取其中的条目，并接受 `.md` 文件和 `.ts` modules（`.ts` 文件可以包装 `defineInstructions` 或 `defineDynamic`）。条目会按文件名的字母顺序（`localeCompare`）组合。

agent 根目录下的扁平 `agent/instructions.md`（或 `.ts`）可以与该目录共存。根文件内容会排在最前，然后是排序后的目录条目。你不能同时在根目录编写 `instructions.md` 和 `instructions.ts`；这种组合会导致 build error。

## Instructions vs skills

Instructions 和 [skills](./skills) 都会把文本送入 model 的 context。区别在于加载时机：

|                           | Loaded                                  | Use for                               |
| ------------------------- | --------------------------------------- | ------------------------------------- |
| `instructions.md` / `.ts` | Always on，每个 turn                    | 永久身份和长期规则                    |
| `agent/skills/*`          | 按需加载，当 model 调用 `load_skill` 时 | 不应让每个 turn 膨胀的可选 procedures |

保持 instructions 简短且稳定。较长或依场景而定的 procedures 应放在 [skills](./skills) 中，只有在请求需要时才进入 context。

Instructions 永远不会运行代码。需要类型化的可执行行为时，请使用 [tool](./tools)。

## Dynamic instructions

如果要在 runtime 根据 session context（auth、tenant 或 channel）解析 prompt，请把 `defineInstructions` 包装在 `defineDynamic` resolver 中。见 [Dynamic capabilities](./guides/dynamic-capabilities)。

## 免责声明

作为 deployer，你有责任确保你的 agent 符合适用法律。

当 eve agent 与人沟通时，如果法律要求，你可能需要披露他们正在与自动化 AI 系统互动。eve 不会自动添加这类披露；请在 instructions 和/或 channel responses 中配置。

## 接下来阅读

- [Tools](./tools)：typed actions，下一项可添加的能力
- [Context control](./concepts/context-control)：控制 model 可见内容的全部杠杆
- [Skills](./skills)：on-demand procedures，与 always-on instructions 相对应
