---
title: "Context Control"
description: "跨 instructions、skills、workspace 和 subagents 控制 eve agent 的 model 何时看到什么。"
---

eve 提供了几种杠杆，用来控制 model 何时看到什么。`instructions.md`（或 `instructions.ts`）始终启用，`skills/` 可用但按需加载，workspace 和 sandbox 则通过 tools 可见，而不是直接粘贴进 prompt。

## 使用 `instructions.md` 设置基础身份

使用 `instructions.md` 编写 agent 的核心 contract。

```md
You are a careful support assistant. Be concise, verify facts before replying, and explain when you
used a tool.
```

让这个文件聚焦于应适用于每个 turn 的稳定行为。

## 使用 `instructions.ts` 在 TypeScript 中组合 instructions

如果要用 typed helpers、lib code 或 environment-derived values 构建 instructions prompt，请把它编写为 module，而不是 markdown。

```ts title="agent/instructions.ts"
import { defineInstructions } from "eve/instructions";
import { buildInstructionsPrompt } from "./lib/prompts.js";

export default defineInstructions({
  markdown: buildInstructionsPrompt(),
});
```

module-backed instructions 会在 build time 运行一次。eve 会把生成的 markdown 捕获到 compiled manifest 中，因此 runtime 会为每个 session 提供同一个 prompt，而不需要重新运行 module。

## 使用 `skills/` 按需加载 procedures

Skills 默认不会进入 always-on prompt，这让 rich procedures 保持可用，同时不会让每个 turn 膨胀。eve 会暴露可用 skills，并添加 framework-owned `load_skill` tool。当请求明显匹配某个 skill description，或用户明确点名某个 skill 时，model 会激活该 skill，eve 会把 skill 的 markdown 追加到 active instructions 中，供后续 turn work 使用。

### Flat skill

```md title="agent/skills/get-weather.md"
Use the weather tool before answering forecast or temperature questions.
```

### Packaged skill

```md title="agent/skills/research/SKILL.md"
---
description: Research unfamiliar topics before answering with confidence.
---

When the task is novel or ambiguous, gather evidence first, then answer with the key facts and the
remaining uncertainty.
```

当你还希望同一个 skill 目录下有 `references/`、`assets/` 或 `scripts/` 等 sibling files 时，packaged skills 很有用。这些路径会出现在 runtime workspace root 下，因此 model 可以用普通 file 或 shell tools 检查它们，而不是把内容粘贴进 prompt。

完整 authoring model 和 install notes 见 [Skills](../skills)。

## 把 runtime files 放进 workspace，而不是 prompt

eve 不会把整个 authored surface inline 到 prompt 中。相反，它会给 model 一个浅层 workspace hint，并提供 runtime tools，让 model 在需要时深入检查。Skill files 位于 active workspace root 下，model 会用共享的 `bash` tool 检查它们，这样可以让 prompts 更小，并让 file 和 command work 更明确。

workspace 和 sandbox model 见 [Sandbox](../sandbox)。

## 用 subagent 委派给 specialist

如果某个 task 值得拥有自己的 prompt 和 tool surface，请使用 local subagent，而不是让 root agent 过载。Subagents 也是 context-control 杠杆。它们拥有自己的 `instructions.md`、tools 和 sandbox，并在自己的 delegated context 中运行，而不是 inline 扩展 root agent。

见 [Subagents](../subagents)。

## 使用 `defineDynamic` 提供 dynamic context

上面的杠杆都是 static 的，编写一次后在每个 session 中相同。当正确 context 取决于 caller（他们的 team、tenant、plan 或 feature flags）时，请在 runtime 解析它。`agent/instructions/` 中的 `defineDynamic` 返回 per-session system prompt，`agent/skills/` 中的 `defineDynamic` 返回 caller 可以加载的 skills 集合。两者都会读取 `ctx.session.auth` 或 channel metadata，因此 billing team 的 caller 会得到 billing instructions 和 playbook，而其他人看不到它们。resolver API 以及每个 event 的触发时机见 [Dynamic capabilities](../guides/dynamic-capabilities)。

## 推荐的 context layout

按 context 用途选择杠杆：

- `instructions.md` 用于 agent 的永久身份。保持简短且稳定。
- 当你需要在 build time 用 typed helpers 组合 prompt 时，使用 `instructions.ts`。
- `skills/` 用于只应在需要时加载的 optional procedures。把 long procedures 放到这里，而不是放进 always-on prompt。
- `tools/` 用于暴露 typed integrations。
- 当 task 需要不同的 specialist surface 时，使用 subagent；只在真正存在 specialization boundaries 时使用。
- 当 model 应检查文件或运行命令，而不是依赖粘贴的 instructions 时，使用 workspace 或 sandbox。

## 接下来阅读

- [Tools](../tools)：暴露 model 可以调用的 typed integrations。
- [Skills](../skills)：on-demand procedures 的完整 authoring model。
- [Subagents](../subagents)：委派给拥有自己 prompt 和 tools 的 specialist。
- [Dynamic capabilities](../guides/dynamic-capabilities)：用 `defineDynamic` 解析 per-session instructions 和 skills。
- [Hooks](../guides/hooks)：在 session events 上运行代码，更新 dynamic resolvers 会读取的 channel state。
